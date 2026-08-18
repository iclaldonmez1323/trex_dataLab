import io
import os
import json
import uuid
import requests
import google.generativeai as genai
from typing import Dict, Any, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import numpy as np

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest")
user_gemini_api_key: str = GEMINI_API_KEY

# Sohbet oturumları (in-memory): session_id -> history listesi
_ai_sessions: dict = {}
_MAX_HISTORY_TURNS = 20

app = FastAPI(title="trex DataLab API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_dataset: Dict[str, Any] = {}
active_df_cache: Optional[pd.DataFrame] = None
original_df_cache: Optional[pd.DataFrame] = None
processed_df_cache: Optional[pd.DataFrame] = None
dropped_columns: set = set()
preprocessing_history_stack: list = []
MAX_FILE_SIZE = 50 * 1024 * 1024


def clean_val_for_json(val: Any) -> Any:
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, (np.floating, float)):
        if np.isneginf(val) or np.isposinf(val) or np.isnan(val):
            return None
        return float(val)
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    return str(val)


def parse_csv_content(content_bytes: bytes, filename: str) -> pd.DataFrame:
    encodings = ["utf-8-sig", "utf-8", "cp1254", "iso-8859-9", "latin-1"]
    last_error: Optional[Exception] = None

    for enc in encodings:
        try:
            sample = content_bytes[:8192].decode(enc, errors="strict")
            delimiter = ","
            if sample.count(";") > sample.count(","):
                delimiter = ";"
            elif sample.count("\t") > sample.count(","):
                delimiter = "\t"

            df = pd.read_csv(
                io.BytesIO(content_bytes),
                encoding=enc,
                sep=delimiter,
                engine="c",
                low_memory=False
            )
            return df
        except Exception as e:
            last_error = e
            continue

    try:
        df = pd.read_csv(
            io.BytesIO(content_bytes),
            encoding="utf-8",
            sep=None,
            engine="python",
            encoding_errors="replace"
        )
        return df
    except Exception as e:
        raise ValueError(f"Dosya okunamadı: {str(last_error or e)}")


@app.get("/")
@app.get("/index.html")
async def serve_index():
    return FileResponse("static/index.html")


@app.get("/data-quality")
@app.get("/data-quality.html")
async def serve_data_quality():
    return FileResponse("static/data-quality.html")


@app.get("/preprocessing")
@app.get("/preprocessing.html")
async def serve_preprocessing():
    return FileResponse("static/preprocessing.html")


@app.get("/visualization")
@app.get("/visualization.html")
async def serve_visualization():
    return FileResponse("static/visualization.html")


@app.get("/portfolio")
@app.get("/portfolio.html")
async def serve_portfolio():
    return FileResponse("static/portfolio.html")


@app.get("/settings")
@app.get("/settings.html")
async def serve_settings():
    return FileResponse("static/settings.html")


@app.get("/support")
@app.get("/support.html")
async def serve_support():
    return FileResponse("static/support.html")


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    global active_dataset, active_df_cache

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sadece CSV dosyası yükleyebilirsiniz."
        )

    content = await file.read()
    size_bytes = len(content)

    if size_bytes > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Dosya boyutu 50MB sınırını aşıyor."
        )

    if size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yüklenen dosya boş."
        )

    try:
        df = parse_csv_content(content, file.filename)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV dosyası işlenirken hata oluştu: {str(err)}"
        )

    rows_count = int(len(df))
    cols_count = int(len(df.columns))
    missing_count = int(df.isna().sum().sum())
    duplicates_count = int(df.duplicated().sum())

    numeric_df = df.select_dtypes(include=[np.number])
    numeric_cols_count = int(len(numeric_df.columns))
    categorical_cols_count = int(cols_count - numeric_cols_count)

    column_types = {}
    for col in df.columns:
        if col in numeric_df.columns:
            column_types[col] = "numeric"
        else:
            column_types[col] = "categorical"

    preview_df = df.head(10)
    preview_rows = []
    for _, row in preview_df.iterrows():
        row_dict = {}
        for col in df.columns:
            row_dict[col] = clean_val_for_json(row[col])
        preview_rows.append(row_dict)

    result_data = {
        "filename": file.filename,
        "size_bytes": size_bytes,
        "rows": rows_count,
        "columns": cols_count,
        "missing": missing_count,
        "duplicates": duplicates_count,
        "numeric_cols": numeric_cols_count,
        "categorical_cols": categorical_cols_count,
        "columns_list": [str(c) for c in df.columns],
        "column_types": column_types,
        "preview": preview_rows,
    }

    global active_dataset, active_df_cache, original_df_cache, processed_df_cache, dropped_columns, preprocessing_history_stack
    active_dataset = result_data
    active_df_cache = df
    original_df_cache = df.copy()
    processed_df_cache = df.copy()
    dropped_columns = set()
    import datetime
    now_time = datetime.datetime.now().strftime("%H:%M")
    preprocessing_history_stack = [{
        "op": "initial",
        "description": "Orijinal veri yüklendi",
        "time": now_time,
        "icon": "upload_file",
        "icon_bg": "bg-slate-gray/10",
        "icon_color": "text-slate-gray",
        "df": df.copy(),
        "dropped_cols": set()
    }]
    return JSONResponse(content=result_data)


@app.get("/api/session")
async def get_session():
    if not active_dataset:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aktif veri seti bulunamadı."
        )
    return JSONResponse(content=active_dataset)


@app.get("/api/active-dataset")
async def get_active_dataset():
    if not active_dataset:
        return JSONResponse(content={"active": False, "data": None})
    return JSONResponse(content={"active": True, "data": active_dataset})


@app.get("/api/search")
async def search_dataset(q: Optional[str] = None, limit: int = 10):
    global active_dataset, active_df_cache
    if active_df_cache is None or not active_dataset:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aktif veri seti bulunamadı."
        )

    df = active_df_cache
    total_rows = int(len(df))
    total_cols = int(len(df.columns))
    cols_list = [str(c) for c in df.columns]

    query_str = (q or "").strip()

    if not query_str:
        preview_df = df.head(limit)
        results = []
        for _, row in preview_df.iterrows():
            row_dict = {}
            for col in df.columns:
                row_dict[col] = clean_val_for_json(row[col])
            results.append(row_dict)

        return JSONResponse(content={
            "q": "",
            "total_matches": total_rows,
            "limit": limit,
            "rows": total_rows,
            "columns": total_cols,
            "results": results,
            "columns_list": cols_list
        })

    # Case-insensitive search across all columns
    query_lower = query_str.lower()
    mask = pd.Series(False, index=df.index)
    for col in df.columns:
        col_str = df[col].fillna("").astype(str).str.lower()
        mask = mask | col_str.str.contains(query_lower, regex=False, na=False)

    matched_df = df[mask]
    total_matches = int(len(matched_df))

    limited_df = matched_df.head(limit)
    results = []
    for _, row in limited_df.iterrows():
        row_dict = {}
        for col in df.columns:
            row_dict[col] = clean_val_for_json(row[col])
        results.append(row_dict)

    return JSONResponse(content={
        "q": query_str,
        "total_matches": total_matches,
        "limit": limit,
        "rows": total_rows,
        "columns": total_cols,
        "results": results,
        "columns_list": cols_list
    })


