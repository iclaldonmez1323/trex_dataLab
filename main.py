import io
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, File, UploadFile, HTTPException, status, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import numpy as np

app = FastAPI(title="trex DataLab API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_original_df: Optional[pd.DataFrame] = None
_working_df: Optional[pd.DataFrame] = None
_filename: Optional[str] = None
_size_bytes: Optional[int] = None
_upload_timestamp: Optional[str] = None
_ops_stack: List[Dict[str, Any]] = []

active_dataset: Dict[str, Any] = {}
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


def get_preview_rows(df: Optional[pd.DataFrame], limit: int = 10) -> List[Dict[str, Any]]:
    if df is None or len(df) == 0:
        return []
    preview_df = df.head(limit)
    rows = []
    for _, row in preview_df.iterrows():
        row_dict = {}
        for col in df.columns:
            row_dict[str(col)] = clean_val_for_json(row[col])
        rows.append(row_dict)
    return rows


def get_schema_data() -> List[Dict[str, Any]]:
    global _original_df, _working_df
    if _original_df is None or _working_df is None:
        return []

    schema = []
    working_rows = len(_working_df)
    orig_rows = len(_original_df)

    for col in _original_df.columns:
        col_str = str(col)
        kept = col in _working_df.columns

        if kept:
            curr_type = str(_working_df[col].dtype)
            missing_cnt = int(_working_df[col].isna().sum())
            missing_pct = round((missing_cnt / working_rows * 100), 1) if working_rows > 0 else 0.0
            is_num = pd.api.types.is_numeric_dtype(_working_df[col])
            is_dt = pd.api.types.is_datetime64_any_dtype(_working_df[col])
        else:
            curr_type = str(_original_df[col].dtype)
            missing_cnt = int(_original_df[col].isna().sum())
            missing_pct = round((missing_cnt / orig_rows * 100), 1) if orig_rows > 0 else 0.0
            is_num = pd.api.types.is_numeric_dtype(_original_df[col])
            is_dt = pd.api.types.is_datetime64_any_dtype(_original_df[col])

        kind = "numeric" if is_num else ("datetime" if is_dt else "categorical")
        orig_type = str(_original_df[col].dtype)

        schema.append({
            "name": col_str,
            "current_type": curr_type,
            "original_type": orig_type,
            "missing_count": missing_cnt,
            "missing_ratio": missing_pct,
            "kind": kind,
            "kept": kept
        })
    return schema


def replay_operations() -> pd.DataFrame:
    global _original_df, _ops_stack
    if _original_df is None:
        return pd.DataFrame()

    df = _original_df.copy()
    dropped_columns = set()

    for item in _ops_stack:
        op = item.get("op")
        col = item.get("column")
        method = item.get("method")
        target_type = item.get("target_type")

        if op == "fill_missing" and col in df.columns:
            if method == "median":
                med_val = df[col].median()
                df[col] = df[col].fillna(med_val)
            elif method == "mean":
                mean_val = df[col].mean()
                df[col] = df[col].fillna(mean_val)
            elif method == "mode":
                mode_s = df[col].mode()
                mode_val = mode_s.iloc[0] if len(mode_s) > 0 else 0
                df[col] = df[col].fillna(mode_val)
            elif method == "unknown":
                df[col] = df[col].fillna("Unknown")
            elif method == "drop_rows":
                df = df.dropna(subset=[col])

        elif op == "drop_duplicates":
            df = df.drop_duplicates()

        elif op == "drop_column" and col:
            dropped_columns.add(col)

        elif op == "keep_column" and col:
            dropped_columns.discard(col)

        elif op == "convert_type" and col in df.columns:
            if target_type == "int64":
                num_s = pd.to_numeric(df[col], errors="raise")
                df[col] = num_s.astype("int64")
            elif target_type == "float64":
                num_s = pd.to_numeric(df[col], errors="raise")
                df[col] = num_s.astype("float64")
            elif target_type == "datetime":
                df[col] = pd.to_datetime(df[col], errors="raise", format="mixed")
            elif target_type == "category":
                df[col] = df[col].astype("category")
            elif target_type == "string":
                df[col] = df[col].astype(str)

    cols_to_keep = [c for c in _original_df.columns if c not in dropped_columns]
    df = df[[c for c in cols_to_keep if c in df.columns]]
    return df


@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")


@app.get("/data-quality")
async def serve_data_quality():
    return FileResponse("static/data-quality.html")


@app.get("/preprocessing")
async def serve_preprocessing():
    return FileResponse("static/preprocessing.html")


@app.get("/visualization")
async def serve_visualization():
    return FileResponse("static/visualization.html")


@app.get("/portfolio")
async def serve_portfolio():
    return FileResponse("static/portfolio.html")


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    global _original_df, _working_df, _filename, _size_bytes, _upload_timestamp, _ops_stack, active_dataset

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

    _original_df = df.copy()
    _working_df = df.copy()
    _filename = file.filename
    _size_bytes = size_bytes
    _upload_timestamp = datetime.now().strftime("%H:%M")

    _ops_stack = [
        {
            "op": "initial",
            "description": "Orijinal veri yüklendi",
            "details": f"{len(_original_df):,} satır × {len(_original_df.columns)} sütun".replace(",", "."),
            "time": _upload_timestamp,
            "icon": "upload_file",
            "icon_bg": "bg-slate-gray/10",
            "icon_color": "text-slate-gray"
        }
    ]

    rows_count = int(len(df))
    cols_count = int(len(df.columns))
    missing_count = int(df.isna().sum().sum())
    duplicates_count = int(df.duplicated().sum())

    numeric_df = df.select_dtypes(include=[np.number])
    numeric_cols_count = int(len(numeric_df.columns))
    categorical_cols_count = int(cols_count - numeric_cols_count)

    column_types = {col: ("numeric" if col in numeric_df.columns else "categorical") for col in df.columns}

    preview_rows = get_preview_rows(df, 10)

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
        "upload_time": _upload_timestamp,
    }

    active_dataset = result_data
    return JSONResponse(content=result_data)


