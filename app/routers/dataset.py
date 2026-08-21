import datetime
from typing import Optional
import numpy as np
import pandas as pd
from fastapi import APIRouter, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse
from app.core.config import MAX_FILE_SIZE
from app.core.state import state, clean_val_for_json
from app.services.parser_service import parse_csv_content

router = APIRouter(tags=["dataset"])


@router.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
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
        "parse_report": parse_report if parse_report.get("skipped_rows", 0) > 0 else None,
    }

    state.active_dataset = result_data
    state.active_df_cache = df
    state.original_df_cache = df.copy()
    state.processed_df_cache = df.copy()
    state.dropped_columns = set()
    now_time = datetime.datetime.now().strftime("%H:%M")
    state.preprocessing_history_stack = [{
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


@router.get("/api/session")
async def get_session():
    if not state.active_dataset:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aktif veri seti bulunamadı."
        )
    return JSONResponse(content=state.active_dataset)


@router.get("/api/active-dataset")
async def get_active_dataset():
    if not state.active_dataset:
        return JSONResponse(content={"active": False, "data": None})
    return JSONResponse(content={"active": True, "data": state.active_dataset})


@router.get("/api/search")
async def search_dataset(q: Optional[str] = None, limit: int = 10):
    if state.active_df_cache is None or not state.active_dataset:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aktif veri seti bulunamadı."
        )

    df = state.active_df_cache
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


@router.post("/api/reset")
@router.delete("/api/reset")
async def reset_dataset():
    state.reset_all()
    return JSONResponse(content={"status": "success", "message": "Veri seti sıfırlandı."})