@app.get("/api/quality")
async def get_quality_report():
    global active_dataset, active_df_cache
    if not active_dataset:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Veri seti bulunamadı. Lütfen önce bir CSV dosyası yükleyin."
        )

    # If we have dataframe or cached data
    df = active_df_cache if active_df_cache is not None else None
    if df is None:
        # Construct fallback structure from active_dataset
        rows = active_dataset.get("rows", 0)
        cols = active_dataset.get("columns", 0)
        missing = active_dataset.get("missing", 0)
        duplicates = active_dataset.get("duplicates", 0)
        missing_rate = round((missing / max(1, rows * cols)) * 100, 2)
        duplicate_rate = round((duplicates / max(1, rows)) * 100, 2)
        score = max(0, 100 - int(missing_rate * 1.5) - int(duplicate_rate * 2))
        status_text = "iyi" if score >= 85 else ("iyilestirme_gerekli" if score >= 70 else "zayif")
        return JSONResponse(content={
            "filename": active_dataset.get("filename", "veri.csv"),
            "rows": rows,
            "columns": cols,
            "upload_time": active_dataset.get("upload_time", "Bugün"),
            "score": score,
            "score_status": status_text,
            "score_breakdown": [
                {"component": "Kayıp Veri", "formula": "Eksik oran × 1.5 (maks 30)", "value": f"%{missing_rate}", "penalty": min(30, int(missing_rate * 1.5))},
                {"component": "Tekrarlanan Kayıt", "formula": "Tekrar oranı × 2 (maks 20)", "value": f"%{duplicate_rate}", "penalty": min(20, int(duplicate_rate * 2))}
            ],
            "metrics": {
                "missing_rate": missing_rate,
                "duplicate_rate": duplicate_rate,
                "type_issues": 0,
                "constant_cols": 0,
                "high_cardinality_cols": 0,
                "outlier_summary": "Minimal"
            },
            "missing": {"total_missing": missing, "rate": missing_rate, "columns": []},
            "duplicates": {"count": duplicates, "rate": duplicate_rate, "samples": []},
            "cardinality": {"columns": []},
            "constant_cols": [],
            "outliers": {"columns": [], "total_outliers": 0, "overall_rate": 0.0, "method": "IQR"},
            "dtypes": []
        })

    rows_count = int(len(df))
    cols_count = int(len(df.columns))
    total_cells = max(1, rows_count * cols_count)
    total_missing = int(df.isna().sum().sum())
    missing_rate = round((total_missing / total_cells) * 100, 2)
    
    duplicate_count = int(df.duplicated().sum())
    duplicate_rate = round((duplicate_count / max(1, rows_count)) * 100, 2)
    
    # Duplicate samples
    duplicate_samples = []
    if duplicate_count > 0:
        dup_rows = df[df.duplicated(keep=False)].head(5)
        for _, r in dup_rows.iterrows():
            row_clean = {str(c): clean_val_for_json(r[c]) for c in df.columns}
            duplicate_samples.append(row_clean)

    # Missing by column
    missing_columns = []
    for col in df.columns:
        col_missing = int(df[col].isna().sum())
        if col_missing > 0:
            col_ratio = round((col_missing / max(1, rows_count)) * 100, 1)
            missing_columns.append({
                "name": str(col),
                "count": col_missing,
                "ratio": col_ratio
            })
    missing_columns.sort(key=lambda x: x["ratio"], reverse=True)

    # Constant columns
    constant_columns = []
    for col in df.columns:
        if df[col].nunique(dropna=False) == 1:
            first_val = clean_val_for_json(df[col].iloc[0]) if len(df) > 0 else "-"
            constant_columns.append({
                "name": str(col),
                "value": str(first_val),
                "ratio": 100.0
            })

    # Cardinality
    cardinality_columns = []
    high_card_count = 0
    for col in df.columns:
        unique_cnt = int(df[col].nunique(dropna=True))
        is_high = (unique_cnt / max(1, rows_count)) > 0.5
        label = "Yuksek" if is_high else "Dusuk"
        if is_high:
            high_card_count += 1
        cardinality_columns.append({
            "name": str(col),
            "unique": unique_cnt,
            "label": label,
            "is_high": is_high
        })

    # Outliers (IQR Method on numeric columns)
    numeric_df = df.select_dtypes(include=[np.number])
    outlier_columns = []
    total_outliers = 0
    for col in numeric_df.columns:
        valid_series = numeric_df[col].dropna()
        if len(valid_series) >= 4:
            q25 = float(valid_series.quantile(0.25))
            q75 = float(valid_series.quantile(0.75))
            iqr = q75 - q25
            if iqr > 0:
                lower = q25 - 1.5 * iqr
                upper = q75 + 1.5 * iqr
                outliers_cnt = int(((valid_series < lower) | (valid_series > upper)).sum())
                if outliers_cnt > 0:
                    total_outliers += outliers_cnt
                    outlier_columns.append({
                        "name": str(col),
                        "count": outliers_cnt,
                        "ratio": round((outliers_cnt / max(1, len(valid_series))) * 100, 2)
                    })
    outlier_columns.sort(key=lambda x: x["count"], reverse=True)
    outlier_rate = round((total_outliers / max(1, rows_count)) * 100, 2)
    has_significant_outlier = any(c["ratio"] > 1.0 for c in outlier_columns)
    outlier_summary = "Belirgin" if has_significant_outlier or total_outliers > 0 else "Minimal"

    # Data Types Check & Suggestions
    dtypes_list = []
    type_issues_count = 0
    for col in df.columns:
        curr_dtype = str(df[col].dtype)
        samples = [str(clean_val_for_json(v)) for v in df[col].dropna().head(2).tolist()]
        sample_str = ", ".join([f'"{s}"' if not s.replace('.', '', 1).isdigit() else s for s in samples])
        
        ok = True
        suggestion = "Uygun görünüyor"
        
        if df[col].dtype == object or str(df[col].dtype) == "string":
            non_na = df[col].dropna()
            if len(non_na) > 0:
                # 1. Check numeric conversion
                num_converted = pd.to_numeric(non_na, errors='coerce')
                valid_num_ratio = float(num_converted.notna().sum()) / len(non_na)
                if valid_num_ratio >= 0.8:
                    ok = False
                    suggestion = "Sayısal (int64) olabilir"
                    type_issues_count += 1
                else:
                    # 2. Check datetime conversion
                    try:
                        date_converted = pd.to_datetime(non_na, errors='coerce')
                        valid_date_ratio = float(date_converted.notna().sum()) / len(non_na)
                        if valid_date_ratio >= 0.8:
                            ok = False
                            suggestion = "Tarih (datetime) olabilir"
                            type_issues_count += 1
                        else:
                            suggestion = "Kategorik uygun görünüyor"
                            ok = True
                    except Exception:
                        suggestion = "Kategorik uygun görünüyor"
                        ok = True
        
        dtypes_list.append({
            "name": str(col),
            "current": curr_dtype,
            "samples": samples,
            "sample_str": sample_str,
            "suggestion": suggestion,
            "ok": ok
        })

    # Score and Penalties
    missing_penalty = min(30, int(round((total_missing / total_cells) * 50)))
    duplicate_penalty = min(10, int(round((duplicate_count / max(1, rows_count)) * 100)))
    type_penalty = min(15, type_issues_count * 4)
    constant_penalty = min(10, len(constant_columns) * 5)
    card_penalty = min(9, high_card_count * 3)
    outlier_penalty = min(10, int(round((total_outliers / max(1, rows_count)) * 40)))

    total_penalty = missing_penalty + duplicate_penalty + type_penalty + constant_penalty + card_penalty + outlier_penalty
    final_score = max(0, 100 - total_penalty)

    if final_score >= 85:
        score_status = "iyi_durumda"
    elif final_score >= 70:
        score_status = "iyilestirme_gerekli"
    else:
        score_status = "zayif"

    score_breakdown = [
        {"component": "Eksik değer", "formula": "oran × 50 (maks 30)", "value": f"%{missing_rate}", "penalty": missing_penalty},
        {"component": "Tekrarlanan kayıt", "formula": "oran × 100 (maks 10)", "value": f"%{duplicate_rate}", "penalty": duplicate_penalty},
        {"component": "Veri tipi sorunu", "formula": "sorunlu kolon × 4 (maks 15)", "value": f"{type_issues_count} Kolon", "penalty": type_penalty},
        {"component": "Sabit kolon", "formula": "sabit kolon × 5 (maks 10)", "value": f"{len(constant_columns)} Kolon", "penalty": constant_penalty},
        {"component": "Yüksek kardinalite", "formula": "kolon sayısı × 3 (maks 9)", "value": f"{high_card_count} Kolon", "penalty": card_penalty},
        {"component": "Aykırı değer", "formula": "oran × 40 (maks 10)", "value": f"%{outlier_rate}", "penalty": outlier_penalty}
    ]

    return JSONResponse(content={
        "filename": active_dataset.get("filename", "veri.csv"),
        "rows": rows_count,
        "columns": cols_count,
        "upload_time": active_dataset.get("upload_time", "14:32"),
        "score": final_score,
        "score_status": score_status,
        "score_breakdown": score_breakdown,
        "metrics": {
            "missing_rate": missing_rate,
            "duplicate_rate": duplicate_rate,
            "type_issues": type_issues_count,
            "constant_cols": len(constant_columns),
            "high_cardinality_cols": high_card_count,
            "outlier_summary": outlier_summary
        },
        "missing": {
            "total_missing": total_missing,
            "rate": missing_rate,
            "columns": missing_columns
        },
        "duplicates": {
            "count": duplicate_count,
            "rate": duplicate_rate,
            "samples": duplicate_samples
        },
        "cardinality": {
            "columns": cardinality_columns
        },
        "constant_cols": constant_columns,
        "outliers": {
            "columns": outlier_columns,
            "total_outliers": total_outliers,
            "overall_rate": outlier_rate,
            "method": "IQR"
        },
        "numeric_columns": [str(c) for c in df.select_dtypes(include=[np.number]).columns],
        "dtypes": dtypes_list
    })


