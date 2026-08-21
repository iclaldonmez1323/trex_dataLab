import datetime
from typing import Dict, Any
import pandas as pd
from fastapi import HTTPException, status
from app.core.state import state, clean_val_for_json


def build_preprocessing_state_response() -> dict:
    """Builds and returns current preprocessing state and stats."""
    if not state.active_dataset or state.original_df_cache is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Veri seti bulunamadı. Lütfen önce bir CSV dosyası yükleyin."
        )

    orig_df = state.original_df_cache
    proc_df = state.processed_df_cache if state.processed_df_cache is not None else orig_df

    active_cols = [c for c in proc_df.columns if c not in state.dropped_columns]
    
    total_missing_cells = int(proc_df[active_cols].isna().sum().sum()) if active_cols else 0
    columns_with_missing = []
    for c in active_cols:
        cnt = int(proc_df[c].isna().sum())
        if cnt > 0:
            columns_with_missing.append({"name": str(c), "count": cnt})

    duplicate_count = int(proc_df[active_cols].duplicated().sum()) if active_cols and len(proc_df) > 0 else 0

    # Outliers (1.5xIQR method on numeric columns)
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
        is_kept = (c not in state.dropped_columns) and (c in proc_df.columns)
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
    for item in reversed(state.preprocessing_history_stack):
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
        "filename": state.active_dataset.get("filename", "veri.csv"),
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