@app.get("/api/quality")
async def get_data_quality():
    global _working_df, _original_df, _filename, _upload_timestamp

    df = _working_df if _working_df is not None else _original_df
    if df is None or len(df) == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Önce bir CSV yükleyin."
        )

    rows = int(len(df))
    cols = int(len(df.columns))
    total_cells = rows * cols

    total_missing = int(df.isna().sum().sum())
    missing_frac = (total_missing / total_cells) if total_cells > 0 else 0.0
    overall_missing_rate = round(missing_frac * 100, 1)

    missing_cols_list = []
    for col in df.columns:
        m_count = int(df[col].isna().sum())
        if m_count > 0:
            m_ratio = round((m_count / rows) * 100, 1) if rows > 0 else 0.0
            missing_cols_list.append({
                "name": str(col),
                "count": m_count,
                "ratio": m_ratio
            })
    missing_cols_list.sort(key=lambda x: x["ratio"], reverse=True)

    dup_count = int(df.duplicated().sum())
    dup_frac = (dup_count / rows) if rows > 0 else 0.0
    dup_rate = round(dup_frac * 100, 2)

    dup_samples_df = df[df.duplicated(keep=False)].head(5)
    dup_samples = []
    for _, row in dup_samples_df.iterrows():
        sample_dict = {str(k): clean_val_for_json(v) for k, v in row.items()}
        dup_samples.append(sample_dict)

    constant_cols_list = []
    for col in df.columns:
        if df[col].nunique(dropna=False) == 1:
            val = df[col].iloc[0]
            constant_cols_list.append({
                "name": str(col),
                "value": str(val) if pd.notna(val) else "Boş",
                "ratio": 100.0
            })
    constant_col_names = {c["name"] for c in constant_cols_list}

    cardinality_cols_list = []
    for col in df.columns:
        if str(col) not in constant_col_names:
            is_num = pd.api.types.is_numeric_dtype(df[col])
            if not is_num or df[col].nunique() < 50:
                uniq = int(df[col].nunique())
                ratio = (uniq / rows) if rows > 0 else 0.0
                label = "Yuksek" if (ratio > 0.5 and uniq > 5) else "Dusuk"
                cardinality_cols_list.append({
                    "name": str(col),
                    "unique": uniq,
                    "label": label
                })
    high_cardinality_count = sum(1 for c in cardinality_cols_list if c["label"] == "Yuksek")

    outlier_cols_list = []
    total_outliers = 0
    numeric_df = df.select_dtypes(include=[np.number])
    for col in numeric_df.columns:
        s = df[col].dropna()
        if len(s) >= 4:
            q1 = float(s.quantile(0.25))
            q3 = float(s.quantile(0.75))
            iqr = q3 - q1
            if iqr > 0:
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                out_cnt = int(((s < lower) | (s > upper)).sum())
                if out_cnt > 0:
                    total_outliers += out_cnt
                    outlier_cols_list.append({
                        "name": str(col),
                        "count": out_cnt,
                        "ratio": round((out_cnt / rows) * 100, 2)
                    })
    outlier_cols_list.sort(key=lambda x: x["count"], reverse=True)
    outlier_frac = (total_outliers / rows) if rows > 0 else 0.0
    overall_outlier_rate = round(outlier_frac * 100, 2)
    outlier_summary = "Belirgin" if (overall_outlier_rate > 1.0 or any(c["ratio"] > 1.0 for c in outlier_cols_list)) else "Minimal"

    dtypes_analysis_list = []
    type_issues_count = 0
    for col in df.columns:
        col_dtype = str(df[col].dtype)
        non_null = df[col].dropna()
        samples = [str(x) for x in non_null.head(2).tolist()] if len(non_null) > 0 else ["—"]

        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            if len(non_null) > 0:
                num_series = pd.to_numeric(non_null, errors="coerce")
                valid_num_pct = num_series.notna().sum() / len(non_null)
                if valid_num_pct >= 0.8:
                    valid_nums = num_series.dropna()
                    is_int = (valid_nums.astype(int) == valid_nums).all() if len(valid_nums) > 0 else False
                    suggestion = "Sayısal (int64) olabilir" if is_int else "Sayısal (float64) olabilir"
                    ok = False
                    type_issues_count += 1
                else:
                    date_series = pd.to_datetime(non_null, errors="coerce", format="mixed")
                    valid_date_pct = date_series.notna().sum() / len(non_null)
                    if valid_date_pct >= 0.8:
                        suggestion = "Tarih (datetime) olabilir"
                        ok = False
                        type_issues_count += 1
                    else:
                        suggestion = "Kategorik uygun görünüyor"
                        ok = True
            else:
                suggestion = "Kategorik uygun görünüyor"
                ok = True
        else:
            suggestion = "Uygun görünüyor"
            ok = True

        dtypes_analysis_list.append({
            "name": str(col),
            "current": col_dtype,
            "samples": samples,
            "suggestion": suggestion,
            "ok": ok
        })

    penalty_missing = min(int(round(missing_frac * 50)), 30)
    penalty_dup = min(int(round(dup_frac * 100)), 10)
    penalty_type = min(type_issues_count * 4, 15)
    penalty_const = min(len(constant_cols_list) * 5, 10)
    penalty_card = min(high_cardinality_count * 3, 9)
    penalty_outlier = min(int(round(outlier_frac * 40)), 10)

    total_penalty = penalty_missing + penalty_dup + penalty_type + penalty_const + penalty_card + penalty_outlier
    score = max(0, int(100 - total_penalty))

    if score >= 85:
        score_status = "iyi_durumda"
    elif score >= 70:
        score_status = "iyilestirme_gerekli"
    else:
        score_status = "zayif"

    score_breakdown = [
        {"component": "Kayıp Veri", "formula": "Eksik oran × 50 (maks 30)", "value": f"%{overall_missing_rate:.1f}", "penalty": penalty_missing},
        {"component": "Tekrarlanan Kayıt", "formula": "Yinelenen oran × 100 (maks 10)", "value": f"%{dup_rate:.2f}", "penalty": penalty_dup},
        {"component": "Veri Tipi Sorunları", "formula": "Sorunlu kolon × 4 (maks 15)", "value": f"{type_issues_count} Kolon", "penalty": penalty_type},
        {"component": "Sabit Kolonlar", "formula": "Sabit kolon × 5 (maks 10)", "value": f"{len(constant_cols_list)} Kolon", "penalty": penalty_const},
        {"component": "Yüksek Kardinalite", "formula": "Yüksek kardinalite × 3 (maks 9)", "value": f"{high_cardinality_count} Kolon", "penalty": penalty_card},
        {"component": "Aykırı Değerler", "formula": "Aykırı oran × 40 (maks 10)", "value": f"%{overall_outlier_rate:.2f}", "penalty": penalty_outlier},
    ]

    quality_data = {
        "filename": _filename,
        "rows": rows,
        "columns": cols,
        "upload_time": _upload_timestamp or "Şimdi",
        "score": score,
        "score_status": score_status,
        "score_breakdown": score_breakdown,
        "metrics": {
            "missing_rate": overall_missing_rate,
            "duplicate_rate": dup_rate,
            "type_issues": type_issues_count,
            "constant_cols": len(constant_cols_list),
            "high_cardinality_cols": high_cardinality_count,
            "outlier_summary": outlier_summary
        },
        "missing": {
            "columns": missing_cols_list,
            "total_missing": total_missing,
            "rate": overall_missing_rate
        },
        "duplicates": {
            "count": dup_count,
            "rate": dup_rate,
            "samples": dup_samples
        },
        "cardinality": {
            "columns": cardinality_cols_list
        },
        "constant_cols": constant_cols_list,
        "outliers": {
            "columns": outlier_cols_list[:2],
            "all_columns": outlier_cols_list,
            "total_outliers": total_outliers,
            "overall_rate": overall_outlier_rate,
            "method": "IQR"
        },
        "dtypes": dtypes_analysis_list
    }

    return JSONResponse(content=quality_data)