def build_preprocessing_state_response():
    global active_dataset, original_df_cache, processed_df_cache, dropped_columns, preprocessing_history_stack
    if not active_dataset or original_df_cache is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Veri seti bulunamadı. Lütfen önce bir CSV dosyası yükleyin."
        )

    orig_df = original_df_cache
    proc_df = processed_df_cache if processed_df_cache is not None else orig_df

    active_cols = [c for c in proc_df.columns if c not in dropped_columns]
    
    total_missing_cells = int(proc_df[active_cols].isna().sum().sum()) if active_cols else 0
    columns_with_missing = []
    for c in active_cols:
        cnt = int(proc_df[c].isna().sum())
        if cnt > 0:
            columns_with_missing.append({"name": str(c), "count": cnt})

    duplicate_count = int(proc_df[active_cols].duplicated().sum()) if active_cols and len(proc_df) > 0 else 0

    schema = []
    for c in orig_df.columns:
        is_kept = (c not in dropped_columns) and (c in proc_df.columns)
        curr_series = proc_df[c] if c in proc_df.columns else orig_df[c]
        orig_series = orig_df[c]
        
        orig_type = str(orig_series.dtype)
        curr_type = str(curr_series.dtype)
        
        if pd.api.types.is_numeric_dtype(curr_series):
            kind = "numeric"
        elif pd.api.types.is_datetime64_any_dtype(curr_series):
            kind = "datetime"
        else:
            kind = "categorical"

        miss_cnt = int(curr_series.isna().sum())
        total_rows = max(1, len(proc_df))
        miss_ratio = round((miss_cnt / total_rows) * 100, 1)

        schema.append({
            "name": str(c),
            "current_type": curr_type,
            "original_type": orig_type,
            "missing_count": miss_cnt,
            "missing_ratio": miss_ratio,
            "kind": kind,
            "kept": is_kept
        })

    history_list = []
    for item in reversed(preprocessing_history_stack):
        history_list.append({
            "op": item.get("op", ""),
            "column": item.get("column", ""),
            "description": item.get("description", ""),
            "time": item.get("time", "10:00"),
            "icon": item.get("icon", "history"),
            "icon_bg": item.get("icon_bg", "bg-primary-container/20"),
            "icon_color": item.get("icon_color", "text-primary")
        })

    preview_df = proc_df[active_cols].head(10) if active_cols else pd.DataFrame()
    preview_rows = []
    for _, row in preview_df.iterrows():
        row_dict = {}
        for col in active_cols:
            row_dict[str(col)] = clean_val_for_json(row[col])
        preview_rows.append(row_dict)

    return {
        "filename": active_dataset.get("filename", "veri.csv"),
        "original": {
            "rows": int(len(orig_df)),
            "columns": int(len(orig_df.columns))
        },
        "processed": {
            "rows": int(len(proc_df)),
            "columns": int(len(active_cols)),
            "missing": total_missing_cells
        },
        "duplicates": duplicate_count,
        "missing_summary": {
            "total_missing_cells": total_missing_cells,
            "columns_with_missing": columns_with_missing
        },
        "schema": schema,
        "history": history_list,
        "preview": preview_rows,
        "columns_list": [str(c) for c in active_cols]
    }


@app.get("/api/preprocessing")
async def get_preprocessing_data():
    return JSONResponse(content=build_preprocessing_state_response())


