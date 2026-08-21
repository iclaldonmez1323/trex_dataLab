import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.core.state import state
from app.services.ml_service import (
    get_ml_dataframe,
    col_kind,
    auto_exclude_reason,
    top_class_ratio,
    detect_time_series,
    ml_data_source,
    run_ml_training
)

router = APIRouter(tags=["machine-learning"])


@router.get("/api/ml/config")
async def ml_config():
    df = get_ml_dataframe()
    if df is None or not state.active_dataset:
        return JSONResponse(status_code=404, content={"error": "Aktif bir veri seti yok. Önce bir CSV yükleyin."})

    columns = []
    missing_counts = {}
    auto_excluded = []
    text_cols = []
    datetime_cols = []
    n_high_card = 0

    for col in df.columns:
        s = df[col]
        kind = col_kind(s)
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

        reason = auto_exclude_reason(col, s, kind)
        ex = reason is not None
        columns.append({
            "name": str(col),
            "dtype": str(s.dtype),
            "kind": kind,
            "avg_length": avg_len,
            "is_datetime": bool(kind == "datetime"),
            "unique_ratio": uniq_ratio,
            "missing_ratio": missing_ratio,
            "class_ratio": top_class_ratio(s) if kind == "categorical" else None,
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
    is_ts, ts_suspected, ts_col = detect_time_series(df)
    return JSONResponse(content={
        "active": True,
        "data_source": ml_data_source(),
        "is_time_series": is_ts,
        "time_series_suspected": ts_suspected,
        "time_column": ts_col,
        "filename": state.active_dataset.get("filename", "veri.csv"),
        "total_rows": total_rows,
        "columns": columns,
        "missing_counts": missing_counts,
        "default_target": first_num,
        "auto_excluded": auto_excluded,
        "feature_candidates": [c["name"] for c in columns],
        "profile": profile,
    })


@router.post("/api/ml/train")
def ml_train(req: dict):
    try:
        result = run_ml_training(req)
        status_code = result.get("status_code", 200)
        return JSONResponse(status_code=status_code, content=result)
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "success": False,
            "error": f"Model eğitimi sırasında hata oluştu: {str(e)}",
            "detail": str(e),
            "traceback": traceback.format_exc(),
        })
