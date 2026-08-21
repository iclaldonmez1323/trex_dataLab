import re
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from app.core.state import state, clean_val_for_json

LABEL_DICT: Dict[str, str] = {
    "order_hour": "Sipariş Saati",
    "customer_age": "Müşteri Yaşı",
    "order_date": "Sipariş Tarihi",
    "product_name": "Ürün Adı",
    "price": "Fiyat",
    "quantity": "Adet",
    "regionname": "Bölge Adı",
    "propertycount": "Konut Sayısı",
    "bedroom2": "Yatak Odası",
    "bathroom": "Banyo",
    "car": "Araç",
    "landsize": "Arsa Alanı",
    "landarea": "Arsa Alanı",
    "buildingarea": "Bina Alanı",
    "yearbuilt": "Yapım Yılı",
    "date": "Tarih",
    "time": "Saat",
    "hour": "Saat",
    "day": "Gün",
    "month": "Ay",
    "year": "Yıl",
    "timestamp": "Zaman Damgası",
    "age": "Yaş",
    "income": "Gelir",
    "credit_score": "Kredi Skoru",
    "segment": "Segment",
    "city": "Şehir",
    "status": "Durum",
    "target": "Hedef",
    "oee": "OEE",
    "availability": "Kullanılabilirlik",
    "performance": "Performans",
    "quality": "Kalite"
}


def pretty_label(col: Optional[str]) -> str:
    if not col:
        return ""
    col_str = str(col).strip()
    norm = re.sub(r'[\s\-_]+', '', col_str).lower()
    for k, v in LABEL_DICT.items():
        k_norm = re.sub(r'[\s\-_]+', '', k).lower()
        if norm == k_norm:
            return v
    cleaned = re.sub(r'[_\-]+', ' ', col_str).strip()
    return cleaned.title() if cleaned else col_str


def looks_like_datetime(s: pd.Series, sample_size: int = 200) -> bool:
    if pd.api.types.is_datetime64_any_dtype(s):
        return True
    sample = s.dropna().head(sample_size)
    if len(sample) == 0:
        return False
    if pd.api.types.is_numeric_dtype(sample):
        return False
    parsed = pd.to_datetime(sample, errors="coerce")
    return float(parsed.notna().sum()) / len(sample) >= 0.8


def is_integer_like(s: pd.Series) -> bool:
    s = s.dropna()
    if len(s) == 0:
        return False
    if pd.api.types.is_integer_dtype(s.dtype):
        return True
    if pd.api.types.is_float_dtype(s.dtype):
        try:
            return bool((s == s.round()).all())
        except Exception:
            return False
    return False


def classify_columns(df: pd.DataFrame) -> Dict[str, list]:
    numeric_cols = []
    datetime_cols = []
    categorical_cols = []

    for col in df.columns:
        series = df[col]
        if pd.api.types.is_numeric_dtype(series):
            numeric_cols.append(str(col))
        elif looks_like_datetime(series):
            datetime_cols.append(str(col))
        else:
            categorical_cols.append(str(col))

    return {
        "numeric": numeric_cols,
        "datetime": datetime_cols,
        "categorical": categorical_cols
    }