@app.post("/api/preprocessing/apply")
async def apply_preprocessing_op(payload: Dict[str, Any]):
    global processed_df_cache, dropped_columns, preprocessing_history_stack
    if processed_df_cache is None or not active_dataset:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aktif veri seti bulunamadı."
        )

    import datetime
    now_time = datetime.datetime.now().strftime("%H:%M")
    
    op = payload.get("op")
    column = payload.get("column")
    method = payload.get("method")
    target_type = payload.get("target_type")

    # Snapshot before operation
    prev_state = {
        "op": op,
        "column": column,
        "df": processed_df_cache.copy(),
        "dropped_cols": set(dropped_columns)
    }

    active_cols_before = [c for c in processed_df_cache.columns if c not in dropped_columns]
    before_stats = {
        "rows": int(len(processed_df_cache)),
        "columns": int(len(active_cols_before)),
        "missing": int(processed_df_cache[active_cols_before].isna().sum().sum()) if active_cols_before else 0
    }

    try:
        desc = ""
        icon = "healing"
        icon_bg = "bg-primary-container/20"
        icon_color = "text-primary"

        if op == "fill_missing":
            cols_to_fill = [column] if column else [c for c in processed_df_cache.columns if c not in dropped_columns and processed_df_cache[c].isna().any()]
            for c in cols_to_fill:
                if c not in processed_df_cache.columns:
                    continue
                if method == "mean":
                    if pd.api.types.is_numeric_dtype(processed_df_cache[c]):
                        processed_df_cache[c] = processed_df_cache[c].fillna(processed_df_cache[c].mean())
                elif method == "median":
                    if pd.api.types.is_numeric_dtype(processed_df_cache[c]):
                        processed_df_cache[c] = processed_df_cache[c].fillna(processed_df_cache[c].median())
                elif method == "mode":
                    mode_vals = processed_df_cache[c].mode()
                    if len(mode_vals) > 0:
                        processed_df_cache[c] = processed_df_cache[c].fillna(mode_vals[0])
                elif method == "unknown":
                    processed_df_cache[c] = processed_df_cache[c].fillna("Unknown")
                elif method == "drop_rows":
                    processed_df_cache = processed_df_cache.dropna(subset=[c])

            method_names = {
                "mean": "ortalama (mean)",
                "median": "medyan (median)",
                "mode": "mod (en sık)",
                "unknown": "'Unknown'",
                "drop_rows": "satır silme"
            }
            method_tr = method_names.get(method, method)
            col_name = column if column else "Tüm eksik sütunlar"
            desc = f"Eksik veriler dolduruldu: {col_name} ({method_tr})"
            icon = "healing"
            icon_bg = "bg-primary-container/20"
            icon_color = "text-primary"

        elif op == "drop_duplicates":
            active_cols = [c for c in processed_df_cache.columns if c not in dropped_columns]
            dup_cnt = int(processed_df_cache[active_cols].duplicated().sum()) if active_cols else 0
            processed_df_cache = processed_df_cache.drop_duplicates(subset=active_cols if active_cols else None)
            desc = f"{dup_cnt} tekrarlayan satır kaldırıldı"
            icon = "delete"
            icon_bg = "bg-error-container"
            icon_color = "text-on-error-container"

        elif op == "drop_column":
            if column:
                dropped_columns.add(column)
                desc = f"Sütun kaldırıldı: {column}"
                icon = "visibility_off"
                icon_bg = "bg-surface-variant"
                icon_color = "text-on-surface-variant"

        elif op == "keep_column":
            if column in dropped_columns:
                dropped_columns.remove(column)
                desc = f"Sütun geri eklendi: {column}"
                icon = "visibility"
                icon_bg = "bg-secondary-container"
                icon_color = "text-on-secondary-container"

        elif op == "convert_type":
            if column and column in processed_df_cache.columns and target_type:
                old_t = str(processed_df_cache[column].dtype)
                if target_type == "int64":
                    processed_df_cache[column] = pd.to_numeric(processed_df_cache[column], errors="coerce").fillna(0).astype("int64")
                elif target_type == "float64":
                    processed_df_cache[column] = pd.to_numeric(processed_df_cache[column], errors="coerce").astype("float64")
                elif target_type == "datetime":
                    processed_df_cache[column] = pd.to_datetime(processed_df_cache[column], errors="coerce")
                elif target_type == "category":
                    processed_df_cache[column] = processed_df_cache[column].astype("category")
                elif target_type == "string":
                    processed_df_cache[column] = processed_df_cache[column].astype("string")
                
                desc = f"Tip dönüşümü: {column} ({old_t.upper()} → {target_type.upper()})"
                icon = "transform"
                icon_bg = "bg-secondary-container"
                icon_color = "text-on-secondary-container"
        else:
            raise ValueError(f"Geçersiz işlem: {op}")

        # Save history item
        history_entry = {
            "op": op,
            "column": column or "",
            "description": desc,
            "time": now_time,
            "icon": icon,
            "icon_bg": icon_bg,
            "icon_color": icon_color,
            "df": prev_state["df"],
            "dropped_cols": prev_state["dropped_cols"]
        }
        preprocessing_history_stack.append(history_entry)

    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"İşlem uygulanamadı: {str(err)}"
        )

    res = build_preprocessing_state_response()
    active_cols_after = [c for c in processed_df_cache.columns if c not in dropped_columns]
    after_stats = {
        "rows": int(len(processed_df_cache)),
        "columns": int(len(active_cols_after)),
        "missing": int(processed_df_cache[active_cols_after].isna().sum().sum()) if active_cols_after else 0
    }

    res["status"] = "success"
    res["operation"] = op
    res["before"] = before_stats
    res["after"] = after_stats
    return JSONResponse(content=res)


@app.post("/api/preprocessing/undo")
async def undo_preprocessing_op():
    global processed_df_cache, dropped_columns, preprocessing_history_stack
    if len(preprocessing_history_stack) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geri alınacak başka işlem bulunmuyor."
        )

    last_entry = preprocessing_history_stack.pop()
    processed_df_cache = last_entry["df"].copy()
    dropped_columns = set(last_entry["dropped_cols"])

    res = build_preprocessing_state_response()
    res["status"] = "success"
    return JSONResponse(content=res)


@app.post("/api/preprocessing/reset")
async def reset_preprocessing_ops():
    global original_df_cache, processed_df_cache, dropped_columns, preprocessing_history_stack
    if original_df_cache is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Veri seti bulunamadı."
        )

    processed_df_cache = original_df_cache.copy()
    dropped_columns = set()
    import datetime
    now_time = datetime.datetime.now().strftime("%H:%M")
    preprocessing_history_stack = [{
        "op": "initial",
        "description": "Orijinal veri yüklendi",
        "time": now_time,
        "icon": "upload_file",
        "icon_bg": "bg-slate-gray/10",
        "icon_color": "text-slate-gray",
        "df": original_df_cache.copy(),
        "dropped_cols": set()
    }]

    res = build_preprocessing_state_response()
    res["status"] = "success"
    return JSONResponse(content=res)


@app.get("/api/preprocessing/download")
async def download_cleaned_csv():
    global processed_df_cache, dropped_columns, active_dataset
    if processed_df_cache is None or not active_dataset:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="İndirilecek veri seti bulunamadı."
        )

    active_cols = [c for c in processed_df_cache.columns if c not in dropped_columns]
    download_df = processed_df_cache[active_cols]
    
    csv_bytes = download_df.to_csv(index=False, encoding="utf-8-sig")
    orig_name = active_dataset.get("filename", "veri.csv")
    cleaned_name = f"temizlenmis_{orig_name}"

    from fastapi.responses import Response
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{cleaned_name}"'}
    )


