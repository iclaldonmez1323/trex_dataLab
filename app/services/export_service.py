from typing import Tuple
import pandas as pd
from fastapi import HTTPException, status
from app.core.state import state


def get_export_csv_bytes() -> Tuple[bytes, str]:
    df = state.get_current_df()
    if df is None or not state.active_dataset:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="İndirilecek veri seti bulunamadı.")

    active_cols = state.get_active_columns()
    download_df = df[active_cols]

    csv_bytes = download_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    orig_name = state.active_dataset.get("filename", "veri.csv")
    base = orig_name.rsplit(".", 1)[0]
    export_name = f"{base}_aktarilan.csv"

    return csv_bytes, export_name


def get_cleaned_csv_bytes() -> Tuple[bytes, str]:
    if state.processed_df_cache is None or not state.active_dataset:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="İndirilecek veri seti bulunamadı."
        )

    active_cols = state.get_active_columns()
    download_df = state.processed_df_cache[active_cols]
    
    csv_bytes = download_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    orig_name = state.active_dataset.get("filename", "veri.csv")
    cleaned_name = f"temizlenmis_{orig_name}"

    return csv_bytes, cleaned_name
