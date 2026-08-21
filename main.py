import io
import os
import csv
import json
import uuid
import re
import warnings
import traceback
import requests
import google.generativeai as genai
from typing import Dict, Any, Optional, Tuple
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold, KFold, TimeSeriesSplit
from sklearn.preprocessing import LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    r2_score, mean_absolute_error, mean_squared_error, confusion_matrix, roc_curve
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
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

ENCODINGS = ["utf-8-sig", "utf-8", "cp1254", "latin5", "iso-8859-9", "cp1252", "latin-1", "utf-16"]
DELIMITERS = [",", ";", "\t", "|"]


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


def _make_report(enc: str, sep, skipped: list) -> dict:
    return {
        "encoding": enc,
        "delimiter": ("auto" if sep is None else sep),
        "skipped_count": len(skipped),
        "skipped_lines": skipped[:20],
    }


def _short(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    return text[:300]


def parse_csv_content(content_bytes: bytes, filename: str) -> Tuple[pd.DataFrame, dict]:
    last_error: Optional[Exception] = None
    diagnostics: list = []

    # UTF-16 BOM tespiti
    if content_bytes.startswith(b"\xff\xfe") or content_bytes.startswith(b"\xfe\xff"):
        enc_list = ["utf-16", "utf-16-le", "utf-16-be"] + [e for e in ENCODINGS if not e.startswith("utf-16")]
    else:
        enc_list = ENCODINGS

    def _looks_merged(df: pd.DataFrame) -> bool:
        if len(df.columns) != 1:
            return False
        col_name = str(df.columns[0])
        if "," in col_name or ";" in col_name or "\t" in col_name or "|" in col_name:
            return True
        if len(df) == 0:
            return False
        sample_vals = df.iloc[:, 0].astype(str).head(20)
        for v in sample_vals:
            if "," in v or ";" in v or "\t" in v or "|" in v:
                return True
        return False

    def _read(enc: str, sep):
        # on_bad_lines="warn" → bozuk satırlar atlanır, ParserWarning mesajları toplanır
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            df = pd.read_csv(
                io.BytesIO(content_bytes),
                encoding=enc,
                sep=sep,
                engine="python",   # C motoru yerine her yerde python (cryptic 'bad delimiter value' vb. hataları önler)
                on_bad_lines="warn",
            )
        skipped_lines = []
        for w in caught:
            if isinstance(w.message, pd.errors.ParserWarning):
                m = re.search(r"line (\d+)", str(w.message))
                if m:
                    skipped_lines.append(int(m.group(1)))

        # Sütun isimlerini stringe çevir ve temizle
        seen = {}
        new_cols = []
        for c in df.columns:
            c_str = str(c).strip() if c is not None else ""
            if not c_str:
                c_str = "unnamed"
            if c_str in seen:
                seen[c_str] += 1
                new_cols.append(f"{c_str}_{seen[c_str]}")
            else:
                seen[c_str] = 0
                new_cols.append(c_str)
        df.columns = new_cols

        return df, sorted(set(skipped_lines))

    # --- Faz 1: otomatik ayraç algılama (sep=None + engine="python", csv.Sniffer) ---
    for enc in enc_list:
        try:
            detected_sep = None
            sample_text = content_bytes[:8192].decode(enc, errors="ignore")
            try:
                detected_sep = csv.Sniffer().sniff(sample_text, delimiters="".join(DELIMITERS)).delimiter
            except Exception:
                pass

            if detected_sep is not None:
                df, skipped = _read(enc, detected_sep)
                if not _looks_merged(df) and len(df.columns) >= 2:
                    return df, _make_report(enc, detected_sep, skipped)
            elif any(d in sample_text for d in DELIMITERS):
                df, skipped = _read(enc, None)
                if not _looks_merged(df) and len(df.columns) >= 2:
                    return df, _make_report(enc, None, skipped)
        except Exception as e:
            last_error = e
            diagnostics.append(f"kodlama={enc}, ayraç=auto → {_short(e)}")
            continue

    # --- Faz 2: sabit ayraç denemesi (sırasıyla , ; \t |) x tüm kodlamalar ---
    for enc in enc_list:
        for sep in DELIMITERS:
            try:
                df, skipped = _read(enc, sep)
                if not _looks_merged(df) and len(df.columns) >= 2:
                    return df, _make_report(enc, sep, skipped)
            except Exception as e:
                last_error = e
                diagnostics.append(f"kodlama={enc}, ayraç={sep} → {_short(e)}")
                continue

    # --- Faz 3: tek-sütun kabul (son çare; hiçbir ayraç çalışmadıysa) ---
    for enc in enc_list:
        for sep_cand in [",", None]:
            try:
                df, skipped = _read(enc, sep_cand)
                if len(df.columns) == 1 and not _looks_merged(df) and len(df) > 0:
                    return df, _make_report(enc, None, skipped)
            except Exception as e:
                last_error = e
                continue

    # --- Toplu hata mesajı: satır bilgisi + denenen listeler ---
    detail = (
        "Dosya okunamadı. Denenen kodlamalar: "
        + ", ".join(enc_list)
        + " | Denenen ayraçlar: "
        + ", ".join([("\\t" if d == "\t" else d) for d in DELIMITERS])
    )
    if last_error is not None:
        detail += " | Son hata: " + _short(last_error)
    if diagnostics:
        detail += " | Ayrıntı: " + " ; ".join(diagnostics[-5:])
    raise ValueError(detail)


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


@app.get("/machine-learning")
@app.get("/machine-learning.html")
async def serve_machine_learning():
    return FileResponse("static/machine-learning.html")


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
        df, parse_report = parse_csv_content(content, file.filename)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV dosyası işlenirken hata oluştu: {str(err)}"
        )

    rows_count = int(len(df))
    cols_count = int(len(df.columns))
    missing_count = int(df.isna().sum().sum())
    try:
        duplicates_count = int(df.duplicated().sum())
    except Exception:
        duplicates_count = 0

    numeric_df = df.select_dtypes(include=[np.number])
    numeric_cols_count = int(len(numeric_df.columns))
    categorical_cols_count = int(cols_count - numeric_cols_count)

    column_types = {}
    for col in df.columns:
        if col in numeric_df.columns:
            column_types[str(col)] = "numeric"
        else:
            column_types[str(col)] = "categorical"

    preview_df = df.head(10)
    preview_rows = []
    for _, row in preview_df.iterrows():
        row_dict = {}
        for i, col in enumerate(df.columns):
            row_dict[str(col)] = clean_val_for_json(row.iloc[i])
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
        "parse_report": parse_report if parse_report.get("skipped_count", 0) > 0 else None,
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


def _compute_quality_report(df: pd.DataFrame, baseline_rows: int) -> dict:
    rows_count = int(len(df))
    cols_count = int(len(df.columns))
    total_cells = max(1, rows_count * cols_count)
    total_missing = int(df.isna().sum().sum())
    missing_rate = round((total_missing / total_cells) * 100, 2)
    
    duplicate_count = int(df.duplicated().sum()) if rows_count > 0 else 0
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

    # Cardinality (Denominator fixed to baseline_rows)
    cardinality_columns = []
    high_card_count = 0
    for col in df.columns:
        unique_cnt = int(df[col].nunique(dropna=True))
        is_high = (unique_cnt / max(1, baseline_rows)) > 0.5
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

    return {
        "rows": rows_count,
        "columns": cols_count,
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
    }