@app.get("/api/visualization/overview")
async def get_visualization_overview():
    global processed_df_cache, active_df_cache, original_df_cache, active_dataset, dropped_columns
    df = processed_df_cache if processed_df_cache is not None else (active_df_cache if active_df_cache is not None else original_df_cache)
    if df is None or not active_dataset:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Veri seti bulunamadı. Lütfen önce bir CSV dosyası yükleyin."
        )

    active_cols = [c for c in df.columns if c not in dropped_columns]
    curr_df = df[active_cols]

    numeric_cols = [c for c in active_cols if pd.api.types.is_numeric_dtype(curr_df[c])]
    categorical_cols = [c for c in active_cols if c not in numeric_cols]

    # Numeric stats
    stats_dict = {}
    for col in numeric_cols:
        series = curr_df[col].dropna()
        if len(series) > 0:
            stats_dict[str(col)] = {
                "count": int(len(series)),
                "mean": round(float(series.mean()), 2),
                "median": round(float(series.median()), 2),
                "std": round(float(series.std()), 2) if len(series) > 1 else 0.0,
                "min": round(float(series.min()), 2),
                "max": round(float(series.max()), 2)
            }
        else:
            stats_dict[str(col)] = {
                "count": 0, "mean": 0.0, "median": 0.0, "std": 0.0, "min": 0.0, "max": 0.0
            }

    # Categorical summary
    cat_summary = {}
    for col in categorical_cols:
        series = curr_df[col].dropna()
        total_non_na = max(1, len(series))
        val_counts = series.value_counts().head(10)
        items = []
        for val, cnt in val_counts.items():
            items.append({
                "value": str(val),
                "count": int(cnt),
                "ratio": round((cnt / total_non_na) * 100, 1)
            })
        cat_summary[str(col)] = items

    # Correlation
    corr_columns = [str(c) for c in numeric_cols]
    corr_matrix = []
    strongest_pairs = []

    if len(numeric_cols) > 0:
        corr_df = curr_df[numeric_cols].corr().fillna(0.0)
        for i, row_col in enumerate(numeric_cols):
            row_vals = []
            for j, col_col in enumerate(numeric_cols):
                val = round(float(corr_df.iloc[i, j]), 2)
                row_vals.append(val)
                if i < j:
                    strongest_pairs.append({
                        "a": str(row_col),
                        "b": str(col_col),
                        "corr": val,
                        "abs_corr": abs(val)
                    })
            corr_matrix.append(row_vals)
        strongest_pairs.sort(key=lambda x: x["abs_corr"], reverse=True)
        strongest_pairs = strongest_pairs[:5]

    # Suggestions
    suggestions = []
    # 1. Histogram for first numeric col
    if len(numeric_cols) > 0:
        col0 = numeric_cols[0]
        suggestions.append({
            "type": "histogram",
            "column": str(col0),
            "title": f"{col0} Dağılımı",
            "reason": "Sayısal Dağılım"
        })

    # 2. Bar for first categorical col
    if len(categorical_cols) > 0:
        cat0 = categorical_cols[0]
        suggestions.append({
            "type": "bar",
            "column": str(cat0),
            "title": f"{cat0} Kategorileri",
            "reason": "Kategori Sayıları"
        })

    # 3. Scatter for strongest correlation pair or 2 numeric cols
    if len(strongest_pairs) > 0:
        p0 = strongest_pairs[0]
        suggestions.append({
            "type": "scatter",
            "x": p0["a"],
            "y": p0["b"],
            "title": f"{p0['a']} × {p0['b']}",
            "reason": f"En Güçlü Korelasyon (r = {p0['corr']})"
        })
    elif len(numeric_cols) >= 2:
        suggestions.append({
            "type": "scatter",
            "x": str(numeric_cols[0]),
            "y": str(numeric_cols[1]),
            "title": f"{numeric_cols[0]} × {numeric_cols[1]}",
            "reason": "İki Değişkenli İlişki"
        })

    # 4. Grouped boxplot if we have cat and num
    if len(categorical_cols) > 0 and len(numeric_cols) > 0:
        suggestions.append({
            "type": "grouped_boxplot",
            "cat": str(categorical_cols[0]),
            "num": str(numeric_cols[0]),
            "title": f"{categorical_cols[0]}'a Göre {numeric_cols[0]}",
            "reason": "Kategori Bazlı Dağılım"
        })

    # 5. Boxplot for second or first numeric col
    if len(numeric_cols) > 1:
        col1 = numeric_cols[1]
        suggestions.append({
            "type": "boxplot",
            "column": str(col1),
            "title": f"{col1} Kutu Grafiği",
            "reason": "Uç Değer ve Çeyreklikler"
        })
    elif len(numeric_cols) == 1:
        suggestions.append({
            "type": "boxplot",
            "column": str(numeric_cols[0]),
            "title": f"{numeric_cols[0]} Kutu Grafiği",
            "reason": "Uç Değer ve Çeyreklikler"
        })

    return JSONResponse(content={
        "numeric_columns": [str(c) for c in numeric_cols],
        "categorical_columns": [str(c) for c in categorical_cols],
        "stats": stats_dict,
        "categorical_summary": cat_summary,
        "correlation": {
            "columns": corr_columns,
            "matrix": corr_matrix,
            "strongest": strongest_pairs
        },
        "suggestions": suggestions
    })