def decide_chart_plan(x_col: Optional[str], y_col: Optional[str], df: pd.DataFrame) -> dict:
    classification = classify_columns(df)
    num_cols = set(classification["numeric"])
    dt_cols = set(classification["datetime"])
    cat_cols = set(classification["categorical"])

    def _get_axis_meta(col: Optional[str]) -> dict:
        if not col or col not in df.columns:
            return {"role": "none", "is_integer_like": False, "nunique": 0, "min": None, "max": None}
        s = df[col].dropna()
        if col in dt_cols:
            role = "time"
            return {"role": role, "is_integer_like": False, "nunique": int(s.nunique()), "min": None, "max": None}
        elif col in num_cols:
            int_like = is_integer_like(s)
            role = "discrete" if (int_like and s.nunique() <= 30) else "continuous"
            min_val = float(s.min()) if len(s) > 0 else None
            max_val = float(s.max()) if len(s) > 0 else None
            return {"role": role, "is_integer_like": int_like, "nunique": int(s.nunique()), "min": min_val, "max": max_val}
        else:
            role = "categorical"
            return {"role": role, "is_integer_like": False, "nunique": int(s.nunique()), "min": None, "max": None}

    x_meta = _get_axis_meta(x_col)
    y_meta = _get_axis_meta(y_col)

    x_label = pretty_label(x_col) if x_col else ""
    y_label = pretty_label(y_col) if y_col else ""

    n_points = 0
    if x_col and y_col and x_col in df.columns and y_col in df.columns:
        n_points = int(df[[x_col, y_col]].dropna().shape[0])
    elif x_col and x_col in df.columns:
        n_points = int(df[x_col].dropna().shape[0])

    needs_jitter = bool(
        (x_meta["is_integer_like"] or y_meta["is_integer_like"] or
         (x_meta["nunique"] > 0 and x_meta["nunique"] <= 0.25 * max(1, n_points)) or
         (y_meta["nunique"] > 0 and y_meta["nunique"] <= 0.25 * max(1, n_points))) and
        x_meta["role"] in ["continuous", "discrete"] and y_meta["role"] in ["continuous", "discrete"]
    )

    overplot_meta = {
        "needs_jitter": needs_jitter,
        "opacity": 0.4 if needs_jitter else 0.6,
        "symbol_size": 4 if n_points > 5000 else (5 if n_points > 1000 else 7),
        "large_mode": bool(n_points > 2000),
        "n_points": n_points
    }

    # 1. Single Variable
    if not y_col or x_col == y_col:
        if x_col in dt_cols:
            return {
                "chart_type": "line",
                "title": f"{x_label} Zaman Serisi",
                "reason": "Zaman Serisi Dağılımı",
                "x_col": x_col, "y_col": None,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {"rotate_labels": 30, "horizontal_bar": False}
            }
        elif x_col in num_cols:
            return {
                "chart_type": "histogram",
                "title": f"{x_label} Dağılımı",
                "reason": "Sayısal Değişken Frekans Dağılımı",
                "x_col": x_col, "y_col": None,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {"rotate_labels": None, "horizontal_bar": False}
            }
        else:
            n_cats = x_meta["nunique"]
            return {
                "chart_type": "bar",
                "title": f"{x_label} Kategorileri",
                "reason": f"Kategori Sayımları ({n_cats} farklı sınıf)",
                "x_col": x_col, "y_col": None,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {
                    "rotate_labels": 45 if 8 <= n_cats <= 15 else (30 if 5 <= n_cats < 8 else 0),
                    "horizontal_bar": bool(n_cats > 15)
                }
            }

    # 2. Time Series
    if (x_col in dt_cols and y_col in num_cols) or (y_col in dt_cols and x_col in num_cols):
        time_c = x_col if x_col in dt_cols else y_col
        num_c = y_col if x_col in dt_cols else x_col
        t_label = pretty_label(time_c)
        n_label = pretty_label(num_c)
        return {
            "chart_type": "line",
            "title": f"{t_label} ile {n_label} Zaman Serisi",
            "reason": "Zaman İçindeki Değişim Eğilimi",
            "x_col": time_c, "y_col": num_c,
            "axis": {"x": _get_axis_meta(time_c), "y": _get_axis_meta(num_c)},
            "overplot": overplot_meta,
            "render_hint": {"rotate_labels": 30, "horizontal_bar": False}
        }

    # 3. Categorical x Numeric
    if (x_col in cat_cols or (x_col in num_cols and x_meta["nunique"] <= 30)) and y_col in num_cols:
        n_cats = x_meta["nunique"]
        if n_cats <= 12:
            return {
                "chart_type": "grouped_boxplot",
                "title": f"{x_label}'a Göre {y_label}",
                "reason": f"Grup Dağılımı ve Çeyreklikler ({n_cats} grup)",
                "x_col": x_col, "y_col": y_col, "cat": x_col, "num": y_col,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {
                    "rotate_labels": 45 if 8 <= n_cats <= 12 else 0,
                    "horizontal_bar": False
                }
            }
        else:
            return {
                "chart_type": "bar_mean",
                "title": f"{x_label}'a Göre Ortalama {y_label}",
                "reason": f"Grup Ortalamaları ({n_cats} kategori için özet bar)",
                "x_col": x_col, "y_col": y_col, "cat": x_col, "num": y_col,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {
                    "rotate_labels": 45 if 12 < n_cats <= 15 else 0,
                    "horizontal_bar": bool(n_cats > 15)
                }
            }

    if (y_col in cat_cols or (y_col in num_cols and y_meta["nunique"] <= 30)) and x_col in num_cols:
        n_cats = y_meta["nunique"]
        if n_cats <= 12:
            return {
                "chart_type": "grouped_boxplot",
                "title": f"{y_label}'a Göre {x_label}",
                "reason": f"Grup Dağılımı ve Çeyreklikler ({n_cats} grup)",
                "x_col": x_col, "y_col": y_col, "cat": y_col, "num": x_col,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {
                    "rotate_labels": 45 if 8 <= n_cats <= 12 else 0,
                    "horizontal_bar": False
                }
            }
        else:
            return {
                "chart_type": "bar_mean",
                "title": f"{y_label}'a Göre Ortalama {x_label}",
                "reason": f"Grup Ortalamaları ({n_cats} kategori için özet bar)",
                "x_col": x_col, "y_col": y_col, "cat": y_col, "num": x_col,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {
                    "rotate_labels": 45 if 12 < n_cats <= 15 else 0,
                    "horizontal_bar": bool(n_cats > 15)
                }
            }

    # 4. Continuous x Continuous
    if x_col in num_cols and y_col in num_cols:
        if n_points > 500:
            return {
                "chart_type": "density_heatmap",
                "title": f"{x_label} × {y_label} Yoğunluk",
                "reason": f"n={n_points} > 500 olduğu için 2D Yoğunluk Haritası (Overplotting Koruması)",
                "x_col": x_col, "y_col": y_col,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {"rotate_labels": 0, "horizontal_bar": False}
            }
        else:
            return {
                "chart_type": "scatter",
                "title": f"{x_label} ile {y_label} Dağılımı",
                "reason": f"İki Değişkenli Sürekli Dağılım (n={n_points})",
                "x_col": x_col, "y_col": y_col,
                "axis": {"x": x_meta, "y": y_meta},
                "overplot": overplot_meta,
                "render_hint": {"rotate_labels": 0, "horizontal_bar": False}
            }

    # 5. Categorical x Categorical
    n_cats = x_meta["nunique"]
    return {
        "chart_type": "bar",
        "title": f"{x_label} Kategorileri",
        "reason": f"Kategorik Dağılım Karşılaştırması ({n_cats} sınıf)",
        "x_col": x_col, "y_col": y_col,
        "axis": {"x": x_meta, "y": y_meta},
        "overplot": overplot_meta,
        "render_hint": {
            "rotate_labels": 45 if 8 <= n_cats <= 15 else 0,
            "horizontal_bar": bool(n_cats > 15)
        }
    }


def get_current_active_df() -> pd.DataFrame:
    df = state.get_current_df()
    if df is None or not state.active_dataset:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Veri seti bulunamadı. Lütfen önce bir CSV dosyası yükleyin."
        )
    active_cols = state.get_active_columns()
    return df[active_cols]
