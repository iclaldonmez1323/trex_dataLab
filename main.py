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


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    global active_dataset

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

    active_dataset = result_data
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


@app.post("/api/reset")
@app.delete("/api/reset")
async def reset_dataset():
    global active_dataset
    active_dataset = {}
    return JSONResponse(content={"status": "success", "message": "Veri seti sıfırlandı."})


app.mount("/static", StaticFiles(directory="static"), name="static")