@app.get("/api/visualization/focus")
async def get_visualization_focus(column: str):
    global processed_df_cache, active_df_cache, original_df_cache, active_dataset, dropped_columns
    df = processed_df_cache if processed_df_cache is not None else (active_df_cache if active_df_cache is not None else original_df_cache)
    if df is None or not active_dataset:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Veri seti bulunamadı. Lütfen önce bir CSV dosyası yükleyin."
        )

    active_cols = [c for c in df.columns if c not in dropped_columns]
    curr_df = df[active_cols]
    if column not in curr_df.columns:
        raise HTTPException(status_code=400, detail="Geçersiz odak değişkeni.")

    numeric_cols = [c for c in active_cols if pd.api.types.is_numeric_dtype(curr_df[c])]
    categorical_cols = [c for c in active_cols if c not in numeric_cols]
    is_numeric = column in numeric_cols

    suggestions = []
    univariate = None
    note = None

    if is_numeric:
        # --- Galeri: odak merkezli ---
        # 1. Histogram (odak sütunu)
        suggestions.append({
            "type": "histogram",
            "column": str(column),
            "title": f"{column} Dağılımı",
            "reason": "Sayısal Dağılım (Odak)"
        })
        # 2. Diğer sayısal sütunlarla scatter (max 3)
        others = [c for c in numeric_cols if c != column]
        for other in others[:3]:
            suggestions.append({
                "type": "scatter",
                "x": str(column),
                "y": str(other),
                "title": f"{column} × {other}",
                "reason": "Odak Değişkeni İlişkisi"
            })
        # 3. Boxplot (odak sütunu)
        suggestions.append({
            "type": "boxplot",
            "column": str(column),
            "title": f"{column} Kutu Grafiği",
            "reason": "Uç Değer ve Çeyreklikler"
        })

        # --- Univariate: istatistikler + histogram + boxplot ---
        series = pd.to_numeric(curr_df[column], errors="coerce").dropna()
        stats = {}
        if len(series) > 0:
            stats = {
                "count": int(len(series)),
                "mean": round(float(series.mean()), 2),
                "median": round(float(series.median()), 2),
                "std": round(float(series.std()), 2) if len(series) > 1 else 0.0,
                "min": round(float(series.min()), 2),
                "max": round(float(series.max()), 2)
            }
        else:
            stats = {"count": 0, "mean": 0.0, "median": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}

        histogram = None
        if len(series) > 0:
            counts, bin_edges = np.histogram(series, bins=min(15, max(5, int(np.sqrt(len(series))))))
            histogram = {
                "bins": [round(float(b), 2) for b in bin_edges],
                "bin_labels": [f"{bin_edges[i]:.1f} - {bin_edges[i+1]:.1f}" for i in range(len(counts))],
                "counts": [int(c) for c in counts]
            }
        else:
            histogram = {"bins": [0, 1], "bin_labels": ["0 - 1"], "counts": [0]}

        boxplot = {"box": [0, 0, 0, 0, 0], "outliers": []}
        if len(series) > 0:
            q1 = float(series.quantile(0.25))
            med = float(series.median())
            q3 = float(series.quantile(0.75))
            iqr = q3 - q1
            low_bound = q1 - 1.5 * iqr
            high_bound = q3 + 1.5 * iqr
            non_outliers = series[(series >= low_bound) & (series <= high_bound)]
            outliers = [round(float(v), 2) for v in series[(series < low_bound) | (series > high_bound)].tolist()]
            boxplot = {
                "box": [
                    round(float(non_outliers.min()), 2) if len(non_outliers) > 0 else round(float(series.min()), 2),
                    round(q1, 2), round(med, 2), round(q3, 2),
                    round(float(non_outliers.max()), 2) if len(non_outliers) > 0 else round(float(series.max()), 2)
                ],
                "outliers": outliers[:100]
            }

        univariate = {
            "is_numeric": True,
            "stats": stats,
            "histogram": histogram,
            "boxplot": boxplot
        }

    else:
        # --- Kategorik odak: bar + grouped boxplot + not ---
        # 1. Bar (odak sütunu)
        suggestions.append({
            "type": "bar",
            "column": str(column),
            "title": f"{column} Kategorileri",
            "reason": "Kategori Sayıları (Odak)"
        })
        # 2. Kategorilere göre sayısal dağılım (max 3 sayısal sütun)
        for num in numeric_cols[:3]:
            suggestions.append({
                "type": "grouped_boxplot",
                "cat": str(column),
                "num": str(num),
                "title": f"{column}'a Göre {num}",
                "reason": "Kategori Bazlı Dağılım"
            })

        # Bar verisi
        series = curr_df[column].dropna()
        total_cnt = max(1, len(series))
        val_counts = series.value_counts().head(15)
        items = []
        for val, count in val_counts.items():
            items.append({
                "value": str(val),
                "count": int(count),
                "ratio": round((count / total_cnt) * 100, 1)
            })
        univariate = {"is_numeric": False, "bar": {"items": items}}

        note = (f"'{column}' kategorik bir değişkendir; histogram/boxplot yerine kategori "
                f"sayıları (bar) ve kategorilere göre sayısal dağılım (kutu grafiği) gösterilmektedir. "
                f"Korelasyon yalnızca sayısal değişkenler arasında hesaplanır.")

    # --- Korelasyon: heatmap tüm matris + liste odak sütununa göre ---
    corr_matrix = []
    strongest = []
    corr_cols = [str(c) for c in numeric_cols]
    if len(numeric_cols) >= 2:
        corr_df = curr_df[[c for c in numeric_cols]]
        corr_np = corr_df.corr()
        corr_matrix = [[round(float(v), 2) for v in row] for row in corr_np.values.tolist()]

        if is_numeric and column in corr_cols:
            # Odak sütununun diğerleriyle korelasyonu (liste odaklı)
            col_row = corr_np[column].drop(labels=[column])
            sorted_pairs = col_row.abs().sort_values(ascending=False)
            for other, r in sorted_pairs.head(5).items():
                strongest.append({"a": str(column), "b": str(other), "corr": round(float(r), 2)})
        else:
            # Tüm çiftler arasında en güçlü
            pairs = []
            n = len(corr_cols)
            for i in range(n):
                for j in range(i + 1, n):
                    v = float(corr_np.iloc[i, j])
                    if not np.isnan(v):
                        pairs.append((abs(v), corr_cols[i], corr_cols[j], v))
            pairs.sort(key=lambda x: x[0], reverse=True)
            for _, a, b, v in pairs[:5]:
                strongest.append({"a": a, "b": b, "corr": round(v, 2)})
    else:
        corr_matrix = []

    return JSONResponse(content={
        "column": str(column),
        "is_numeric": is_numeric,
        "suggestions": suggestions,
        "univariate": univariate,
        "correlation": {"columns": corr_cols, "matrix": corr_matrix, "strongest": strongest},
        "note": note
    })