@app.get("/api/preprocessing")
async def get_preprocessing_data():
    global _original_df, _working_df, _filename, _ops_stack

    if _original_df is None or _working_df is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Önce bir CSV yükleyin."
        )

    missing_cols = [
        {"name": str(c), "count": int(_working_df[c].isna().sum())}
        for c in _working_df.columns if _working_df[c].isna().sum() > 0
    ]

    res = {
        "filename": _filename,
        "original": {
            "rows": len(_original_df),
            "columns": len(_original_df.columns)
        },
        "processed": {
            "rows": len(_working_df),
            "columns": len(_working_df.columns),
            "missing": int(_working_df.isna().sum().sum())
        },
        "duplicates": int(_working_df.duplicated().sum()),
        "missing_summary": {
            "total_missing_cells": int(_working_df.isna().sum().sum()),
            "columns_with_missing": missing_cols
        },
        "schema": get_schema_data(),
        "history": list(reversed(_ops_stack)),
        "preview": get_preview_rows(_working_df, 10),
        "columns_list": list(_working_df.columns)
    }
    return JSONResponse(content=res)


@app.post("/api/preprocessing/apply")
async def apply_preprocessing_op(payload: Dict[str, Any] = Body(...)):
    global _original_df, _working_df, _ops_stack, _upload_timestamp

    if _original_df is None or _working_df is None:
        raise HTTPException(status_code=409, detail="Önce bir CSV yükleyin.")

    op = payload.get("op")
    col = payload.get("column")
    method = payload.get("method")
    target_type = payload.get("target_type")

    before_rows = len(_working_df)
    before_cols = len(_working_df.columns)
    before_missing = int(_working_df.isna().sum().sum())

    samples_before = []
    if col and col in _working_df.columns:
        affected_idx = _working_df[_working_df[col].isna()].index if op == "fill_missing" else _working_df.index[:3]
        sample_subset = _working_df.loc[affected_idx[:3]] if len(affected_idx) > 0 else _working_df.head(3)
        cols_to_show = [c for c in [list(_working_df.columns)[0], col] if c in _working_df.columns]
        if len(cols_to_show) < 3 and len(_working_df.columns) > len(cols_to_show):
            cols_to_show.extend([c for c in _working_df.columns if c not in cols_to_show][:2])
        samples_before = [{str(k): clean_val_for_json(v) for k, v in row.items()} for _, row in sample_subset[cols_to_show].iterrows()]

    current_time = datetime.now().strftime("%H:%M")
    op_desc = ""
    icon_name = "transform"
    icon_bg = "bg-secondary-container"
    icon_color = "text-on-secondary-container"

    if op == "fill_missing":
        if not col or col not in _working_df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz sütun adı.")

        is_num = pd.api.types.is_numeric_dtype(_working_df[col])

        if method in ["mean", "median"] and not is_num:
            raise HTTPException(status_code=400, detail="Ortalama ve Medyan yalnızca sayısal sütunlara uygulanabilir.")

        if method == "median":
            val_name = "medyan"
        elif method == "mean":
            val_name = "ortalama"
        elif method == "mode":
            val_name = "mod"
        elif method == "unknown":
            val_name = "'Unknown'"
        elif method == "drop_rows":
            val_name = "eksik satırları silme"
        else:
            raise HTTPException(status_code=400, detail="Geçersiz doldurma yöntemi.")

        op_desc = f"{col} sütunu {val_name} ile dolduruldu" if method != "drop_rows" else f"{col} sütunundaki eksik satırlar kaldırıldı"
        icon_name = "healing"
        icon_bg = "bg-primary-container/20"
        icon_color = "text-primary"

    elif op == "drop_duplicates":
        dup_count = int(_working_df.duplicated().sum())
        op_desc = f"{dup_count} tekrarlayan satır kaldırıldı"
        icon_name = "delete"
        icon_bg = "bg-error-container"
        icon_color = "text-on-error-container"

    elif op == "drop_column":
        if not col:
            raise HTTPException(status_code=400, detail="Sütun belirtilmedi.")
        op_desc = f"{col} sütunu kaldırıldı"
        icon_name = "visibility_off"
        icon_bg = "bg-surface-variant"
        icon_color = "text-on-surface-variant"

    elif op == "keep_column":
        if not col:
            raise HTTPException(status_code=400, detail="Sütun belirtilmedi.")
        op_desc = f"{col} sütunu geri eklendi"
        icon_name = "visibility"
        icon_bg = "bg-secondary-container"
        icon_color = "text-on-secondary-container"

    elif op == "convert_type":
        if not col or col not in _working_df.columns or not target_type:
            raise HTTPException(status_code=400, detail="Geçersiz tip dönüşüm parametreleri.")

        old_type = str(_working_df[col].dtype).upper()
        target_upper = target_type.upper()

        try:
            if target_type == "int64":
                num_s = pd.to_numeric(_working_df[col], errors="raise")
                if (num_s % 1 != 0).any():
                    raise ValueError("Ondalıklı değerler içeriyor.")
            elif target_type == "float64":
                pd.to_numeric(_working_df[col], errors="raise")
            elif target_type == "datetime":
                pd.to_datetime(_working_df[col], errors="raise", format="mixed")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Dönüştürülemedi: Sütundaki bazı değerler {target_upper} tipine uygun değil ({str(e)})"
            )

        op_desc = f"Tip dönüşümü: {col} {old_type} → {target_upper}"
        icon_name = "transform"
        icon_bg = "bg-secondary-container"
        icon_color = "text-on-secondary-container"
    else:
        raise HTTPException(status_code=400, detail="Bilinmeyen işlem türü.")

    new_op_entry = {
        "op": op,
        "column": col,
        "method": method,
        "target_type": target_type,
        "description": op_desc,
        "details": f"{col}" if col else "",
        "time": current_time,
        "icon": icon_name,
        "icon_bg": icon_bg,
        "icon_color": icon_color
    }

    _ops_stack.append(new_op_entry)

    try:
        _working_df = replay_operations()
    except Exception as err:
        _ops_stack.pop()
        raise HTTPException(status_code=422, detail=f"İşlem uygulanamadı: {str(err)}")

    after_rows = len(_working_df)
    after_cols = len(_working_df.columns)
    after_missing = int(_working_df.isna().sum().sum())

    samples_after = []
    if col and col in _working_df.columns and len(samples_before) > 0:
        cols_shown = list(samples_before[0].keys())
        cols_to_use = [c for c in cols_shown if c in _working_df.columns]
        if len(cols_to_use) > 0:
            sample_sub_after = _working_df.loc[sample_subset.index[:len(samples_before)]] if 'sample_subset' in locals() else _working_df.head(len(samples_before))
            samples_after = [{str(k): clean_val_for_json(v) for k, v in row.items()} for _, row in sample_sub_after[cols_to_use].iterrows()]

    missing_cols = [
        {"name": str(c), "count": int(_working_df[c].isna().sum())}
        for c in _working_df.columns if _working_df[c].isna().sum() > 0
    ]

    res = {
        "status": "success",
        "operation": op_desc,
        "before": {"rows": before_rows, "columns": before_cols, "missing": before_missing},
        "after": {"rows": after_rows, "columns": after_cols, "missing": after_missing},
        "samples_before": samples_before,
        "samples_after": samples_after,
        "processed": {
            "rows": after_rows,
            "columns": after_cols,
            "missing": after_missing
        },
        "duplicates": int(_working_df.duplicated().sum()),
        "missing_summary": {
            "total_missing_cells": after_missing,
            "columns_with_missing": missing_cols
        },
        "schema": get_schema_data(),
        "history": list(reversed(_ops_stack)),
        "preview": get_preview_rows(_working_df, 10),
        "columns_list": list(_working_df.columns)
    }
    return JSONResponse(content=res)


