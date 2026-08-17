import io
from typing import Dict, Any, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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
async def serve_index():
    return FileResponse("static/index.html")


@app.get("/data-quality")
async def serve_data_quality():
    return FileResponse("static/data-quality.html")


@app.get("/preprocessing")
async def serve_preprocessing():
    return FileResponse("static/preprocessing.html")


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
        is_high = (unique_cnt > rows_count * 0.4 and unique_cnt > 20) or (unique_cnt > 500)
        label = f"Yüksek ({unique_cnt})" if is_high else f"Düşük ({unique_cnt})"
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
            q25 = valid_series.quantile(0.25)
            q75 = valid_series.quantile(0.75)
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
    outlier_rate = round((total_outliers / max(1, rows_count * max(1, len(numeric_df.columns)))) * 100, 2)
    outlier_summary = "Belirgin" if total_outliers > 0 else "Minimal"

    # Data Types Check & Suggestions
    dtypes_list = []
    type_issues_count = 0
    for col in df.columns:
        curr_dtype = str(df[col].dtype)
        samples = [str(clean_val_for_json(v)) for v in df[col].dropna().head(3).tolist()]
        sample_str = ", ".join([f'"{s}"' if not s.replace('.', '', 1).isdigit() else s for s in samples])
        
        ok = True
        suggestion = "Uygun görünüyor"
        
        if df[col].dtype == object or str(df[col].dtype) == "string":
            # Check if numeric
            non_na = df[col].dropna()
            if len(non_na) > 0:
                try:
                    pd.to_numeric(non_na)
                    ok = False
                    suggestion = "Sayısal (float/int) olabilir"
                    type_issues_count += 1
                except Exception:
                    # Check if date
                    try:
                        pd.to_datetime(non_na, format="%Y-%m-%d", errors="raise")
                        ok = False
                        suggestion = "Tarih (datetime) olabilir"
                        type_issues_count += 1
                    except Exception:
                        pass
        
        dtypes_list.append({
            "name": str(col),
            "current": curr_dtype,
            "samples": samples,
            "sample_str": sample_str,
            "suggestion": suggestion,
            "ok": ok
        })

    # Score and Penalties
    missing_penalty = min(30, int(round(missing_rate * 2)))
    duplicate_penalty = min(20, int(round(duplicate_rate * 5)))
    type_penalty = min(20, type_issues_count * 5)
    constant_penalty = min(15, len(constant_columns) * 5)
    outlier_penalty = min(15, min(15, int(round(outlier_rate * 3))))

    total_penalty = missing_penalty + duplicate_penalty + type_penalty + constant_penalty + outlier_penalty
    final_score = max(0, 100 - total_penalty)

    if final_score >= 85:
        score_status = "iyi"
    elif final_score >= 70:
        score_status = "iyilestirme_gerekli"
    else:
        score_status = "zayif"

    score_breakdown = [
        {"component": "Kayıp Veri", "formula": "Eksik oran × 2 (maks 30)", "value": f"%{missing_rate}", "penalty": missing_penalty},
        {"component": "Tekrarlanan Kayıt", "formula": "Tekrar oranı × 5 (maks 20)", "value": f"%{duplicate_rate}", "penalty": duplicate_penalty},
        {"component": "Veri Tipi Sorunları", "formula": "Sorunlu kolon × 5 (maks 20)", "value": f"{type_issues_count} Kolon", "penalty": type_penalty},
        {"component": "Sabit Kolonlar", "formula": "Sabit kolon × 5 (maks 15)", "value": f"{len(constant_columns)} Kolon", "penalty": constant_penalty},
        {"component": "Aykırı Değerler", "formula": "Aykırı oran × 3 (maks 15)", "value": f"%{outlier_rate}", "penalty": outlier_penalty}
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


app.mount("/static", StaticFiles(directory="static"), name="static")