@app.get("/api/visualization/chart")
async def get_visualization_chart(
    type: str,
    column: Optional[str] = None,
    x: Optional[str] = None,
    y: Optional[str] = None,
    cat: Optional[str] = None,
    num: Optional[str] = None
):
    global processed_df_cache, active_df_cache, original_df_cache, active_dataset, dropped_columns
    df = processed_df_cache if processed_df_cache is not None else (active_df_cache if active_df_cache is not None else original_df_cache)
    if df is None or not active_dataset:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Veri seti bulunamadı."
        )

    active_cols = [c for c in df.columns if c not in dropped_columns]
    curr_df = df[active_cols]

    if type == "histogram":
        col_name = column or x or num
        if not col_name or col_name not in curr_df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz histogram kolonu.")
        
        series = pd.to_numeric(curr_df[col_name], errors="coerce").dropna()
        if len(series) == 0:
            return JSONResponse(content={"bins": [0, 1], "bin_labels": ["0 - 1"], "counts": [0]})

        counts, bin_edges = np.histogram(series, bins=min(15, max(5, int(np.sqrt(len(series))))))
        bin_labels = [f"{bin_edges[i]:.1f} - {bin_edges[i+1]:.1f}" for i in range(len(counts))]
        return JSONResponse(content={
            "bins": [round(float(b), 2) for b in bin_edges],
            "bin_labels": bin_labels,
            "counts": [int(c) for c in counts]
        })

    elif type == "boxplot":
        col_name = column or x or num
        if not col_name or col_name not in curr_df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz boxplot kolonu.")
        
        series = pd.to_numeric(curr_df[col_name], errors="coerce").dropna()
        if len(series) == 0:
            return JSONResponse(content={"box": [0, 0, 0, 0, 0], "outliers": []})

        q1 = float(series.quantile(0.25))
        med = float(series.median())
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1
        low_bound = q1 - 1.5 * iqr
        high_bound = q3 + 1.5 * iqr

        non_outliers = series[(series >= low_bound) & (series <= high_bound)]
        whisker_min = float(non_outliers.min()) if len(non_outliers) > 0 else float(series.min())
        whisker_max = float(non_outliers.max()) if len(non_outliers) > 0 else float(series.max())
        outliers = [round(float(v), 2) for v in series[(series < low_bound) | (series > high_bound)].tolist()]

        return JSONResponse(content={
            "box": [round(whisker_min, 2), round(q1, 2), round(med, 2), round(q3, 2), round(whisker_max, 2)],
            "outliers": outliers[:100],
            "q1": round(q1, 2),
            "q3": round(q3, 2),
            "iqr": round(iqr, 2),
            "lower_bound": round(low_bound, 2),
            "upper_bound": round(high_bound, 2),
            "outlier_count": len(outliers),
            "total": int(len(series))
        })

    elif type == "bar":
        col_name = column or x or cat
        if not col_name or col_name not in curr_df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz bar kolonu.")
        
        series = curr_df[col_name].dropna()
        total_cnt = max(1, len(series))
        val_counts = series.value_counts().head(15)
        items = []
        for val, count in val_counts.items():
            items.append({
                "value": str(val),
                "count": int(count),
                "ratio": round((count / total_cnt) * 100, 1)
            })
        return JSONResponse(content={"items": items})

    elif type == "scatter":
        x_col = x or column
        y_col = y
        if not x_col or not y_col or x_col not in curr_df.columns or y_col not in curr_df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz scatter kolonları.")

        scatter_df = curr_df[[x_col, y_col]].dropna()
        if len(scatter_df) > 1000:
            scatter_df = scatter_df.sample(1000, random_state=42)

        x_vals = [round(float(v), 2) if isinstance(v, (int, float, np.number)) else str(v) for v in scatter_df[x_col].tolist()]
        y_vals = [round(float(v), 2) if isinstance(v, (int, float, np.number)) else str(v) for v in scatter_df[y_col].tolist()]

        return JSONResponse(content={
            "x_name": str(x_col),
            "y_name": str(y_col),
            "x": x_vals,
            "y": y_vals
        })

    elif type == "grouped_boxplot":
        cat_col = cat or x
        num_col = num or y or column
        if not cat_col or not num_col or cat_col not in curr_df.columns or num_col not in curr_df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz grouped boxplot kolonları.")

        sub_df = curr_df[[cat_col, num_col]].dropna()
        top_cats = sub_df[cat_col].value_counts().head(6).index.tolist()

        groups = []
        for c_val in top_cats:
            cat_series = pd.to_numeric(sub_df[sub_df[cat_col] == c_val][num_col], errors="coerce").dropna()
            if len(cat_series) == 0:
                continue

            q1 = float(cat_series.quantile(0.25))
            med = float(cat_series.median())
            q3 = float(cat_series.quantile(0.75))
            iqr = q3 - q1
            low_b = q1 - 1.5 * iqr
            high_b = q3 + 1.5 * iqr

            non_outliers = cat_series[(cat_series >= low_b) & (cat_series <= high_b)]
            w_min = float(non_outliers.min()) if len(non_outliers) > 0 else float(cat_series.min())
            w_max = float(non_outliers.max()) if len(non_outliers) > 0 else float(cat_series.max())
            outliers = [round(float(v), 2) for v in cat_series[(cat_series < low_b) | (cat_series > high_b)].tolist()]

            groups.append({
                "name": str(c_val),
                "box": [round(w_min, 2), round(q1, 2), round(med, 2), round(q3, 2), round(w_max, 2)],
                "outliers": outliers[:50]
            })

        return JSONResponse(content={
            "cat": str(cat_col),
            "num": str(num_col),
            "groups": groups
        })

    else:
        raise HTTPException(status_code=400, detail=f"Desteklenmeyen grafik tipi: {type}")


def build_ai_context(page: str) -> dict:
    global processed_df_cache, active_df_cache, active_dataset, dropped_columns
    df = processed_df_cache if processed_df_cache is not None else (active_df_cache if active_df_cache is not None else None)
    active_cols = [c for c in df.columns if c not in dropped_columns] if df is not None else []
    context = {
        "page": page,
        "dataset_loaded": df is not None,
        "dataset": None,
    }
    if df is not None:
        try:
            sub = df[active_cols]
            dtypes = {str(c): str(sub[c].dtype) for c in active_cols}
            missing = {str(c): int(sub[c].isna().sum()) for c in active_cols if sub[c].isna().sum() > 0}

            # İlk 3 satır önizleme (okunaklı ve JSON uyumlu)
            preview_serializable = []
            for _, r in sub.head(3).iterrows():
                row_vals = []
                for c in active_cols:
                    val = r[c]
                    if pd.isna(val) or val is None:
                        row_vals.append(None)
                    elif isinstance(val, (float, np.floating)):
                        row_vals.append(None if (np.isnan(val) or np.isinf(val)) else round(float(val), 4))
                    elif isinstance(val, (int, np.integer)):
                        row_vals.append(int(val))
                    else:
                        row_vals.append(str(val))
                preview_serializable.append(row_vals)

            # Korelasyon özeti: en güçlü 10 çift (sayısal sütunlar)
            corr_pairs = []
            numeric = sub.select_dtypes(include=["number"])
            if numeric.shape[1] >= 2 and len(numeric) >= 2:
                corr = numeric.corr()
                for i, c1 in enumerate(corr.columns):
                    for c2 in corr.columns[i + 1:]:
                        v = corr.loc[c1, c2]
                        if pd.notna(v) and not np.isnan(v) and not np.isinf(v):
                            corr_pairs.append((str(c1), str(c2), round(float(v), 3)))
                corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
                corr_pairs = corr_pairs[:10]

            context["dataset"] = {
                "filename": active_dataset.get("filename", "bilinmiyor"),
                "rows": int(len(df)),
                "columns": [str(c) for c in active_cols],
                "col_count": len(active_cols),
                "dtypes": dtypes,
                "missing_counts": missing,
                "preview_first_3_rows": {
                    "columns": [str(c) for c in active_cols],
                    "rows": preview_serializable
                },
                "top_correlations": corr_pairs,
            }
        except Exception as e:
            print("[AI] Veri bağlamı oluşturulamadı:", e)
            context["dataset"] = {
                "filename": active_dataset.get("filename", "bilinmiyor"),
                "rows": int(len(df)),
                "columns": [str(c) for c in active_cols],
                "col_count": len(active_cols),
            }
    return context