@app.post("/api/preprocessing/undo")
async def undo_preprocessing_op():
    global _original_df, _working_df, _ops_stack

    if _original_df is None:
        raise HTTPException(status_code=409, detail="Önce bir CSV yükleyin.")

    if len(_ops_stack) > 1:
        popped = _ops_stack.pop()
        undone_desc = f"Geri alındı: {popped.get('description', '')}"
    else:
        undone_desc = "Geri alınacak başka işlem yok."

    _working_df = replay_operations()

    missing_cols = [
        {"name": str(c), "count": int(_working_df[c].isna().sum())}
        for c in _working_df.columns if _working_df[c].isna().sum() > 0
    ]

    res = {
        "status": "success",
        "operation": undone_desc,
        "processed": {
            "rows": len(_working_df),
            "columns": len(_working_df.columns),
            "missing": int(_working_df.isna().sum().sum())
        },
        "duplicates": int(_working_df.duplicated().sum()),
        "missing_summary": {
            "total_missing_cells": int(_working_df.isna().sum().sum()),
            "columns_with_missing": missing_cols
        },
        "schema": get_schema_data(),
        "history": list(reversed(_ops_stack)),
        "preview": get_preview_rows(_working_df, 10),
        "columns_list": list(_working_df.columns)
    }
    return JSONResponse(content=res)