def apply_preprocessing_op(payload: Dict[str, Any]) -> dict:
    """Executes a preprocessing operation and updates the state."""
    if state.processed_df_cache is None or not state.active_dataset:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aktif veri seti bulunamadı."
        )

    now_time = datetime.datetime.now().strftime("%H:%M")
    op = payload.get("op")
    column = payload.get("column")
    method = payload.get("method")
    target_type = payload.get("target_type")

    # Snapshot before operation
    prev_state = {
        "op": op,
        "column": column,
        "df": state.processed_df_cache.copy(),
        "dropped_cols": set(state.dropped_columns)
    }

    active_cols_before = [c for c in state.processed_df_cache.columns if c not in state.dropped_columns]
    before_stats = {
        "rows": int(len(state.processed_df_cache)),
        "columns": int(len(active_cols_before)),
        "missing": int(state.processed_df_cache[active_cols_before].isna().sum().sum()) if active_cols_before else 0
    }

    try:
        desc = ""
        icon = "healing"
        icon_bg = "bg-primary-container/20"
        icon_color = "text-primary"

        if op == "fill_missing":
            cols_to_fill = [column] if column else [c for c in state.processed_df_cache.columns if c not in state.dropped_columns and state.processed_df_cache[c].isna().any()]
            for c in cols_to_fill:
                if c not in state.processed_df_cache.columns:
                    continue
                if method == "mean":
                    if pd.api.types.is_numeric_dtype(state.processed_df_cache[c]):
                        state.processed_df_cache[c] = state.processed_df_cache[c].fillna(state.processed_df_cache[c].mean())
                elif method == "median":
                    if pd.api.types.is_numeric_dtype(state.processed_df_cache[c]):
                        state.processed_df_cache[c] = state.processed_df_cache[c].fillna(state.processed_df_cache[c].median())
                elif method == "mode":
                    mode_vals = state.processed_df_cache[c].mode()
                    if len(mode_vals) > 0:
                        state.processed_df_cache[c] = state.processed_df_cache[c].fillna(mode_vals[0])
                elif method == "unknown":
                    if pd.api.types.is_numeric_dtype(state.processed_df_cache[c]):
                        mode_vals = state.processed_df_cache[c].mode()
                        if len(mode_vals) > 0:
                            state.processed_df_cache[c] = state.processed_df_cache[c].fillna(mode_vals[0])
                    else:
                        state.processed_df_cache[c] = state.processed_df_cache[c].fillna("Unknown")
                elif method == "drop_rows":
                    state.processed_df_cache = state.processed_df_cache.dropna(subset=[c])

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
            active_cols = [c for c in state.processed_df_cache.columns if c not in state.dropped_columns]
            dup_cnt = int(state.processed_df_cache[active_cols].duplicated().sum()) if active_cols else 0
            state.processed_df_cache = state.processed_df_cache.drop_duplicates(subset=active_cols if active_cols else None)
            desc = f"{dup_cnt} tekrarlayan satır kaldırıldı"
            icon = "delete"
            icon_bg = "bg-error-container"
            icon_color = "text-on-error-container"

        elif op == "drop_column":
            if column:
                state.dropped_columns.add(column)
                desc = f"Sütun kaldırıldı: {column}"
                icon = "visibility_off"
                icon_bg = "bg-surface-variant"
                icon_color = "text-on-surface-variant"

        elif op == "keep_column":
            if column in state.dropped_columns:
                state.dropped_columns.remove(column)
                desc = f"Sütun geri eklendi: {column}"
                icon = "visibility"
                icon_bg = "bg-secondary-container"
                icon_color = "text-on-secondary-container"

        elif op == "convert_type":
            if column and column in state.processed_df_cache.columns and target_type:
                old_t = str(state.processed_df_cache[column].dtype)
                if target_type == "int64":
                    state.processed_df_cache[column] = pd.to_numeric(state.processed_df_cache[column], errors="coerce").fillna(0).astype("int64")
                elif target_type == "float64":
                    state.processed_df_cache[column] = pd.to_numeric(state.processed_df_cache[column], errors="coerce").astype("float64")
                elif target_type == "datetime":
                    state.processed_df_cache[column] = pd.to_datetime(state.processed_df_cache[column], errors="coerce")
                elif target_type == "category":
                    state.processed_df_cache[column] = state.processed_df_cache[column].astype("category")
                elif target_type == "string":
                    state.processed_df_cache[column] = state.processed_df_cache[column].astype("string")
                
                desc = f"Tip dönüşümü: {column} ({old_t.upper()} → {target_type.upper()})"
                icon = "transform"
                icon_bg = "bg-secondary-container"
                icon_color = "text-on-secondary-container"

        elif op == "outlier_management":
            method = method or "cap"
            selected_cols = payload.get("columns") or []

            def _is_id_like(c):
                low = str(c).lower()
                if "id" in low or "code" in low or "no" in low or "key" in low:
                    return True
                s = state.processed_df_cache[c]
                non_na = s.dropna()
                if len(non_na) == 0:
                    return False
                return int(non_na.nunique()) == int(len(non_na)) and pd.api.types.is_numeric_dtype(s)

            candidate_cols = [c for c in state.processed_df_cache.columns if c not in state.dropped_columns
                              and pd.api.types.is_numeric_dtype(state.processed_df_cache[c])
                              and not _is_id_like(c)]

            if selected_cols:
                numeric_cols = [c for c in state.processed_df_cache.columns
                                if c in selected_cols and c not in state.dropped_columns
                                and pd.api.types.is_numeric_dtype(state.processed_df_cache[c])]
            else:
                numeric_cols = candidate_cols

            if not numeric_cols:
                raise ValueError("İşlenecek sayısal sütun bulunamadı; aykırı değer işlemi uygulanamadı.")

            # 1.5×IQR bounds
            iqr_factor = 1.5
            bounds = {}
            for c in numeric_cols:
                series = pd.to_numeric(state.processed_df_cache[c], errors="coerce").dropna()
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

            outlier_flags = {}
            for c in numeric_cols:
                if c in bounds:
                    s = pd.to_numeric(state.processed_df_cache[c], errors="coerce")
                    outlier_flags[c] = (s < bounds[c]["iqr_lower"]) | (s > bounds[c]["iqr_upper"])
                else:
                    outlier_flags[c] = pd.Series(False, index=state.processed_df_cache.index)

            if method == "remove_iqr":
                start_rows = len(state.processed_df_cache)
                total_removed = 0
                for _ in range(5):
                    if len(state.processed_df_cache) == 0:
                        break
                    cur_flags = {}
                    for c in numeric_cols:
                        s = pd.to_numeric(state.processed_df_cache[c], errors="coerce")
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
                                cur_flags[c] = pd.Series(False, index=state.processed_df_cache.index)
                        else:
                            cur_flags[c] = pd.Series(False, index=state.processed_df_cache.index)

                    bad = pd.Series(False, index=state.processed_df_cache.index)
                    for c in numeric_cols:
                        bad = bad | cur_flags[c].fillna(False)

                    bad_cnt = int(bad.sum())
                    if bad_cnt == 0:
                        break
                    if len(state.processed_df_cache) - bad_cnt < start_rows * 0.5:
                        break
                    state.processed_df_cache = state.processed_df_cache[~bad].reset_index(drop=True)
                    total_removed += bad_cnt

                desc = f"Aykırı satırlar silindi ({total_removed} satır, 1.5×IQR, seçili {len(numeric_cols)} sütun)"

            elif method == "remove_zscore":
                bad = pd.Series(False, index=state.processed_df_cache.index)
                for c in numeric_cols:
                    s = pd.to_numeric(state.processed_df_cache[c], errors="coerce")
                    mean = float(s.mean())
                    std = float(s.std())
                    if std == 0 or pd.isna(std):
                        continue
                    bad = bad | ((s - mean).abs() > 3 * std).fillna(False)
                removed = int(bad.sum())
                state.processed_df_cache = state.processed_df_cache[~bad].reset_index(drop=True)
                desc = f"Aykırı satırlar silindi ({removed} satır, Z-Score > 3, seçili {len(numeric_cols)} sütun)"

            elif method == "cap":
                for c in numeric_cols:
                    if c in bounds:
                        state.processed_df_cache[c] = pd.to_numeric(state.processed_df_cache[c], errors="coerce").clip(
                            lower=bounds[c]["iqr_lower"], upper=bounds[c]["iqr_upper"])
                desc = f"Aykırı değerler sınır değerlere eşitlendi (Capping, 1.5×IQR, seçili {len(numeric_cols)} sütun)"

            elif method == "replace_median":
                for c in numeric_cols:
                    if c in bounds:
                        s = pd.to_numeric(state.processed_df_cache[c], errors="coerce").astype(float)
                        s = s.mask(outlier_flags[c], bounds[c]["median"])
                        state.processed_df_cache[c] = s
                desc = f"Aykırı değerler medyan ile değiştirildi (1.5×IQR sınırı, seçili {len(numeric_cols)} sütun)"

            else:
                raise ValueError(f"Geçersiz aykırı değer yöntemi: {method}")

            icon = "filter_alt"
            icon_bg = "bg-warning-orange/10"
            icon_color = "text-[#a1680d]"
        else:
            raise ValueError(f"Geçersiz işlem: {op}")

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
        state.preprocessing_history_stack.append(history_entry)

    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"İşlem uygulanamadı: {str(err)}"
        )

    res = build_preprocessing_state_response()
    active_cols_after = [c for c in state.processed_df_cache.columns if c not in state.dropped_columns]
    after_stats = {
        "rows": int(len(state.processed_df_cache)),
        "columns": int(len(active_cols_after)),
        "missing": int(state.processed_df_cache[active_cols_after].isna().sum().sum()) if active_cols_after else 0
    }

    res["status"] = "success"
    res["operation"] = op
    res["before"] = before_stats
    res["after"] = after_stats
    return res


def undo_preprocessing_op() -> dict:
    """Undoes the last preprocessing operation."""
    if len(state.preprocessing_history_stack) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geri alınacak başka işlem bulunmuyor."
        )

    last_entry = state.preprocessing_history_stack.pop()
    state.processed_df_cache = last_entry["df"].copy()
    state.dropped_columns = set(last_entry["dropped_cols"])

    res = build_preprocessing_state_response()
    res["status"] = "success"
    return res


def reset_preprocessing_ops() -> dict:
    """Resets all preprocessing operations back to original uploaded state."""
    if state.original_df_cache is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Veri seti bulunamadı."
        )

    state.processed_df_cache = state.original_df_cache.copy()
    state.dropped_columns = set()
    now_time = datetime.datetime.now().strftime("%H:%M")
    state.preprocessing_history_stack = [{
        "op": "initial",
        "description": "Orijinal veri yüklendi",
        "time": now_time,
        "icon": "upload_file",
        "icon_bg": "bg-slate-gray/10",
        "icon_color": "text-slate-gray",
        "df": state.original_df_cache.copy(),
        "dropped_cols": set()
    }]

    res = build_preprocessing_state_response()
    res["status"] = "success"
    return res