@app.get("/api/quality")
async def get_quality_report():
    global active_dataset, active_df_cache, original_df_cache, processed_df_cache, dropped_columns
    if not active_dataset:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Veri seti bulunamadı. Lütfen önce bir CSV dosyası yükleyin."
        )

    # If we have dataframe or cached data
    df_raw = original_df_cache if original_df_cache is not None else active_df_cache
    df_proc = processed_df_cache if processed_df_cache is not None else active_df_cache

    if df_raw is None and df_proc is None:
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
            "numeric_columns": [],
            "dtypes": [],
            "comparison": {
                "raw_score": score,
                "processed_score": score,
                "delta": 0,
                "raw_rows": rows,
                "processed_rows": rows
            }
        })

    baseline_rows = int(len(df_raw)) if df_raw is not None else (int(len(df_proc)) if df_proc is not None else 0)

    # İşlenmiş rapor: mantıksal olarak kaldırılmış kolonlar hariç
    if dropped_columns and df_proc is not None:
        active_cols = [c for c in df_proc.columns if c not in dropped_columns]
        df_proc_active = df_proc[active_cols]
    else:
        df_proc_active = df_proc

    raw_report = _compute_quality_report(df_raw.copy(), baseline_rows) if df_raw is not None else {}
    proc_report = _compute_quality_report(df_proc_active.copy(), baseline_rows) if df_proc_active is not None else raw_report

    raw_score = raw_report.get("score", 0)
    proc_score = proc_report.get("score", 0)
    raw_rows = raw_report.get("rows", baseline_rows)
    proc_rows = proc_report.get("rows", baseline_rows)
    delta = proc_score - raw_score

    comparison = {
        "raw_score": int(raw_score),
        "processed_score": int(proc_score),
        "delta": int(delta),
        "raw_rows": int(raw_rows),
        "processed_rows": int(proc_rows)
    }

    response_data = {
        "filename": active_dataset.get("filename", "veri.csv"),
        "upload_time": active_dataset.get("upload_time", "14:32"),
        "comparison": comparison,
        **proc_report
    }

    return JSONResponse(content=response_data)


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

    # Outliers (IQR method on numeric columns)
    outlier_cols = []
    total_outliers = 0
    for c in active_cols:
        col_series = pd.to_numeric(proc_df[c], errors="coerce").dropna()
        if len(col_series) == 0:
            continue
        q1 = col_series.quantile(0.25)
        q3 = col_series.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        cnt = int(((col_series < lower) | (col_series > upper)).sum())
        if cnt > 0:
            total_outliers += cnt
            outlier_cols.append({
                "name": str(c),
                "count": cnt,
                "ratio": round((cnt / max(1, len(col_series))) * 100, 2)
            })
    outlier_cols.sort(key=lambda x: x["count"], reverse=True)

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
        "outliers": {
            "columns": outlier_cols,
            "total_outliers": total_outliers,
            "overall_rate": round((total_outliers / max(1, len(proc_df))) * 100, 2)
        },
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
                    if pd.api.types.is_numeric_dtype(processed_df_cache[c]):
                        mode_vals = processed_df_cache[c].mode()
                        if len(mode_vals) > 0:
                            processed_df_cache[c] = processed_df_cache[c].fillna(mode_vals[0])
                    else:
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

        elif op == "outlier_management":
            method = method or "cap"
            selected_cols = payload.get("columns") or []

            # 1) Aday sütunlar: sayısal, düşürülmemiş, ID/kategorik değil
            def _is_id_like(c):
                low = str(c).lower()
                if "id" in low or "code" in low or "no" in low or "key" in low:
                    return True
                s = processed_df_cache[c]
                non_na = s.dropna()
                if len(non_na) == 0:
                    return False
                return int(non_na.nunique()) == int(len(non_na)) and pd.api.types.is_numeric_dtype(s)

            candidate_cols = [c for c in processed_df_cache.columns if c not in dropped_columns
                              if pd.api.types.is_numeric_dtype(processed_df_cache[c])
                              and not _is_id_like(c)]

            # 2) Seçilen sütunlar filtresi (kullanıcı açıkça seçtiyse ID muafiyeti uygulanmaz)
            if selected_cols:
                numeric_cols = [c for c in processed_df_cache.columns
                                if c in selected_cols and c not in dropped_columns
                                and pd.api.types.is_numeric_dtype(processed_df_cache[c])]
            else:
                numeric_cols = candidate_cols

            if not numeric_cols:
                raise ValueError("İşlenecek sayısal sütun bulunamadı; aykırı değer işlemi uygulanamadı.")

            # 3) Sınırlar (Tüm sayaçlarla uyumlu 1.5×IQR)
            iqr_factor = 1.5
            bounds = {}
            for c in numeric_cols:
                series = pd.to_numeric(processed_df_cache[c], errors="coerce").dropna()
                if len(series) == 0:
                    continue
                q1 = float(series.quantile(0.25))
                q3 = float(series.quantile(0.75))
                iqr = q3 - q1
                bounds[c] = {
                    "iqr_lower": q1 - iqr_factor * iqr,
                    "iqr_upper": q3 + iqr_factor * iqr,
                    "median": float(series.median())
                }

            # 4) Her sütun için aykırı işaretleri (1.5×IQR sınırına göre)
            outlier_flags = {}
            for c in numeric_cols:
                if c in bounds:
                    s = pd.to_numeric(processed_df_cache[c], errors="coerce")
                    outlier_flags[c] = (s < bounds[c]["iqr_lower"]) | (s > bounds[c]["iqr_upper"])
                else:
                    outlier_flags[c] = pd.Series(False, index=processed_df_cache.index)

            if method == "remove_iqr":
                start_rows = len(processed_df_cache)
                total_removed = 0
                for _ in range(5):
                    if len(processed_df_cache) == 0:
                        break
                    # Güncel df ile 1.5×IQR bayrakları yeniden hesaplanır
                    cur_flags = {}
                    for c in numeric_cols:
                        s = pd.to_numeric(processed_df_cache[c], errors="coerce")
                        s_clean = s.dropna()
                        if len(s_clean) >= 4:
                            q1 = float(s_clean.quantile(0.25))
                            q3 = float(s_clean.quantile(0.75))
                            iqr = q3 - q1
                            if iqr > 0:
                                lower = q1 - 1.5 * iqr
                                upper = q3 + 1.5 * iqr
                                cur_flags[c] = (s < lower) | (s > upper)
                            else:
                                cur_flags[c] = pd.Series(False, index=processed_df_cache.index)
                        else:
                            cur_flags[c] = pd.Series(False, index=processed_df_cache.index)

                    bad = pd.Series(False, index=processed_df_cache.index)
                    for c in numeric_cols:
                        bad = bad | cur_flags[c].fillna(False)

                    bad_cnt = int(bad.sum())
                    if bad_cnt == 0:
                        break
                    if len(processed_df_cache) - bad_cnt < start_rows * 0.5:
                        break
                    processed_df_cache = processed_df_cache[~bad].reset_index(drop=True)
                    total_removed += bad_cnt

                desc = f"Aykırı satırlar silindi ({total_removed} satır, 1.5×IQR, seçili {len(numeric_cols)} sütun)"

            elif method == "remove_zscore":
                bad = pd.Series(False, index=processed_df_cache.index)
                for c in numeric_cols:
                    s = pd.to_numeric(processed_df_cache[c], errors="coerce")
                    mean = float(s.mean())
                    std = float(s.std())
                    if std == 0 or pd.isna(std):
                        continue
                    bad = bad | ((s - mean).abs() > 3 * std).fillna(False)
                removed = int(bad.sum())
                processed_df_cache = processed_df_cache[~bad].reset_index(drop=True)
                desc = f"Aykırı satırlar silindi ({removed} satır, Z-Score > 3, seçili {len(numeric_cols)} sütun)"

            elif method == "cap":
                for c in numeric_cols:
                    if c in bounds:
                        processed_df_cache[c] = pd.to_numeric(processed_df_cache[c], errors="coerce").clip(
                            lower=bounds[c]["iqr_lower"], upper=bounds[c]["iqr_upper"])
                desc = f"Aykırı değerler sınır değerlere eşitlendi (Capping, 1.5×IQR, seçili {len(numeric_cols)} sütun)"

            elif method == "replace_median":
                for c in numeric_cols:
                    if c in bounds:
                        s = pd.to_numeric(processed_df_cache[c], errors="coerce").astype(float)
                        s = s.mask(outlier_flags[c], bounds[c]["median"])
                        processed_df_cache[c] = s
                desc = f"Aykırı değerler medyan ile değiştirildi (1.5×IQR sınırı, seçili {len(numeric_cols)} sütun)"

            else:
                raise ValueError(f"Geçersiz aykırı değer yöntemi: {method}")

            icon = "filter_alt"
            icon_bg = "bg-warning-orange/10"
            icon_color = "text-[#a1680d]"
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


@app.get("/api/export/csv")
async def export_current_csv():
    global processed_df_cache, active_df_cache, active_dataset, dropped_columns
    df = processed_df_cache if processed_df_cache is not None else active_df_cache
    if df is None or not active_dataset:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="İndirilecek veri seti bulunamadı.")

    active_cols = [c for c in df.columns if c not in dropped_columns]
    download_df = df[active_cols]

    csv_bytes = download_df.to_csv(index=False, encoding="utf-8-sig")
    orig_name = active_dataset.get("filename", "veri.csv")
    base = orig_name.rsplit(".", 1)[0]
    export_name = f"{base}_aktarilan.csv"

    from fastapi.responses import Response
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{export_name}"'}
    )


# ==========================================
# Görselleştirme Karar Motoru (Chart Decision Engine)
# ==========================================

# Modül seviyesinde genişletilebilir alan adı sözlüğü
LABEL_DICT: Dict[str, str] = {
    "order_hour": "Sipariş Saati",
    "customer_age": "Müşteri Yaşı",
    "order_date": "Sipariş Tarihi",
    "product_name": "Ürün Adı",
    "price": "Fiyat",
    "quantity": "Adet",
    "regionname": "Bölge Adı",
    "propertycount": "Konut Sayısı",
    "bedroom2": "Yatak Odası",
    "bathroom": "Banyo",
    "car": "Araç",
    "landsize": "Arsa Alanı",
    "landarea": "Arsa Alanı",
    "buildingarea": "Bina Alanı",
    "yearbuilt": "Yapım Yılı",
    "date": "Tarih",
    "time": "Saat",
    "hour": "Saat",
    "day": "Gün",
    "month": "Ay",
    "year": "Yıl",
    "timestamp": "Zaman Damgası",
    "age": "Yaş",
    "income": "Gelir",
    "credit_score": "Kredi Skoru",
    "segment": "Segment",
    "city": "Şehir",
    "status": "Durum",
    "target": "Hedef",
    "oee": "OEE",
    "availability": "Kullanılabilirlik",
    "performance": "Performans",
    "quality": "Kalite"
}