@app.post("/api/preprocessing/reset")
async def reset_preprocessing():
    global _original_df, _working_df, _ops_stack, _upload_timestamp

    if _original_df is None:
        raise HTTPException(status_code=409, detail="Önce bir CSV yükleyin.")

    _working_df = _original_df.copy()
    _ops_stack = [
        {
            "op": "initial",
            "description": "Orijinal veri yüklendi",
            "details": f"{len(_original_df):,} satır × {len(_original_df.columns)} sütun".replace(",", "."),
            "time": _upload_timestamp or datetime.now().strftime("%H:%M"),
            "icon": "upload_file",
            "icon_bg": "bg-slate-gray/10",
            "icon_color": "text-slate-gray"
        }
    ]

    missing_cols = [
        {"name": str(c), "count": int(_working_df[c].isna().sum())}
        for c in _working_df.columns if _working_df[c].isna().sum() > 0
    ]

    res = {
        "status": "success",
        "operation": "Tüm işlemler sıfırlandı, orijinal veriye dönüldü",
        "processed": {
            "rows": len(_working_df),
            "columns": len(_working_df.columns),
            "missing": int(_working_df.isna().sum().sum())
        },
        "duplicates": int(_working_df.duplicated().sum()),
        "missing_summary": {
            "total_missing_cells": int(_working_df.isna().sum().sum()),
            "columns_with_missing": missing_cols
        },
        "schema": get_schema_data(),
        "history": list(reversed(_ops_stack)),
        "preview": get_preview_rows(_working_df, 10),
        "columns_list": list(_working_df.columns)
    }
    return JSONResponse(content=res)


