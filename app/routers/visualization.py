from typing import Optional
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from app.services.visualization_service import (
    get_current_active_df,
    classify_columns,
    decide_chart_plan,
    pretty_label
)

router = APIRouter(tags=["visualization"])


@router.get("/api/visualization/overview")
async def get_visualization_overview():
    curr_df = get_current_active_df()
    classification = classify_columns(curr_df)
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

    # Dynamic suggestions
    suggestions = []

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

    if len(categorical_cols) > 0:
        plan_bar = decide_chart_plan(categorical_cols[0], None, curr_df)
        suggestions.append({
            "type": "bar",
            "column": str(categorical_cols[0]),
            "title": plan_bar["title"],
            "reason": plan_bar["reason"],
            "plan": plan_bar
        })

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


@router.get("/api/visualization/focus")
async def get_visualization_focus(column: str):
    curr_df = get_current_active_df()
    if column not in curr_df.columns:
        raise HTTPException(status_code=400, detail="Geçersiz odak değişkeni.")

    classification = classify_columns(curr_df)
    numeric_cols = classification["numeric"]
    datetime_cols = classification["datetime"]
    categorical_cols = classification["categorical"]

    is_numeric = column in numeric_cols
    is_datetime = column in datetime_cols

    suggestions = []
    univariate = None
    note = None

    if is_datetime:
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
        plan_hist = decide_chart_plan(column, None, curr_df)
        suggestions.append({
            "type": "histogram",
            "column": str(column),
            "title": plan_hist["title"],
            "reason": "Sayısal Dağılım (Odak)",
            "plan": plan_hist
        })
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
        suggestions.append({
            "type": "boxplot",
            "column": str(column),
            "title": f"{pretty_label(column)} Kutu Grafiği",
            "reason": "Uç Değer ve Çeyreklikler"
        })

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
        plan_bar = decide_chart_plan(column, None, curr_df)
        suggestions.append({
            "type": "bar",
            "column": str(column),
            "title": plan_bar["title"],
            "reason": "Kategori Sayıları (Odak)",
            "plan": plan_bar
        })
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


@router.get("/api/visualization/chart")
async def get_visualization_chart(
    type: str,
    column: Optional[str] = None,
    x: Optional[str] = None,
    y: Optional[str] = None,
    cat: Optional[str] = None,
    num: Optional[str] = None
):
    curr_df = get_current_active_df()

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