def rule_based_reply(question: str, context: dict) -> str:
    q = question.lower()
    ds = context.get("dataset")

    if not context.get("dataset_loaded") or ds is None:
        return ("Henüz bir veri seti yüklenmemiş. 'Yeni Veri Yükle' butonundan bir CSV dosyası "
                "yükleyin; ardından veri kalitesi, görselleştirme ve model analizi sorularınızı yanıtlayabilirim.")

    rows, cols = ds["rows"], ds["col_count"]

    if "kalite" in q or "özet" in q or "quality" in q:
        return (f"Şu an '{ds['filename']}' veri seti yüklü ({rows} satır, {cols} sütun). "
                "Veri kalitesi detayları için Data Quality sayfasını inceleyebilirsiniz; "
                "kalite skoru ve eksik veri oranları orada listelenir.")
    if "değişken" in q or "önemli" in q or "sütun" in q or "variable" in q:
        col_sample = ', '.join(ds['columns'][:12])
        return (f"Veri setinde şu sütunlar var: {col_sample}"
                + (" ..." if cols > 12 else "")
                + ". En önemli değişkenleri belirlemek için Visualization sayfasındaki korelasyon "
                  "matrisi ve model metriklerine bakabilirsiniz.")
    if "aykırı" in q or "outlier" in q:
        return "Aykırı değer analizi için Data Quality sayfasındaki 'Aykırı Değer Analizi (IQR)' bölümüne ve Visualization'daki kutu grafiklerine bakabilirsiniz."
    if "model" in q or "başarı" in q or "f1" in q or "accuracy" in q:
        return ("Model sonuçları için Portfolio sayfasındaki 'Model Sonuçları (AI4I 2020)' tablosuna "
                "bakabilirsiniz. En iyi performans Random Forest modelinde görülmektedir.")
    if "sayfa" in q or "nerede" in q:
        return f"Şu an '{context.get('page')}' sayfasındasınız. Veri kalitesi için Data Quality, ön işleme için Preprocessing, grafikler için Visualization sekmelerini kullanabilirsiniz."
    return (f"Bu soruya veri bağlamından kural tabanlı yanıt verebildim: şu an '{ds['filename']}' "
            f"yüklü ({rows} satır, {cols} sütun). Daha akıllı yanıtlar için Ayarlar sayfasından Gemini API anahtarı girebilirsiniz.")


@app.post("/api/ai-assistant/settings")
async def set_ai_settings(payload: dict):
    global user_gemini_api_key
    key = (payload.get("apiKey") or "").strip()
    if key:
        user_gemini_api_key = key
        return JSONResponse(content={"ok": True, "message": "Gemini API anahtarı kaydedildi."})
    return JSONResponse(status_code=400, content={"ok": False, "message": "API anahtarı boş olamaz."})


@app.get("/api/ai-assistant/settings")
async def get_ai_settings():
    global user_gemini_api_key
    has_key = bool(user_gemini_api_key)
    masked_key = ""
    if has_key:
        masked_key = user_gemini_api_key[:4] + "..." + user_gemini_api_key[-4:] if len(user_gemini_api_key) > 8 else "***"
    return JSONResponse(content={"has_key": has_key, "masked_key": masked_key})


@app.post("/api/ai-assistant/chat")
async def ai_assistant_chat(payload: dict):
    global user_gemini_api_key
    question = (payload.get("message") or "").strip()
    page = (payload.get("page") or "index.html").strip()
    session_id = (payload.get("session_id") or "").strip() or uuid.uuid4().hex
    if not question:
        raise HTTPException(status_code=400, detail="Soru boş olamaz.")

    context = build_ai_context(page)

    # Anahtar çözümleme: istekle gelen api_key önceliklidir, yoksa global kullanılır.
    request_api_key = (payload.get("api_key") or "").strip()
    api_key = request_api_key or user_gemini_api_key

    if not api_key:
        fallback_reply = rule_based_reply(question, context)
        fallback_history = _ai_sessions.get(session_id, [])
        fallback_history.append({"role": "user", "content": question})
        fallback_history.append({"role": "assistant", "content": fallback_reply})
        _ai_sessions[session_id] = fallback_history[-_MAX_HISTORY_TURNS * 2:]
        return JSONResponse(content={
            "reply": fallback_reply,
            "source": "fallback",
            "context": context,
            "session_id": session_id,
        })

    # Sistem rolü (prompt): genel danışman kimliği + dinamik veri bağlamı
    system_prompt = (
        "Sen trex DataLab platformunun kıdemli Veri Bilimi ve İstatistik uzmanı yapay zeka asistanısın. "
        "Kullanıcının soracağı genel istatistik, makine öğrenmesi, kodlama veya günlük her türlü soruya "
        "Türkçe, son derece akıllı, eğitici, samimi ve detaylı yanıtlar verirsin.\n\n"
        "Aşağıda kullanıcının şu an yüklediği veri setinin özeti ve aktif sayfa bilgisi var. "
        "Veriyle ilgili sorularda bu bağlamı doğrudan kullan (sütun adlarına göre cevap ver, örneğin "
        "'Regionname ne anlama gelir?' gibi sorularda gerçek sütun değerlerine atıfta bulun). "
        "Veri dışı veya genel bir soru sorulduğunda kendi geniş bilgi dağarcığınla eksiksiz yanıtla. "
        "Veri seti yüklü değilse, kullanıcıya önce 'Yeni Veri Yükle' ile CSV yüklemesi gerektiğini söyle.\n\n"
        + json.dumps(context, ensure_ascii=False, default=str)
    )

    # --- Gemini (google-generativeai SDK) ---
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.4,
                max_output_tokens=800,
            ),
        )

        history = _ai_sessions.get(session_id, [])
        gemini_history = []
        for turn in history[-_MAX_HISTORY_TURNS:]:
            gemini_history.append({
                "role": "user" if turn["role"] == "user" else "model",
                "parts": [turn["content"]],
            })

        chat = model.start_chat(history=gemini_history)
        response = chat.send_message(question)
        reply = (response.text or "").strip() or "Yanıt üretilemedi."

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": reply})
        _ai_sessions[session_id] = history[-_MAX_HISTORY_TURNS * 2:]

        return JSONResponse(content={
            "reply": reply,
            "source": "gemini",
            "context": context,
            "session_id": session_id,
        })
    except Exception as e:
        error_msg = f"Gemini API hatası: {str(e)}"
        print("[AI]", error_msg)
        # Kural tabanlıya sessizce düşme; gerçek hata kullanıcıya gösterilir.
        return JSONResponse(content={
            "reply": error_msg,
            "source": "error",
            "context": context,
            "session_id": session_id,
        })


@app.post("/api/ai-assistant/reset")
async def reset_ai_session(payload: dict):
    session_id = (payload.get("session_id") or "").strip()
    if session_id and session_id in _ai_sessions:
        _ai_sessions.pop(session_id, None)
    return JSONResponse(content={"ok": True})


@app.post("/api/reset")
@app.delete("/api/reset")
async def reset_dataset():
    global active_dataset, active_df_cache, original_df_cache, processed_df_cache, dropped_columns, preprocessing_history_stack
    active_dataset = {}
    active_df_cache = None
    original_df_cache = None
    processed_df_cache = None
    dropped_columns = set()
    preprocessing_history_stack = []
    return JSONResponse(content={"status": "success", "message": "Veri seti sıfırlandı."})


if os.path.exists("portfolio/grafikler"):
    app.mount("/portfolio/grafikler", StaticFiles(directory="portfolio/grafikler"), name="portfolio_grafikler")

if os.path.exists("components"):
    app.mount("/components", StaticFiles(directory="components"), name="components")

app.mount("/static", StaticFiles(directory="static"), name="static")