@app.get("/api/preprocessing/download")
async def download_cleaned_csv():
    global _working_df, _filename

    if _working_df is None or len(_working_df) == 0:
        raise HTTPException(status_code=409, detail="İndirilecek veri bulunamadı.")

    buffer = io.StringIO()
    _working_df.to_csv(buffer, index=False, encoding="utf-8-sig")
    buffer.seek(0)

    download_name = "temizlenmis_veri.csv"
    if _filename:
        base_name = _filename.rsplit(".", 1)[0]
        download_name = f"{base_name}_temizlenmis.csv"

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={download_name}"
        }
    )


# VISUALIZATION ENDPOINTS
@app.get("/api/visualization/overview")
async def get_visualization_overview():
    global _working_df, _original_df

    df = _working_df if _working_df is not None else _original_df
    if df is None or len(df) == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Önce bir CSV yükleyin."
        )

    numeric_cols = [str(c) for c in df.select_dtypes(include=[np.number]).columns]
    categorical_cols = [str(c) for c in df.columns if str(c) not in numeric_cols]

    stats = {}
    for col in numeric_cols:
        s = df[col].dropna()
        if len(s) > 0:
            stats[col] = {
                "count": int(len(s)),
                "mean": round(float(s.mean()), 2),
                "median": round(float(s.median()), 2),
                "std": round(float(s.std()), 2) if len(s) > 1 else 0.0,
                "min": round(float(s.min()), 2),
                "max": round(float(s.max()), 2)
            }
        else:
            stats[col] = {"count": 0, "mean": 0.0, "median": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}

    cat_summary = {}
    for col in categorical_cols:
        vc = df[col].dropna().value_counts().head(10)
        total_valid = max(1, len(df[col].dropna()))
        cat_summary[col] = [
            {"value": str(k), "count": int(v), "ratio": round((v / total_valid) * 100, 2)}
            for k, v in vc.items()
        ]

    corr_cols = numeric_cols[:15]
    corr_matrix = []
    strongest_pairs = []

    if len(corr_cols) >= 2:
        corr_df = df[corr_cols].corr()
        for r_idx, row_col in enumerate(corr_cols):
            row_vals = []
            for c_idx, col_name in enumerate(corr_cols):
                val = corr_df.loc[row_col, col_name]
                clean_corr = 0.0 if (pd.isna(val) or np.isnan(val)) else round(float(val), 2)
                row_vals.append(clean_corr)
                if r_idx < c_idx and not np.isnan(val):
                    strongest_pairs.append({
                        "a": row_col,
                        "b": col_name,
                        "corr": round(float(val), 2),
                        "abs_corr": round(abs(float(val)), 2)
                    })
            corr_matrix.append(row_vals)
        strongest_pairs.sort(key=lambda x: x["abs_corr"], reverse=True)

    suggestions = []
    # 1. Histogram suggestion
    if len(numeric_cols) > 0:
        first_num = numeric_cols[0]
        suggestions.append({
            "type": "histogram",
            "column": first_num,
            "title": f"{first_num} Dağılımı",
            "reason": "Sayısal Dağılım"
        })

    # 2. Categorical bar suggestion
    if len(categorical_cols) > 0:
        first_cat = categorical_cols[0]
        suggestions.append({
            "type": "bar",
            "column": first_cat,
            "title": f"{first_cat} Kategorileri",
            "reason": "Kategori Sayıları"
        })

    # 3. Scatter plot suggestion for strongest correlation
    if len(strongest_pairs) > 0:
        best_pair = strongest_pairs[0]
        suggestions.append({
            "type": "scatter",
            "x": best_pair["a"],
            "y": best_pair["b"],
            "title": f"{best_pair['a']} × {best_pair['b']}",
            "reason": f"En Güçlü Korelasyon (r = {best_pair['corr']})"
        })

    # 4. Grouped boxplot if cat + num exist
    if len(categorical_cols) > 0 and len(numeric_cols) > 0:
        c_col = categorical_cols[0]
        n_col = numeric_cols[0]
        suggestions.append({
            "type": "grouped_boxplot",
            "cat": c_col,
            "num": n_col,
            "title": f"{c_col}'a Göre {n_col}",
            "reason": "Kategori Bazlı Dağılım"
        })

    # 5. Second numeric histogram/boxplot if available
    if len(numeric_cols) > 1:
        second_num = numeric_cols[1]
        suggestions.append({
            "type": "boxplot",
            "column": second_num,
            "title": f"{second_num} Kutu Grafiği",
            "reason": "Uç Değer ve Çeyreklikler"
        })

    # 6. Second categorical bar or second scatter
    if len(categorical_cols) > 1:
        second_cat = categorical_cols[1]
        suggestions.append({
            "type": "bar",
            "column": second_cat,
            "title": f"{second_cat} Dağılımı",
            "reason": "Kategori Frekansları"
        })
    elif len(strongest_pairs) > 1:
        pair2 = strongest_pairs[1]
        suggestions.append({
            "type": "scatter",
            "x": pair2["a"],
            "y": pair2["b"],
            "title": f"{pair2['a']} × {pair2['b']}",
            "reason": f"Korelasyon Analizi (r = {pair2['corr']})"
        })

    return JSONResponse(content={
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "stats": stats,
        "categorical_summary": cat_summary,
        "correlation": {
            "columns": corr_cols,
            "matrix": corr_matrix,
            "strongest": strongest_pairs[:5]
        },
        "suggestions": suggestions
    })


