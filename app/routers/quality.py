from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from app.core.state import state
from app.services.quality_service import compute_quality_report

router = APIRouter(tags=["quality"])


@router.get("/api/quality")
async def get_quality_report():
    if not state.active_dataset:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Veri seti bulunamadı. Lütfen önce bir CSV dosyası yükleyin."
        )

    df_raw = state.original_df_cache if state.original_df_cache is not None else state.active_df_cache
    df_proc = state.processed_df_cache if state.processed_df_cache is not None else state.active_df_cache

    if df_raw is None and df_proc is None:
        rows = state.active_dataset.get("rows", 0)
        cols = state.active_dataset.get("columns", 0)
        missing = state.active_dataset.get("missing", 0)
        duplicates = state.active_dataset.get("duplicates", 0)
        missing_rate = round((missing / max(1, rows * cols)) * 100, 2)
        duplicate_rate = round((duplicates / max(1, rows)) * 100, 2)
        score = max(0, 100 - int(missing_rate * 1.5) - int(duplicate_rate * 2))
        status_text = "iyi" if score >= 85 else ("iyilestirme_gerekli" if score >= 70 else "zayif")
        return JSONResponse(content={
            "filename": state.active_dataset.get("filename", "veri.csv"),
            "rows": rows,
            "columns": cols,
            "upload_time": state.active_dataset.get("upload_time", "Bugün"),
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

    if state.dropped_columns and df_proc is not None:
        active_cols = [c for c in df_proc.columns if c not in state.dropped_columns]
        df_proc_active = df_proc[active_cols]
    else:
        df_proc_active = df_proc

    raw_report = compute_quality_report(df_raw.copy(), baseline_rows) if df_raw is not None else {}
    proc_report = compute_quality_report(df_proc_active.copy(), baseline_rows) if df_proc_active is not None else raw_report

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
        "filename": state.active_dataset.get("filename", "veri.csv"),
        "upload_time": state.active_dataset.get("upload_time", "14:32"),
        "comparison": comparison,
        **proc_report
    }

    return JSONResponse(content=response_data)
