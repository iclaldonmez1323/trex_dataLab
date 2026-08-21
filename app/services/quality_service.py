import pandas as pd
import numpy as np
from app.core.state import clean_val_for_json


def compute_quality_report(df: pd.DataFrame, baseline_rows: int) -> dict:
    """Computes comprehensive data quality metrics, penalties, and quality score."""
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