@app.get("/api/visualization/chart")
async def get_visualization_chart(
    type: str = Query(...),
    column: Optional[str] = Query(None),
    x: Optional[str] = Query(None),
    y: Optional[str] = Query(None),
    cat: Optional[str] = Query(None),
    num: Optional[str] = Query(None)
):
    global _working_df, _original_df

    df = _working_df if _working_df is not None else _original_df
    if df is None or len(df) == 0:
        raise HTTPException(status_code=409, detail="Önce bir CSV yükleyin.")

    if type == "histogram":
        if not column or column not in df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz sütun adı.")
        s = pd.to_numeric(df[column], errors="coerce").dropna()
        if len(s) == 0:
            return JSONResponse(content={"bins": [], "bin_labels": [], "counts": []})

        num_bins = min(25, max(8, int(len(s)**0.5)))
        counts, bin_edges = np.histogram(s, bins=num_bins)
        bin_labels = [f"{bin_edges[i]:.1f} - {bin_edges[i+1]:.1f}" for i in range(len(counts))]
        bins = [round(float(b), 2) for b in bin_edges]

        return JSONResponse(content={
            "column": column,
            "bins": bins,
            "bin_labels": bin_labels,
            "counts": [int(c) for c in counts]
        })

    elif type == "boxplot":
        if not column or column not in df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz sütun adı.")
        s = pd.to_numeric(df[column], errors="coerce").dropna()
        if len(s) == 0:
            return JSONResponse(content={"box": [0, 0, 0, 0, 0], "outliers": []})

        q1 = float(s.quantile(0.25))
        med = float(s.quantile(0.50))
        q3 = float(s.quantile(0.75))
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        valid_points = s[(s >= lower_bound) & (s <= upper_bound)]
        whisker_min = float(valid_points.min()) if len(valid_points) > 0 else float(s.min())
        whisker_max = float(valid_points.max()) if len(valid_points) > 0 else float(s.max())

        outliers = [round(float(v), 2) for v in s[(s < lower_bound) | (s > upper_bound)].tolist()]

        return JSONResponse(content={
            "column": column,
            "box": [round(whisker_min, 2), round(q1, 2), round(med, 2), round(q3, 2), round(whisker_max, 2)],
            "outliers": outliers
        })

    elif type == "bar":
        if not column or column not in df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz sütun adı.")
        s = df[column].dropna()
        vc = s.value_counts().head(15)
        total = max(1, len(s))
        items = [
            {"value": str(k), "count": int(v), "ratio": round((v / total) * 100, 2)}
            for k, v in vc.items()
        ]
        return JSONResponse(content={"column": column, "items": items})

    elif type == "scatter":
        if not x or not y or x not in df.columns or y not in df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz X veya Y sütun adı.")

        sub = df[[x, y]].dropna()
        x_vals = pd.to_numeric(sub[x], errors="coerce")
        y_vals = pd.to_numeric(sub[y], errors="coerce")
        mask = x_vals.notna() & y_vals.notna()

        x_clean = [round(float(v), 2) for v in x_vals[mask].tolist()]
        y_clean = [round(float(v), 2) for v in y_vals[mask].tolist()]

        return JSONResponse(content={
            "x_name": x,
            "y_name": y,
            "x": x_clean,
            "y": y_clean
        })

    elif type == "grouped_boxplot":
        if not cat or not num or cat not in df.columns or num not in df.columns:
            raise HTTPException(status_code=400, detail="Geçersiz kategori veya sayısal sütun adı.")

        sub = df[[cat, num]].dropna()
        top_cats = sub[cat].value_counts().head(8).index.tolist()

        groups = []
        for c_val in top_cats:
            group_s = pd.to_numeric(sub[sub[cat] == c_val][num], errors="coerce").dropna()
            if len(group_s) > 0:
                q1 = float(group_s.quantile(0.25))
                med = float(group_s.quantile(0.50))
                q3 = float(group_s.quantile(0.75))
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                valid_p = group_s[(group_s >= lower) & (group_s <= upper)]
                w_min = float(valid_p.min()) if len(valid_p) > 0 else float(group_s.min())
                w_max = float(valid_p.max()) if len(valid_p) > 0 else float(group_s.max())
                outliers = [round(float(v), 2) for v in group_s[(group_s < lower) | (group_s > upper)].tolist()]
                groups.append({
                    "name": str(c_val),
                    "box": [round(w_min, 2), round(q1, 2), round(med, 2), round(q3, 2), round(w_max, 2)],
                    "outliers": outliers
                })

        return JSONResponse(content={
            "cat": cat,
            "num": num,
            "groups": groups
        })

    else:
        raise HTTPException(status_code=400, detail="Bilinmeyen grafik türü.")


@app.get("/api/active-dataset")
async def get_active_dataset():
    if not active_dataset:
        return JSONResponse(content={"active": False, "data": None})
    return JSONResponse(content={"active": True, "data": active_dataset})


@app.delete("/api/reset")
async def reset_dataset():
    global active_dataset, _original_df, _working_df, _filename, _size_bytes, _upload_timestamp, _ops_stack
    active_dataset = {}
    _original_df = None
    _working_df = None
    _filename = None
    _size_bytes = None
    _upload_timestamp = None
    _ops_stack = []
    return JSONResponse(content={"status": "success", "message": "Veri seti sıfırlandı."})


app.mount("/static", StaticFiles(directory="static"), name="static")