def pretty_label(col: Optional[str]) -> str:
    """Sütun adlarını güzelleştirir; sözlükte yoksa Title Case formatlar."""
    if not col:
        return ""
    col_str = str(col).strip()
    norm = re.sub(r'[\s\-_]+', '', col_str).lower()
    for k, v in LABEL_DICT.items():
        k_norm = re.sub(r'[\s\-_]+', '', k).lower()
        if norm == k_norm:
            return v
    # Fallback: alt çizgi / tireleri boşluğa çevir ve Title Case yap
    cleaned = re.sub(r'[_\-]+', ' ', col_str).strip()
    return cleaned.title() if cleaned else col_str


def _looks_like_datetime(s: pd.Series, sample_size: int = 200) -> bool:
    """Bir serinin tarih/zaman içerip içermediğini tespit eder."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return True
    sample = s.dropna().head(sample_size)
    if len(sample) == 0:
        return False
    if pd.api.types.is_numeric_dtype(sample):
        return False
    parsed = pd.to_datetime(sample, errors="coerce")
    return float(parsed.notna().sum()) / len(sample) >= 0.8


def _is_integer_like(s: pd.Series) -> bool:
    """Serinin tam sayı veya tam sayıya yuvarlanmış değerlerden oluşup oluşmadığını tespit eder."""
    s = s.dropna()
    if len(s) == 0:
        return False
    if pd.api.types.is_integer_dtype(s.dtype):
        return True
    if pd.api.types.is_float_dtype(s.dtype):
        try:
            return bool((s == s.round()).all())
        except Exception:
            return False
    return False


def _classify_columns(df: pd.DataFrame) -> Dict[str, list]:
    """Sütunları numeric, datetime ve categorical olarak gruplar."""
    numeric_cols = []
    datetime_cols = []
    categorical_cols = []

    for col in df.columns:
        series = df[col]
        if pd.api.types.is_numeric_dtype(series):
            numeric_cols.append(str(col))
        elif _looks_like_datetime(series):
            datetime_cols.append(str(col))
        else:
            categorical_cols.append(str(col))

    return {
        "numeric": numeric_cols,
        "datetime": datetime_cols,
        "categorical": categorical_cols
    }


def decide_chart_plan(x_col: Optional[str], y_col: Optional[str], df: pd.DataFrame) -> dict:
    """Ortak Karar Motoru: Verilen sütun çifti için en uygun grafik planını üretir."""
    classification = _classify_columns(df)
    num_cols = set(classification["numeric"])
    dt_cols = set(classification["datetime"])
    cat_cols = set(classification["categorical"])

    def _get_axis_meta(col: Optional[str]) -> dict:
        if not col or col not in df.columns:
            return {"role": "none", "is_integer_like": False, "nunique": 0, "min": None, "max": None}
        s = df[col].dropna()
        if col in dt_cols:
            role = "time"
            return {"role": role, "is_integer_like": False, "nunique": int(s.nunique()), "min": None, "max": None}
        elif col in num_cols:
            int_like = _is_integer_like(s)
            role = "discrete" if (int_like and s.nunique() <= 30) else "continuous"
            min_val = float(s.min()) if len(s) > 0 else None
            max_val = float(s.max()) if len(s) > 0 else None
            return {"role": role, "is_integer_like": int_like, "nunique": int(s.nunique()), "min": min_val, "max": max_val}
        else:
            role = "categorical"
            return {"role": role, "is_integer_like": False, "nunique": int(s.nunique()), "min": None, "max": None}

    x_meta = _get_axis_meta(x_col)
    y_meta = _get_axis_meta(y_col)

    x_label = pretty_label(x_col) if x_col else ""
    y_label = pretty_label(y_col) if y_col else ""

    # Gözlem sayısı
    n_points = 0
    if x_col and y_col and x_col in df.columns and y_col in df.columns:
        n_points = int(df[[x_col, y_col]].dropna().shape[0])
    elif x_col and x_col in df.columns:
        n_points = int(df[x_col].dropna().shape[0])

    needs_jitter = bool(
        (x_meta["is_integer_like"] or y_meta["is_integer_like"] or
         (x_meta["nunique"] > 0 and x_meta["nunique"] <= 0.25 * max(1, n_points)) or
         (y_meta["nunique"] > 0 and y_meta["nunique"] <= 0.25 * max(1, n_points))) and
        x_meta["role"] in ["continuous", "discrete"] and y_meta["role"] in ["continuous", "discrete"]
    )

    overplot_meta = {
        "needs_jitter": needs_jitter,
        "opacity": 0.4 if needs_jitter else 0.6,
        "symbol_size": 4 if n_points > 5000 else (5 if n_points > 1000 else 7),
        "large_mode": bool(n_points > 2000),
        "n_points": n_points
    }

    # 1. Tek Değişken (x == y veya y yok)
    if not y_col or x_col == y_col:
        if x_col in dt_cols:
            return {
                "chart_type": "line",
                "title": f"{x_label} Zaman Serisi",
                "reason": "Zaman Serisi Dağılımı",
                "x_col": x_col, "y_col": None,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {"rotate_labels": 30, "horizontal_bar": False}
            }
        elif x_col in num_cols:
            return {
                "chart_type": "histogram",
                "title": f"{x_label} Dağılımı",
                "reason": "Sayısal Değişken Frekans Dağılımı",
                "x_col": x_col, "y_col": None,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {"rotate_labels": None, "horizontal_bar": False}
            }
        else:
            n_cats = x_meta["nunique"]
            return {
                "chart_type": "bar",
                "title": f"{x_label} Kategorileri",
                "reason": f"Kategori Sayımları ({n_cats} farklı sınıf)",
                "x_col": x_col, "y_col": None,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {
                    "rotate_labels": 45 if 8 <= n_cats <= 15 else (30 if 5 <= n_cats < 8 else 0),
                    "horizontal_bar": bool(n_cats > 15)
                }
            }

    # 2. Zaman Serisi: x datetime + y numeric OR y datetime + x numeric
    if (x_col in dt_cols and y_col in num_cols) or (y_col in dt_cols and x_col in num_cols):
        time_c = x_col if x_col in dt_cols else y_col
        num_c = y_col if x_col in dt_cols else x_col
        t_label = pretty_label(time_c)
        n_label = pretty_label(num_c)
        return {
            "chart_type": "line",
            "title": f"{t_label} ile {n_label} Zaman Serisi",
            "reason": "Zaman İçindeki Değişim Eğilimi",
            "x_col": time_c, "y_col": num_c,
            "axis": {"x": _get_axis_meta(time_c), "y": _get_axis_meta(num_c)},
            "overplot": overplot_meta,
            "render_hint": {"rotate_labels": 30, "horizontal_bar": False}
        }

    # 3. Kesikli/Kategorik × Sürekli
    # Durum A: x kategorik veya kesikli (nunique <= 30), y sürekli sayısal
    if (x_col in cat_cols or (x_col in num_cols and x_meta["nunique"] <= 30)) and y_col in num_cols:
        n_cats = x_meta["nunique"]
        if n_cats <= 12:
            return {
                "chart_type": "grouped_boxplot",
                "title": f"{x_label}'a Göre {y_label}",
                "reason": f"Grup Dağılımı ve Çeyreklikler ({n_cats} grup)",
                "x_col": x_col, "y_col": y_col, "cat": x_col, "num": y_col,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {
                    "rotate_labels": 45 if 8 <= n_cats <= 12 else 0,
                    "horizontal_bar": False
                }
            }
        else:
            return {
                "chart_type": "bar_mean",
                "title": f"{x_label}'a Göre Ortalama {y_label}",
                "reason": f"Grup Ortalamaları ({n_cats} kategori için özet bar)",
                "x_col": x_col, "y_col": y_col, "cat": x_col, "num": y_col,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {
                    "rotate_labels": 45 if 12 < n_cats <= 15 else 0,
                    "horizontal_bar": bool(n_cats > 15)
                }
            }

    # Durum B: y kategorik veya kesikli (nunique <= 30), x sürekli sayısal
    if (y_col in cat_cols or (y_col in num_cols and y_meta["nunique"] <= 30)) and x_col in num_cols:
        n_cats = y_meta["nunique"]
        if n_cats <= 12:
            return {
                "chart_type": "grouped_boxplot",
                "title": f"{y_label}'a Göre {x_label}",
                "reason": f"Grup Dağılımı ve Çeyreklikler ({n_cats} grup)",
                "x_col": x_col, "y_col": y_col, "cat": y_col, "num": x_col,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {
                    "rotate_labels": 45 if 8 <= n_cats <= 12 else 0,
                    "horizontal_bar": False
                }
            }
        else:
            return {
                "chart_type": "bar_mean",
                "title": f"{y_label}'a Göre Ortalama {x_label}",
                "reason": f"Grup Ortalamaları ({n_cats} kategori için özet bar)",
                "x_col": x_col, "y_col": y_col, "cat": y_col, "num": x_col,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {
                    "rotate_labels": 45 if 12 < n_cats <= 15 else 0,
                    "horizontal_bar": bool(n_cats > 15)
                }
            }

    # 4. Sürekli × Sürekli (Her iki eksen sayısal ve nunique > 30)
    if x_col in num_cols and y_col in num_cols:
        if n_points > 500:
            return {
                "chart_type": "density_heatmap",
                "title": f"{x_label} × {y_label} Yoğunluk",
                "reason": f"n={n_points} > 500 olduğu için 2D Yoğunluk Haritası (Overplotting Koruması)",
                "x_col": x_col, "y_col": y_col,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {"rotate_labels": 0, "horizontal_bar": False}
            }
        else:
            return {
                "chart_type": "scatter",
                "title": f"{x_label} ile {y_label} Dağılımı",
                "reason": f"İki Değişkenli Sürekli Dağılım (n={n_points})",
                "x_col": x_col, "y_col": y_col,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {"rotate_labels": 0, "horizontal_bar": False}
            }

    # 5. Kategorik × Kategorik
    n_cats = x_meta["nunique"]
    return {
        "chart_type": "bar",
        "title": f"{x_label} Kategorileri",
        "reason": f"Kategorik Dağılım Karşılaştırması ({n_cats} sınıf)",
        "x_col": x_col, "y_col": y_col,
        "axis": {"x": x_meta, "y": y_meta},
        "overplot": overplot_meta,
        "render_hint": {
            "rotate_labels": 45 if 8 <= n_cats <= 15 else 0,
            "horizontal_bar": bool(n_cats > 15)
        }
    }


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

    classification = _classify_columns(curr_df)
    numeric_cols = classification["numeric"]
    datetime_cols = classification["datetime"]
    categorical_cols = classification["categorical"]

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

    # Karar Motoru ile Dinamik Öneriler Üretimi
    suggestions = []

    # 1. Zaman Serisi varsa ilk öneri Line
    if len(datetime_cols) > 0 and len(numeric_cols) > 0:
        plan_line = decide_chart_plan(datetime_cols[0], numeric_cols[0], curr_df)
        suggestions.append({
            "type": "line",
            "x": datetime_cols[0],
            "y": numeric_cols[0],
            "title": plan_line["title"],
            "reason": plan_line["reason"],
            "plan": plan_line
        })
    elif len(numeric_cols) > 0:
        plan_hist = decide_chart_plan(numeric_cols[0], None, curr_df)
        suggestions.append({
            "type": "histogram",
            "column": str(numeric_cols[0]),
            "title": plan_hist["title"],
            "reason": plan_hist["reason"],
            "plan": plan_hist
        })

    # 2. Kategorik çubuk grafik
    if len(categorical_cols) > 0:
        plan_bar = decide_chart_plan(categorical_cols[0], None, curr_df)
        suggestions.append({
            "type": "bar",
            "column": str(categorical_cols[0]),
            "title": plan_bar["title"],
            "reason": plan_bar["reason"],
            "plan": plan_bar
        })

    # 3. İki değişkenli ilişki (Scatter veya 2D Heatmap)
    if len(strongest_pairs) > 0:
        p0 = strongest_pairs[0]
        plan_2d = decide_chart_plan(p0["a"], p0["b"], curr_df)
        suggestions.append({
            "type": plan_2d["chart_type"],
            "x": p0["a"],
            "y": p0["b"],
            "title": plan_2d["title"],
            "reason": f"En Güçlü Korelasyon (r = {p0['corr']}) - {plan_2d['reason']}",
            "plan": plan_2d
        })
    elif len(numeric_cols) >= 2:
        plan_2d = decide_chart_plan(numeric_cols[0], numeric_cols[1], curr_df)
        suggestions.append({
            "type": plan_2d["chart_type"],
            "x": str(numeric_cols[0]),
            "y": str(numeric_cols[1]),
            "title": plan_2d["title"],
            "reason": plan_2d["reason"],
            "plan": plan_2d
        })

    # 4. Kategoriye göre sayısal dağılım (Grouped boxplot veya Ortalama Bar)
    if len(categorical_cols) > 0 and len(numeric_cols) > 0:
        plan_grp = decide_chart_plan(categorical_cols[0], numeric_cols[0], curr_df)
        suggestions.append({
            "type": plan_grp["chart_type"],
            "cat": str(categorical_cols[0]),
            "num": str(numeric_cols[0]),
            "title": plan_grp["title"],
            "reason": plan_grp["reason"],
            "plan": plan_grp
        })

    # 5. Boxplot (Uç Değer ve Çeyreklikler)
    target_box_col = numeric_cols[1] if len(numeric_cols) > 1 else (numeric_cols[0] if len(numeric_cols) > 0 else None)
    if target_box_col:
        suggestions.append({
            "type": "boxplot",
            "column": str(target_box_col),
            "title": f"{pretty_label(target_box_col)} Kutu Grafiği",
            "reason": "Uç Değer ve Çeyreklikler (Boxplot)"
        })

    return JSONResponse(content={
        "date_columns": [str(c) for c in datetime_cols],
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

    classification = _classify_columns(curr_df)
    numeric_cols = classification["numeric"]
    datetime_cols = classification["datetime"]
    categorical_cols = classification["categorical"]

    is_numeric = column in numeric_cols
    is_datetime = column in datetime_cols

    suggestions = []
    univariate = None
    note = None

    if is_datetime:
        # --- Tarih/Zaman Odak ---
        # 1. Sayısal sütunlarla Line grafikleri
        for num in numeric_cols[:3]:
            plan_line = decide_chart_plan(column, num, curr_df)
            suggestions.append({
                "type": "line",
                "x": str(column),
                "y": str(num),
                "title": plan_line["title"],
                "reason": plan_line["reason"],
                "plan": plan_line
            })

        # Univariate: Tarih dağılımı
        series_dt = pd.to_datetime(curr_df[column], errors="coerce").dropna()
        min_dt = str(series_dt.min()) if len(series_dt) > 0 else "—"
        max_dt = str(series_dt.max()) if len(series_dt) > 0 else "—"
        total_obs = len(series_dt)

        univariate = {
            "is_datetime": True,
            "is_numeric": False,
            "stats": {
                "count": total_obs,
                "min": min_dt,
                "max": max_dt,
                "nunique": int(series_dt.nunique())
            }
        }
        note = f"'{pretty_label(column)}' zaman serisi değişkenidir; zaman içindeki eğilimleri incelemek için çizgi (line) grafikleri önerilmektedir."

    elif is_numeric:
        # --- Sayısal Odak ---
        # 1. Histogram
        plan_hist = decide_chart_plan(column, None, curr_df)
        suggestions.append({
            "type": "histogram",
            "column": str(column),
            "title": plan_hist["title"],
            "reason": "Sayısal Dağılım (Odak)",
            "plan": plan_hist
        })
        # 2. Diğer sayısal sütunlarla ilişki (Scatter / Density)
        others = [c for c in numeric_cols if c != column]
        for other in others[:3]:
            plan_2d = decide_chart_plan(column, other, curr_df)
            suggestions.append({
                "type": plan_2d["chart_type"],
                "x": str(column),
                "y": str(other),
                "title": plan_2d["title"],
                "reason": plan_2d["reason"],
                "plan": plan_2d
            })
        # 3. Boxplot
        suggestions.append({
            "type": "boxplot",
            "column": str(column),
            "title": f"{pretty_label(column)} Kutu Grafiği",
            "reason": "Uç Değer ve Çeyreklikler"
        })

        # Univariate: istatistikler + histogram + boxplot
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
            "is_datetime": False,
            "stats": stats,
            "histogram": histogram,
            "boxplot": boxplot
        }

    else:
        # --- Kategorik Odak ---
        # 1. Bar
        plan_bar = decide_chart_plan(column, None, curr_df)
        suggestions.append({
            "type": "bar",
            "column": str(column),
            "title": plan_bar["title"],
            "reason": "Kategori Sayıları (Odak)",
            "plan": plan_bar
        })
        # 2. Sayısal değişkenlere göre dağılımlar (Grouped boxplot / Bar Mean)
        for num in numeric_cols[:3]:
            plan_grp = decide_chart_plan(column, num, curr_df)
            suggestions.append({
                "type": plan_grp["chart_type"],
                "cat": str(column),
                "num": str(num),
                "title": plan_grp["title"],
                "reason": plan_grp["reason"],
                "plan": plan_grp
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
        univariate = {"is_numeric": False, "is_datetime": False, "bar": {"items": items}}

        note = (f"'{pretty_label(column)}' kategorik bir değişkendir; histogram/boxplot yerine kategori "
                f"sayıları (bar) ve kategorilere göre sayısal dağılım gösterilmektedir.")

    # --- Korelasyon: heatmap tüm matris + liste odak sütununa göre ---
    corr_matrix = []
    strongest = []
    corr_cols = [str(c) for c in numeric_cols]
    if len(numeric_cols) >= 2:
        corr_df = curr_df[[c for c in numeric_cols]]
        corr_np = corr_df.corr()
        corr_matrix = [[round(float(v), 2) for v in row] for row in corr_np.values.tolist()]

        if is_numeric and column in corr_cols:
            col_row = corr_np[column].drop(labels=[column])
            sorted_pairs = col_row.abs().sort_values(ascending=False)
            for other, r in sorted_pairs.head(5).items():
                strongest.append({"a": str(column), "b": str(other), "corr": round(float(r), 2)})
        else:
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
        "is_datetime": is_datetime,
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

    if type == "auto":
        col_x = x or column or cat
        col_y = y or num
        plan = decide_chart_plan(col_x, col_y, curr_df)
        target_type = plan["chart_type"]
        type = target_type
        if target_type in ["grouped_boxplot", "bar_mean", "bar_median"]:
            cat = plan.get("cat", col_x)
            num = plan.get("num", col_y)
        elif target_type in ["scatter", "density_heatmap", "line"]:
            x = plan.get("x_col", col_x)
            y = plan.get("y_col", col_y)
        else:
            column = plan.get("x_col", col_x)

    if type == "histogram":
        col_name = column or x or num
        if not col_name or col_name not in curr_df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz histogram kolonu.")

        series = pd.to_numeric(curr_df[col_name], errors="coerce").dropna()
        if len(series) == 0:
            return JSONResponse(content={"bins": [0, 1], "bin_labels": ["0 - 1"], "counts": [0], "column_label": pretty_label(col_name)})

        counts, bin_edges = np.histogram(series, bins=min(15, max(5, int(np.sqrt(len(series))))))
        bin_labels = [f"{bin_edges[i]:.1f} - {bin_edges[i+1]:.1f}" for i in range(len(counts))]
        return JSONResponse(content={
            "column": str(col_name),
            "column_label": pretty_label(col_name),
            "bins": [round(float(b), 2) for b in bin_edges],
            "bin_labels": bin_labels,
            "counts": [int(c) for c in counts],
            "plan": decide_chart_plan(col_name, None, curr_df)
        })

    elif type == "boxplot":
        col_name = column or x or num
        if not col_name or col_name not in curr_df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz boxplot kolonu.")

        series = pd.to_numeric(curr_df[col_name], errors="coerce").dropna()
        if len(series) == 0:
            return JSONResponse(content={"box": [0, 0, 0, 0, 0], "outliers": [], "column_label": pretty_label(col_name)})

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
            "column": str(col_name),
            "column_label": pretty_label(col_name),
            "box": [round(whisker_min, 2), round(q1, 2), round(med, 2), round(q3, 2), round(whisker_max, 2)],
            "outliers": outliers[:100],
            "q1": round(q1, 2),
            "q3": round(q3, 2),
            "iqr": round(iqr, 2),
            "lower_bound": round(low_bound, 2),
            "upper_bound": round(high_bound, 2),
            "outlier_count": len(outliers),
            "total": int(len(series)),
            "plan": decide_chart_plan(col_name, None, curr_df)
        })

    elif type == "bar":
        col_name = column or x or cat
        if not col_name or col_name not in curr_df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz bar kolonu.")

        series = curr_df[col_name].dropna()
        total_cnt = max(1, len(series))
        val_counts = series.value_counts().head(30)
        items = []
        for val, count in val_counts.items():
            items.append({
                "value": str(val),
                "count": int(count),
                "ratio": round((count / total_cnt) * 100, 1)
            })
        return JSONResponse(content={
            "column": str(col_name),
            "column_label": pretty_label(col_name),
            "items": items,
            "plan": decide_chart_plan(col_name, None, curr_df)
        })

    elif type in ["bar_mean", "bar_median"]:
        cat_col = cat or x
        num_col = num or y or column
        if not cat_col or not num_col or cat_col not in curr_df.columns or num_col not in curr_df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz bar_mean/bar_median kolonları.")

        sub = curr_df[[cat_col, num_col]].dropna()
        sub[num_col] = pd.to_numeric(sub[num_col], errors="coerce")
        sub = sub.dropna(subset=[num_col])

        is_median = (type == "bar_median")
        grouped = sub.groupby(cat_col)[num_col].agg(["mean", "median", "count"]).reset_index()
        sort_key = "median" if is_median else "mean"
        grouped = grouped.sort_values(sort_key, ascending=False).head(30)

        items = []
        for _, row in grouped.iterrows():
            items.append({
                "value": str(row[cat_col]),
                "mean": round(float(row["mean"]), 2),
                "median": round(float(row["median"]), 2),
                "count": int(row["count"])
            })

        return JSONResponse(content={
            "cat": str(cat_col),
            "num": str(num_col),
            "cat_label": pretty_label(cat_col),
            "num_label": pretty_label(num_col),
            "type": type,
            "items": items,
            "plan": decide_chart_plan(cat_col, num_col, curr_df)
        })

    elif type == "scatter":
        x_col = x or column
        y_col = y
        if not x_col or not y_col or x_col not in curr_df.columns or y_col not in curr_df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz scatter kolonları.")

        sub = curr_df[[x_col, y_col]].dropna()
        plan = decide_chart_plan(x_col, y_col, curr_df)
        overplot = plan.get("overplot", {})
        needs_jitter = overplot.get("needs_jitter", False)

        x_raw = pd.to_numeric(sub[x_col], errors="coerce")
        y_raw = pd.to_numeric(sub[y_col], errors="coerce")
        valid = x_raw.notna() & y_raw.notna()
        x_valid = x_raw[valid].values
        y_valid = y_raw[valid].values

        total_pts = len(x_valid)
        if total_pts == 0:
            return JSONResponse(content={
                "x_name": str(x_col), "y_name": str(y_col),
                "x_label": pretty_label(x_col), "y_label": pretty_label(y_col),
                "x": [], "y": [], "points": [], "n": 0, "needs_jitter": False, "plan": plan
            })

        # Jitter uygulama (deterministik seed)
        if needs_jitter:
            rng = np.random.default_rng(42)
            x_range = float(x_valid.max() - x_valid.min()) if len(x_valid) > 0 else 1.0
            y_range = float(y_valid.max() - y_valid.min()) if len(y_valid) > 0 else 1.0
            jitter_x = rng.uniform(-x_range * 0.02, x_range * 0.02, size=len(x_valid))
            jitter_y = rng.uniform(-y_range * 0.02, y_range * 0.02, size=len(y_valid))
            x_out = np.round(x_valid + jitter_x, 3).tolist()
            y_out = np.round(y_valid + jitter_y, 3).tolist()
        else:
            x_out = np.round(x_valid, 3).tolist()
            y_out = np.round(y_valid, 3).tolist()

        # Çakışan nokta frekanslarını hesapla
        pair_counts = {}
        for xv, yv in zip(x_valid, y_valid):
            k = (round(float(xv), 2), round(float(yv), 2))
            pair_counts[k] = pair_counts.get(k, 0) + 1

        points_data = []
        for xo, yo, xv, yv in zip(x_out, y_out, x_valid, y_valid):
            cnt = pair_counts.get((round(float(xv), 2), round(float(yv), 2)), 1)
            ratio = round((cnt / max(1, total_pts)) * 100, 1)
            points_data.append([float(xo), float(yo), int(cnt), float(ratio), float(xv), float(yv)])

        return JSONResponse(content={
            "x_name": str(x_col),
            "y_name": str(y_col),
            "x_label": pretty_label(x_col),
            "y_label": pretty_label(y_col),
            "x": x_out,
            "y": y_out,
            "points": points_data,
            "n": total_pts,
            "needs_jitter": needs_jitter,
            "plan": plan
        })

    elif type == "density_heatmap":
        x_col = x or column
        y_col = y
        if not x_col or not y_col or x_col not in curr_df.columns or y_col not in curr_df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz density_heatmap kolonları.")

        sub = curr_df[[x_col, y_col]].dropna()
        x_raw = pd.to_numeric(sub[x_col], errors="coerce")
        y_raw = pd.to_numeric(sub[y_col], errors="coerce")
        valid = x_raw.notna() & y_raw.notna()
        x_clean = x_raw[valid].values
        y_clean = y_raw[valid].values

        if len(x_clean) == 0:
            return JSONResponse(content={
                "x_name": str(x_col), "y_name": str(y_col),
                "x_label": pretty_label(x_col), "y_label": pretty_label(y_col),
                "bins_x": [0.0, 1.0], "bins_y": [0.0, 1.0],
                "counts": [[0]], "n": 0, "min_count": 0, "max_count": 0,
                "plan": decide_chart_plan(x_col, y_col, curr_df)
            })

        H, xedges, yedges = np.histogram2d(x_clean, y_clean, bins=[50, 40])
        max_c = int(H.max()) if H.size > 0 else 0
        min_c = int(H[H > 0].min()) if (H > 0).any() else 0

        # ECharts heatmap için [x_idx, y_idx, count] listesi
        matrix_data = []
        for i in range(len(xedges) - 1):
            for j in range(len(yedges) - 1):
                c_val = int(H[i, j])
                if c_val > 0:
                    matrix_data.append([i, j, c_val])

        return JSONResponse(content={
            "x_name": str(x_col),
            "y_name": str(y_col),
            "x_label": pretty_label(x_col),
            "y_label": pretty_label(y_col),
            "bins_x": [round(float(v), 4) for v in xedges],
            "bins_y": [round(float(v), 4) for v in yedges],
            "data": matrix_data,
            "n": int(len(x_clean)),
            "min_count": min_c,
            "max_count": max_c,
            "plan": decide_chart_plan(x_col, y_col, curr_df)
        })

    elif type == "line":
        x_col = x or column
        y_col = y or num
        if not x_col or not y_col or x_col not in curr_df.columns or y_col not in curr_df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz line kolonları.")

        sub = curr_df[[x_col, y_col]].dropna().copy()
        sub["_parsed_dt"] = pd.to_datetime(sub[x_col], errors="coerce")
        sub = sub.dropna(subset=["_parsed_dt"])
        sub = sub.sort_values("_parsed_dt")
        sub[y_col] = pd.to_numeric(sub[y_col], errors="coerce")
        sub = sub.dropna(subset=[y_col])

        # Satır > 20.000 ise sıralı adımla küçült
        if len(sub) > 20000:
            step = int(np.ceil(len(sub) / 20000.0))
            sub = sub.iloc[::step]

        x_vals = [
            ts.strftime("%Y-%m-%d %H:%M:%S") if (ts.hour or ts.minute or ts.second) else ts.strftime("%Y-%m-%d")
            for ts in sub["_parsed_dt"]
        ]
        y_vals = [round(float(v), 2) for v in sub[y_col].tolist()]

        return JSONResponse(content={
            "x_name": str(x_col),
            "y_name": str(y_col),
            "x_label": pretty_label(x_col),
            "y_label": pretty_label(y_col),
            "x": x_vals,
            "y": y_vals,
            "n": len(x_vals),
            "plan": decide_chart_plan(x_col, y_col, curr_df)
        })

    elif type == "grouped_boxplot":
        cat_col = cat or x
        num_col = num or y or column
        if not cat_col or not num_col or cat_col not in curr_df.columns or num_col not in curr_df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz grouped boxplot kolonları.")

        sub_df = curr_df[[cat_col, num_col]].dropna()
        top_cats = sub_df[cat_col].value_counts().head(8).index.tolist()

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
            "cat_label": pretty_label(cat_col),
            "num_label": pretty_label(num_col),
            "groups": groups,
            "plan": decide_chart_plan(cat_col, num_col, curr_df)
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


def get_ml_dataframe() -> Optional[pd.DataFrame]:
    if processed_df_cache is not None:
        df = processed_df_cache.copy()
        if dropped_columns:
            df = df.drop(columns=[c for c in dropped_columns if c in df.columns], errors="ignore")
    elif active_df_cache is not None:
        df = active_df_cache.copy()
    else:
        return None
    return df


CARDINALITY_RATIO = 0.70      # metin/kategorik benzersizlik oranı eşiği
NUMERIC_ID_RATIO = 0.90       # integer-like sayısal benzersizlik eşiği
MISSING_RATIO = 0.80          # eksiklik oranı eşiği


def _is_integer_like(s: pd.Series) -> bool:
    s = s.dropna()
    if len(s) == 0:
        return False
    if pd.api.types.is_integer_dtype(s.dtype):
        return True
    if pd.api.types.is_float_dtype(s.dtype):
        return bool((s == s.round()).all())
    return False


_ID_RE = re.compile(
    r"(\b(uuid|tckn|tc_no|udi|code|kayit_no|kayıt_no|numara)\b)|"   # tam sözcükler
    r"(?:^|_)id$|_id(?:$|_)",                                        # 'id' ile biten / _id içeren
    re.IGNORECASE
)


def _col_kind(s: pd.Series) -> str:
    if pd.api.types.is_numeric_dtype(s):
        return "numeric"

    # Datetime tespiti (ilk 200 boş-olmayan örnekte >= %80 dönüşüm)
    sample = s.dropna().head(200)
    if len(sample) > 0:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                parsed = pd.to_datetime(sample, errors="coerce")
                if float(parsed.notna().sum() / len(sample)) >= 0.8:
                    return "datetime"
        except Exception:
            pass

    # Metin tespiti (ortalama uzunluk >= 30 veya en az bir değer > 80)
    if s.dtype == object or pd.api.types.is_string_dtype(s):
        s_str = s.dropna().astype(str)
        if len(s_str) > 0:
            lens = s_str.str.len()
            avg_len = float(lens.mean())
            max_len = int(lens.max())
            if avg_len >= 30 or max_len > 80:
                return "text"

    return "categorical"


def _auto_exclude_reason(name: str, s: pd.Series, kind: str) -> Optional[str]:
    n = int(s.notna().sum())
    total = int(len(s))
    nunique = int(s.nunique(dropna=True))
    if n == 0:
        return "Sütun tamamen boş"
    unique_ratio = nunique / n if n else 0.0
    missing_ratio = 1.0 - (n / total) if total else 1.0

    # 1) Sıfır varyans
    if nunique <= 1:
        return "Sabit sütun (tek benzersiz değer)"
    # 2) Aşırı eksik veri
    if missing_ratio >= MISSING_RATIO:
        return f"Aşırı eksik veri (%{round(missing_ratio * 100)})"
    # 3) Tarih/zaman
    if kind == "datetime":
        return "Tarih/zaman sütunu (özellik çıkarımı gerekir)"
    # 4) Serbest metin
    if kind == "text":
        return "Serbest metin sütunu"
    # 5) Güvenli ad sezgisi (kelime sınırlı; 'no'/'key' alt-dizesi YOK)
    if _ID_RE.search(str(name)):
        return "Kimlik/numara sütunu"
    # 6) Metin/kategorik yüksek benzersizlik
    if kind in ("categorical", "text") and unique_ratio >= CARDINALITY_RATIO:
        return f"Yüksek benzersizlik (%{round(unique_ratio * 100)})"
    # 7) Integer-like sayısal yüksek benzersizlik (UDI, Product ID int vb.)
    if kind == "numeric" and _is_integer_like(s) and unique_ratio >= NUMERIC_ID_RATIO:
        return f"Sayısal kimlik (integer, %{round(unique_ratio * 100)} benzersiz)"
    return None


def _auto_exclude_column(name: str, s: pd.Series, kind: Optional[str] = None) -> bool:
    kind = kind or _col_kind(s)
    return _auto_exclude_reason(name, s, kind) is not None


def _ml_data_source() -> str:
    if processed_df_cache is not None and original_df_cache is not None:
        if len(preprocessing_history_stack) > 1 or not processed_df_cache.equals(original_df_cache):
            return "processed"
    return "raw"


def _top_class_ratio(s: pd.Series) -> float:
    vc = s.dropna().value_counts(normalize=True)
    return float(vc.iloc[0]) if len(vc) else 0.0


def _detect_time_series(df: pd.DataFrame) -> tuple:
    """
    (confirmed, suspected, time_column)
    confirmed : gerçek zaman serisi — tekil zaman değerleri + düzenli aralıklar (örn. günlük/aylık).
    suspected : yalnızca zaman sütunu varlığı (kesit verideki 'Date' gibi) — bilgi rozeti, K-Fold gizlenmez.
    """
    TIME_KEYS = ("date", "time", "tarih", "saat", "timestamp", "datetime")

    for col in df.columns:
        s = df[col]
        name_low = str(col).lower()
        is_time_named = any(k in name_low for k in TIME_KEYS)

        parsed = None
        if pd.api.types.is_datetime64_any_dtype(s):
            parsed = s
        elif s.dtype == object:
            try:
                parsed = pd.to_datetime(s, errors="coerce")
            except Exception:
                parsed = None
        parseable = parsed is not None and parsed.notna().mean() >= 0.9

        if not is_time_named and not parseable:
            continue

        # Zaman benzeri sütun var: önce ŞÜPHE işaretlenir (K-Fold yine açık kalır)
        confirmed = False
        if parseable:
            ts = parsed.dropna()
            n = len(ts)
            if n >= 10:
                unique = ts.nunique() == n                 # tekil zaman değerleri (kesitte aynı tarih tekrarı yok)
                monotonic = bool(ts.is_monotonic_increasing)
                if unique and monotonic:
                    gaps = ts.diff().dropna()
                    if len(gaps) > 0:
                        med = gaps.median()
                        if med is not None and med > pd.Timedelta(0):
                            # Düzenli aralık: aralıkların çoğu medyandan %25 sapma içinde (aylık 30/31/28 gün uyumlu)
                            tolerance = med * 0.25
                            regular = float(((gaps - med).abs() <= tolerance).mean()) >= 0.9
                            confirmed = regular
        return bool(confirmed), True, str(col)

    return False, False, None


@app.get("/api/ml/config")
async def ml_config():
    df = get_ml_dataframe()
    if df is None or not active_dataset:
        return JSONResponse(status_code=404, content={"error": "Aktif bir veri seti yok. Önce bir CSV yükleyin."})

    columns = []
    missing_counts = {}
    auto_excluded = []
    text_cols = []
    datetime_cols = []
    n_high_card = 0

    for col in df.columns:
        s = df[col]
        kind = _col_kind(s)
        n_non_null = int(s.notna().sum())
        total_col_rows = len(s)
        missing_ratio = round(1.0 - (n_non_null / total_col_rows) if total_col_rows else 1.0, 3)
        avg_len = round(float(s.dropna().astype(str).str.len().mean()), 1) if n_non_null else 0.0
        uniq_ratio = round(float(s.nunique(dropna=True) / n_non_null) if n_non_null else 0.0, 3)
        if uniq_ratio >= 0.95:
            n_high_card += 1

        if kind == "text":
            text_cols.append(str(col))
        elif kind == "datetime":
            datetime_cols.append(str(col))

        reason = _auto_exclude_reason(col, s, kind)
        ex = reason is not None
        columns.append({
            "name": str(col),
            "dtype": str(s.dtype),
            "kind": kind,
            "avg_length": avg_len,
            "is_datetime": bool(kind == "datetime"),
            "unique_ratio": uniq_ratio,
            "missing_ratio": missing_ratio,
            "class_ratio": _top_class_ratio(s) if kind == "categorical" else None,
            "auto_exclude": ex,
            "should_exclude": ex,
            "exclude_reason": reason,
        })
        missing_counts[str(col)] = int(s.isna().sum())
        if ex:
            auto_excluded.append(str(col))

    total_rows = int(len(df))
    if total_rows < 50:
        sample_bucket = "tiny"
        cv_rec = {"cv_visible": False, "cv_fixed_k": None, "note": "Çapraz doğrulama için çok az veri (K-Fold kapalı)"}
    elif total_rows <= 150:
        sample_bucket = "small"
        cv_rec = {"cv_visible": True, "cv_fixed_k": 3, "note": "Küçük veri seti: K=3 sabitlendi"}
    elif total_rows <= 2000:
        sample_bucket = "normal"
        cv_rec = {"cv_visible": True, "cv_fixed_k": None, "note": ""}
    else:
        sample_bucket = "large"
        cv_rec = {"cv_visible": True, "cv_fixed_k": None, "note": ""}

    has_imbalance = any(c.get("class_ratio") is not None and c["class_ratio"] >= 0.90 for c in columns)
    missing_ratio = round(float(df.isna().sum().sum() / (len(df) * len(df.columns))), 4) if len(df) and len(df.columns) else 0.0

    profile = {
        "total_rows": total_rows,
        "n_numeric": int(sum(1 for c in columns if c["kind"] == "numeric")),
        "n_categorical": int(sum(1 for c in columns if c["kind"] == "categorical")),
        "n_datetime": int(len(datetime_cols)),
        "n_text": int(len(text_cols)),
        "n_high_cardinality": int(n_high_card),
        "missing_ratio": missing_ratio,
        "text_columns": text_cols,
        "datetime_columns": datetime_cols,
        "has_imbalance": has_imbalance,
        "sample_bucket": sample_bucket,
        "recommended": cv_rec,
    }

    first_num = next((c["name"] for c in columns if c["kind"] == "numeric"), columns[0]["name"] if columns else "")
    is_ts, ts_suspected, ts_col = _detect_time_series(df)
    return JSONResponse(content={
        "active": True,
        "data_source": _ml_data_source(),
        "is_time_series": is_ts,
        "time_series_suspected": ts_suspected,
        "time_column": ts_col,
        "filename": active_dataset.get("filename", "veri.csv"),
        "total_rows": total_rows,
        "columns": columns,
        "missing_counts": missing_counts,
        "default_target": first_num,
        "auto_excluded": auto_excluded,
        "feature_candidates": [c["name"] for c in columns],
        "profile": profile,
    })


CLASS_MODELS = {
    "logistic": {"name": "Logistic Regression", "cls": LogisticRegression, "kwargs": {"max_iter": 2000}},
    "dtree_clf": {"name": "Decision Tree", "cls": DecisionTreeClassifier, "kwargs": {"random_state": 42}},
    "rf_clf": {"name": "Random Forest", "cls": RandomForestClassifier, "kwargs": {"random_state": 42, "n_estimators": 50, "max_depth": 10, "n_jobs": -1}},
}
REGR_MODELS = {
    "linear": {"name": "Linear Regression", "cls": LinearRegression, "kwargs": {}},
    "dtree_reg": {"name": "Decision Tree Regressor", "cls": DecisionTreeRegressor, "kwargs": {"random_state": 42}},
    "rf_reg": {"name": "Random Forest Regressor", "cls": RandomForestRegressor, "kwargs": {"random_state": 42, "n_estimators": 50, "max_depth": 10, "n_jobs": -1}},
}

ALLOWED_HYPERPARAMS = {
    "rf_clf": ["n_estimators", "max_depth"],
    "rf_reg": ["n_estimators", "max_depth"],
    "dtree_clf": ["max_depth"],
    "dtree_reg": ["max_depth"],
    "logistic": ["C"],
    "linear": [],
}


def _coerce_hyper(key: str, val: Any):
    if key == "max_depth" and (val in (None, "auto", "", 0, "0") or val is None):
        return None
    try:
        f = float(val)
        if key in ("n_estimators", "max_depth"):
            return int(f)
        return f
    except (ValueError, TypeError):
        return None


@app.post("/api/ml/train")
def ml_train(req: dict):
    try:
        return _run_ml_training(req)
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "success": False,
            "error": f"Model eğitimi sırasında hata oluştu: {str(e)}",
            "detail": str(e),
            "traceback": traceback.format_exc(),
        })


def _run_ml_training(req: dict) -> JSONResponse:
    df = get_ml_dataframe()
    if df is None or not active_dataset:
        return JSONResponse(status_code=404, content={"error": "Aktif bir veri seti yok."})

    if len(df.columns) < 2:
        return JSONResponse(status_code=400, content={
            "error": "Model eğitimi için en az 2 sütun (1 hedef + en az 1 özellik) gereklidir.",
            "detail": f"Mevcut veri setinde yalnızca 1 sütun bulunmaktadır: {list(df.columns)}. Lütfen ana sayfadan çok sütunlu geçerli bir CSV dosyası yükleyin.",
        })

    target = req.get("target")
    if not target or target not in df.columns:
        return JSONResponse(status_code=400, content={"error": "Geçerli bir hedef değişken seçin."})

    problem_type = req.get("problem_type", "auto")   # auto | classification | regression
    train_ratio = float(req.get("train_ratio", 0.8))
    train_ratio = max(0.5, min(0.95, train_ratio))
    model_ids = req.get("models", [])
    cv_k = int(req.get("cv_k", 5))
    cv_mode = req.get("cv_mode", "auto")  # time_series | kfold | auto
    missing_strategy = req.get("missing_strategy", "fill")  # fill | drop
    user_exclude = req.get("exclude_columns", []) or []
    user_exclude = [c for c in user_exclude if c != target]

    if not model_ids:
        return JSONResponse(status_code=400, content={"error": "En az bir model seçin."})

    target_is_numeric = pd.api.types.is_numeric_dtype(df[target])
    is_classification = (problem_type == "classification") or (problem_type == "auto" and not target_is_numeric)
    is_regression = (problem_type == "regression") or (problem_type == "auto" and target_is_numeric)

    is_ts, ts_suspected, ts_col = _detect_time_series(df)
    use_ts = (cv_mode == "time_series") or (cv_mode == "auto" and is_ts)
    top_class = _top_class_ratio(df[target]) if is_classification else None
    imbalanced = bool(is_classification and top_class is not None and top_class >= 0.9)

    if use_ts and ts_col and ts_col in df.columns:
        df = df.sort_values(ts_col).reset_index(drop=True)

    # --- ID benzeri sütunları otomatik + kullanıcı seçimiyle hariç tut ---
    if "exclude_columns" in req and req["exclude_columns"] is not None:
        user_exclude = [c for c in req.get("exclude_columns", []) if c != target and c in df.columns]
        excluded = sorted(set(user_exclude))
    else:
        auto_excluded = [c for c in df.columns if c != target and _auto_exclude_column(c, df[c])]
        excluded = sorted(set(auto_excluded))

    features = [c for c in df.columns if c != target and c not in excluded]
    if not features:
        # Eğer tüm özellikler hariç tutulduysa kullanıcıya net hata dön
        return JSONResponse(status_code=400, content={
            "error": "Hariç tutma sonrası kullanılabilir özellik sütunu kalmadı.",
            "detail": f"Hariç tutulan sütunlar: {', '.join(excluded) if excluded else 'yok'}. Lütfen hariç tutulan sütun listesinden en az bir özelliği kaldırın.",
        })

    X = df[features].copy()
    y = df[target].copy()

    # --- 1) Eksik değer stratejisi (kodlama ÖNCESİ) ---
    X = X.dropna(axis=1, how="all")  # tamamen boş sütunları kaldır
    if missing_strategy == "fill":
        num_cols = [c for c in X.columns if pd.api.types.is_numeric_dtype(X[c])]
        cat_cols = [c for c in X.columns if not pd.api.types.is_numeric_dtype(X[c])]
        if num_cols:
            X[num_cols] = SimpleImputer(strategy="median").fit_transform(X[num_cols])
        if cat_cols:
            X[cat_cols] = SimpleImputer(strategy="most_frequent").fit_transform(X[cat_cols])
        y = y[X.notna().any(axis=1)]
        X = X[X.notna().any(axis=1)]
        y = y[X.index]
    else:  # drop
        df_clean = df.dropna(subset=features + [target])
        X = df_clean[features].copy()
        y = df_clean[target].copy()

    if len(X) < 5:
        return JSONResponse(status_code=400, content={"error": "Temizleme sonrası yeterli veri kalmadı."})

    # --- 2) Kategorik (metinsel) özellikleri get_dummies ile one-hot kodla ---
    cat_cols = [c for c in X.columns if not pd.api.types.is_numeric_dtype(X[c])]
    if cat_cols:
        X = pd.get_dummies(X, columns=cat_cols, prefix_sep="_", dtype=int)

    # --- 3) Güvenlik ağı: kalan NaN'ları impute et, hâlâ NaN olan satırları sil ---
    X = X.fillna(X.median(numeric_only=True)).fillna(0)
    X = X.dropna()
    y = y[X.index]
    y = y.dropna()
    X = X.loc[y.index]

    if len(X) < 5:
        return JSONResponse(status_code=400, content={"error": "Temizlik/imputation sonrası yeterli veri kalmadı."})

    # --- Hedef kodlama ---
    class_names = None
    if is_classification:
        y_le = LabelEncoder()
        y_enc = y_le.fit_transform(y.astype(str))
        class_names = [str(c) for c in y_le.classes_]
        y = y_enc
        if len(class_names) < 2:
            return JSONResponse(status_code=400, content={"error": "Hedef değişkende en az 2 sınıf olmalı."})

    feature_names = list(X.columns)  # one-hot sonrası gerçek özellik adları

    # --- Train/Test bölme ---
    stratify = None
    if not use_ts and is_classification and len(pd.Series(y).value_counts()) > 1 and min(pd.Series(y).value_counts()) >= 2:
        stratify = y
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, train_size=train_ratio, random_state=42, shuffle=not use_ts, stratify=stratify)

    models = CLASS_MODELS if is_classification else REGR_MODELS
    n_splits = max(2, min(cv_k, min(pd.Series(y).value_counts().min(), len(X)) if is_classification else len(X)))

    def _safe_float(v) -> Optional[float]:
        if v is None:
            return None
        try:
            f = float(v)
            if np.isnan(f) or np.isinf(f):
                return None
            return f
        except Exception:
            return None

    def _safe_float_list(arr) -> list:
        res = []
        for x in arr:
            sf = _safe_float(x)
            res.append(sf if sf is not None else 0.0)
        return res

    results = []
    for mid in model_ids:
        if mid not in models:
            continue
        cfg = models[mid]
        row = {"id": mid, "name": cfg["name"], "metrics": {}, "cv_mean": None, "cv_std": None,
               "model_error": None, "confusion": None, "roc": None, "actual_vs_predicted": None, "feature_importance": []}
        user_hypers = req.get("hyperparams", {}) or {}
        model_hypers = user_hypers.get(mid, {}) if isinstance(user_hypers, dict) else {}
        params = dict(cfg["kwargs"])
        allowed = ALLOWED_HYPERPARAMS.get(mid, [])
        for k, v in model_hypers.items():
            if k in allowed:
                coerced = _coerce_hyper(k, v)
                if k == "n_estimators" and coerced is not None:
                    params[k] = max(10, min(500, coerced))
                elif k == "max_depth":
                    params[k] = max(1, min(50, coerced)) if coerced is not None else None
                elif k == "C" and coerced is not None:
                    params[k] = max(0.001, min(1000.0, coerced))

        try:
            model = cfg["cls"](**params)
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            if is_classification:
                row["metrics"]["accuracy"] = _safe_float(accuracy_score(y_test, y_pred))
                row["metrics"]["precision"] = _safe_float(precision_score(y_test, y_pred, average="macro", zero_division=0))
                row["metrics"]["recall"] = _safe_float(recall_score(y_test, y_pred, average="macro", zero_division=0))
                row["metrics"]["f1"] = _safe_float(f1_score(y_test, y_pred, average="macro", zero_division=0))
                try:
                    if hasattr(model, "predict_proba"):
                        proba = model.predict_proba(X_test)
                        row["metrics"]["roc_auc"] = _safe_float(roc_auc_score(y_test, proba, multi_class="ovr", average="macro"))
                    else:
                        row["metrics"]["roc_auc"] = None
                except Exception:
                    row["metrics"]["roc_auc"] = None
                try:
                    if use_ts:
                        cv = TimeSeriesSplit(n_splits=n_splits)
                    else:
                        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
                    scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy")
                    row["cv_mean"], row["cv_std"] = _safe_float(scores.mean()), _safe_float(scores.std())
                except Exception:
                    pass
                cm = confusion_matrix(y_test, y_pred, labels=list(range(len(class_names))))
                row["confusion"] = {"matrix": [[int(val) for val in row_cm] for row_cm in cm], "labels": class_names}
                if hasattr(model, "predict_proba"):
                    try:
                        proba = model.predict_proba(X_test)
                        roc_curves = []
                        if len(class_names) == 2:
                            fpr, tpr, _ = roc_curve(y_test, proba[:, 1])
                            roc_curves.append({"label": f"{class_names[1]} (AUC)", "fpr": _safe_float_list(fpr), "tpr": _safe_float_list(tpr)})
                        else:
                            for i, cls in enumerate(class_names):
                                y_bin = (y_test == i).astype(int)
                                fpr, tpr, _ = roc_curve(y_bin, proba[:, i])
                                roc_curves.append({"label": cls, "fpr": _safe_float_list(fpr), "tpr": _safe_float_list(tpr)})
                        row["roc"] = roc_curves
                    except Exception:
                        row["roc"] = None
            else:
                row["metrics"]["r2"] = _safe_float(r2_score(y_test, y_pred))
                row["metrics"]["mae"] = _safe_float(mean_absolute_error(y_test, y_pred))
                row["metrics"]["mse"] = _safe_float(mean_squared_error(y_test, y_pred))
                row["metrics"]["rmse"] = _safe_float(np.sqrt(mean_squared_error(y_test, y_pred)))
                try:
                    if use_ts:
                        cv = TimeSeriesSplit(n_splits=n_splits)
                    else:
                        cv = KFold(n_splits=n_splits, shuffle=True, random_state=42)
                    scores = cross_val_score(model, X, y, cv=cv, scoring="r2")
                    row["cv_mean"], row["cv_std"] = _safe_float(scores.mean()), _safe_float(scores.std())
                except Exception:
                    pass
                n = len(y_test)
                idx = list(range(n))
                if n > 400:
                    step = n / 400.0
                    idx = [int(i * step) for i in range(400)]
                row["actual_vs_predicted"] = {
                    "actual": _safe_float_list([y_test.iloc[i] for i in idx]),
                    "predicted": _safe_float_list([y_pred[i] for i in idx]),
                }

            # Özellik önemi (one-hot sonrası feature_names kullanılır)
            if hasattr(model, "feature_importances_"):
                imp = model.feature_importances_
            elif hasattr(model, "coef_"):
                coef = model.coef_
                imp = np.abs(coef).mean(axis=0) if coef.ndim > 1 else np.abs(coef)
            else:
                imp = np.zeros(len(feature_names))
            row["feature_importance"] = sorted(
                [{"feature": str(f), "importance": _safe_float(v) or 0.0} for f, v in zip(feature_names, imp)],
                key=lambda x: x["importance"], reverse=True)[:15]
        except Exception as e:
            row["model_error"] = f"{cfg['name']}: {str(e)}"

        results.append(row)

    if not results:
        return JSONResponse(status_code=400, content={"error": "Seçilen modeller geçersiz."})

    healthy = [r for r in results if r["model_error"] is None]
    if not healthy:
        return JSONResponse(status_code=500, content={
            "error": "Seçilen hiçbir model eğitilemedi.",
            "detail": "; ".join(r["model_error"] for r in results if r.get("model_error")),
            "traceback": None,
        })

    if is_classification:
        def _score(r): return (r["metrics"].get("accuracy") or 0, r["metrics"].get("f1") or 0)
    else:
        def _score(r): return (r["metrics"].get("r2") or -999, 0)
    best = max(healthy, key=_score)

    return JSONResponse(content={
        "problem_type": "classification" if is_classification else "regression",
        "target": target,
        "data_source": _ml_data_source(),
        "is_time_series": is_ts,
        "time_series_suspected": ts_suspected,
        "time_column": ts_col,
        "cv_method": "time_series_split" if use_ts else ("stratified_kfold" if is_classification else "kfold"),
        "imbalanced": imbalanced,
        "imbalance_ratio": top_class,
        "excluded_columns": excluded,
        "feature_count": len(feature_names),
        "total_rows": int(len(X)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "cv_k": n_splits,
        "models": results,
        "best_model": best["id"],
    })


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

