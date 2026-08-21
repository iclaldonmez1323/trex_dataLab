import re
import warnings
import traceback
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold, KFold, TimeSeriesSplit
from sklearn.preprocessing import LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    r2_score, mean_absolute_error, mean_squared_error, confusion_matrix, roc_curve
)
from app.core.state import state

CARDINALITY_RATIO = 0.70
NUMERIC_ID_RATIO = 0.90
MISSING_RATIO = 0.80
MONOTONIC_ID_RATIO = 0.95

_ID_RE = re.compile(
    r"(\b(uuid|tckn|tc_no|udi|code|kayit_no|kayıt_no|numara)\b)|"
    r"(?:^|_)id$|_id(?:$|_)",
    re.IGNORECASE
)

CLASS_MODELS = {
    "logistic": {"name": "Logistic Regression", "cls": LogisticRegression, "kwargs": {"max_iter": 2000}},
    "dtree_clf": {"name": "Decision Tree", "cls": DecisionTreeClassifier, "kwargs": {"random_state": 42}},
    "rf_clf": {"name": "Random Forest", "cls": RandomForestClassifier, "kwargs": {"random_state": 42, "n_estimators": 50, "max_depth": 10, "n_jobs": -1}},
}
REGR_MODELS = {
    "linear": {"name": "Linear Regression", "cls": LinearRegression, "kwargs": {}},
    "dtree_reg": {"name": "Decision Tree Regressor", "cls": DecisionTreeRegressor, "kwargs": {"random_state": 42}},
    "rf_reg": {"name": "Random Forest Regressor", "cls": RandomForestRegressor, "kwargs": {"random_state": 42, "n_estimators": 50, "max_depth": 10, "n_jobs": -1}},
}

ALLOWED_HYPERPARAMS = {
    "rf_clf": ["n_estimators", "max_depth"],
    "rf_reg": ["n_estimators", "max_depth"],
    "dtree_clf": ["max_depth"],
    "dtree_reg": ["max_depth"],
    "logistic": ["C"],
    "linear": [],
}


def is_integer_like(s: pd.Series) -> bool:
    s = s.dropna()
    if len(s) == 0:
        return False
    if pd.api.types.is_integer_dtype(s.dtype):
        return True
    if pd.api.types.is_float_dtype(s.dtype):
        return bool((s == s.round()).all())
    return False


def monotonic_ratio(s: pd.Series) -> float:
    """Boş olmayan değerlerin satır sırasındaki ardışık çiftlerinin
    kesin artış VEYA kesin azalış oranını döndürür (büyüğü)."""
    v = s.dropna().reset_index(drop=True)
    if len(v) < 2:
        return 0.0
    diff = v.diff().dropna()
    inc = float((diff > 0).sum()) / len(diff)
    dec = float((diff < 0).sum()) / len(diff)
    return max(inc, dec)


def col_kind(s: pd.Series) -> str:
    if pd.api.types.is_numeric_dtype(s):
        return "numeric"

    sample = s.dropna().head(200)
    if len(sample) > 0:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                parsed = pd.to_datetime(sample, errors="coerce")
                if float(parsed.notna().sum() / len(sample)) >= 0.8:
                    return "datetime"
        except Exception:
            pass

    if s.dtype == object or pd.api.types.is_string_dtype(s):
        s_str = s.dropna().astype(str)
        if len(s_str) > 0:
            lens = s_str.str.len()
            avg_len = float(lens.mean())
            max_len = int(lens.max())
            if avg_len >= 30 or max_len > 80:
                return "text"

    return "categorical"


def auto_exclude_reason(name: str, s: pd.Series, kind: str) -> Optional[str]:
    n = int(s.notna().sum())
    total = int(len(s))
    nunique = int(s.nunique(dropna=True))
    if n == 0:
        return "Sütun tamamen boş"
    unique_ratio = nunique / n if n else 0.0
    missing_ratio = 1.0 - (n / total) if total else 1.0

    if nunique <= 1:
        return "Sabit sütun (tek benzersiz değer)"
    if missing_ratio >= MISSING_RATIO:
        return f"Aşırı eksik veri (%{round(missing_ratio * 100)})"
    if kind == "datetime":
        return "Tarih/zaman sütunu (özellik çıkarımı gerekir)"
    if kind == "text":
        return "Serbest metin sütunu"
    if _ID_RE.search(str(name)):
        return "Kimlik/numara sütunu"
    if kind in ("categorical", "text") and unique_ratio >= CARDINALITY_RATIO:
        return f"Yüksek benzersizlik (%{round(unique_ratio * 100)})"
    if (kind == "numeric"
            and is_integer_like(s)
            and unique_ratio >= NUMERIC_ID_RATIO
            and monotonic_ratio(s) >= MONOTONIC_ID_RATIO):
        return f"Sayısal kimlik (integer, %{round(unique_ratio * 100)} benzersiz)"
    return None


def auto_exclude_column(name: str, s: pd.Series, kind: Optional[str] = None) -> bool:
    kind = kind or col_kind(s)
    return auto_exclude_reason(name, s, kind) is not None


def ml_data_source() -> str:
    if state.processed_df_cache is not None and state.original_df_cache is not None:
        if len(state.preprocessing_history_stack) > 1 or not state.processed_df_cache.equals(state.original_df_cache):
            return "processed"
    return "raw"


def top_class_ratio(s: pd.Series) -> float:
    vc = s.dropna().value_counts(normalize=True)
    return float(vc.iloc[0]) if len(vc) else 0.0


def detect_time_series(df: pd.DataFrame) -> tuple:
    TIME_KEYS = ("date", "time", "tarih", "saat", "timestamp", "datetime")

    for col in df.columns:
        s = df[col]
        name_low = str(col).lower()
        is_time_named = any(k in name_low for k in TIME_KEYS)

        parsed = None
        if pd.api.types.is_datetime64_any_dtype(s):
            parsed = s
        elif s.dtype == object:
            try:
                parsed = pd.to_datetime(s, errors="coerce")
            except Exception:
                parsed = None
        parseable = parsed is not None and parsed.notna().mean() >= 0.9

        if not is_time_named and not parseable:
            continue

        confirmed = False
        if parseable:
            ts = parsed.dropna()
            n = len(ts)
            if n >= 10:
                unique = ts.nunique() == n
                monotonic = bool(ts.is_monotonic_increasing)
                if unique and monotonic:
                    gaps = ts.diff().dropna()
                    if len(gaps) > 0:
                        med = gaps.median()
                        if med is not None and med > pd.Timedelta(0):
                            tolerance = med * 0.25
                            regular = float(((gaps - med).abs() <= tolerance).mean()) >= 0.9
                            confirmed = regular
        return bool(confirmed), True, str(col)

    return False, False, None


def get_ml_dataframe() -> Optional[pd.DataFrame]:
    if state.processed_df_cache is not None:
        df = state.processed_df_cache.copy()
        if state.dropped_columns:
            df = df.drop(columns=[c for c in state.dropped_columns if c in df.columns], errors="ignore")
    elif state.active_df_cache is not None:
        df = state.active_df_cache.copy()
    else:
        return None
    return df


def coerce_hyper(key: str, val: Any):
    if key == "max_depth" and (val in (None, "auto", "", 0, "0") or val is None):
        return None
    try:
        f = float(val)
        if key in ("n_estimators", "max_depth"):
            return int(f)
        return f
    except (ValueError, TypeError):
        return None


def run_ml_training(req: dict) -> dict:
    df = get_ml_dataframe()
    if df is None or not state.active_dataset:
        return {"error": "Aktif bir veri seti yok.", "status_code": 404}

    if len(df.columns) < 2:
        return {
            "error": "Model eğitimi için en az 2 sütun (1 hedef + en az 1 özellik) gereklidir.",
            "detail": f"Mevcut veri setinde yalnızca 1 sütun bulunmaktadır: {list(df.columns)}. Lütfen ana sayfadan çok sütunlu geçerli bir CSV dosyası yükleyin.",
            "status_code": 400
        }

    target = req.get("target")
    if not target or target not in df.columns:
        return {"error": "Geçerli bir hedef değişken seçin.", "status_code": 400}

    problem_type = req.get("problem_type", "auto")
    train_ratio = float(req.get("train_ratio", 0.8))
    train_ratio = max(0.5, min(0.95, train_ratio))
    model_ids = req.get("models", [])
    cv_k = int(req.get("cv_k", 5))
    cv_mode = req.get("cv_mode", "auto")
    missing_strategy = req.get("missing_strategy", "fill")
    user_exclude = req.get("exclude_columns", []) or []
    user_exclude = [c for c in user_exclude if c != target]

    if not model_ids:
        return {"error": "En az bir model seçin.", "status_code": 400}

    target_is_numeric = pd.api.types.is_numeric_dtype(df[target])
    is_classification = (problem_type == "classification") or (problem_type == "auto" and not target_is_numeric)
    is_regression = (problem_type == "regression") or (problem_type == "auto" and target_is_numeric)

    is_ts, ts_suspected, ts_col = detect_time_series(df)
    use_ts = (cv_mode == "time_series") or (cv_mode == "auto" and is_ts)
    top_class = top_class_ratio(df[target]) if is_classification else None
    imbalanced = bool(is_classification and top_class is not None and top_class >= 0.9)

    if use_ts and ts_col and ts_col in df.columns:
        df = df.sort_values(ts_col).reset_index(drop=True)

    if "exclude_columns" in req and req["exclude_columns"] is not None:
        user_exclude = [c for c in req.get("exclude_columns", []) if c != target and c in df.columns]
        excluded = sorted(set(user_exclude))
    else:
        auto_excluded = [c for c in df.columns if c != target and auto_exclude_column(c, df[c])]
        excluded = sorted(set(auto_excluded))

    features = [c for c in df.columns if c != target and c not in excluded]
    if not features:
        return {
            "error": "Hariç tutma sonrası kullanılabilir özellik sütunu kalmadı.",
            "detail": f"Hariç tutulan sütunlar: {', '.join(excluded) if excluded else 'yok'}. Lütfen hariç tutulan sütun listesinden en az bir özelliği kaldırın.",
            "status_code": 400
        }

    X = df[features].copy()
    y = df[target].copy()

    X = X.dropna(axis=1, how="all")
    if missing_strategy == "fill":
        num_cols = [c for c in X.columns if pd.api.types.is_numeric_dtype(X[c])]
        cat_cols = [c for c in X.columns if not pd.api.types.is_numeric_dtype(X[c])]
        if num_cols:
            X[num_cols] = SimpleImputer(strategy="median").fit_transform(X[num_cols])
        if cat_cols:
            X[cat_cols] = SimpleImputer(strategy="most_frequent").fit_transform(X[cat_cols])
        y = y[X.notna().any(axis=1)]
        X = X[X.notna().any(axis=1)]
        y = y[X.index]
    else:
        df_clean = df.dropna(subset=features + [target])
        X = df_clean[features].copy()
        y = df_clean[target].copy()

    if len(X) < 5:
        return {"error": "Temizleme sonrası yeterli veri kalmadı.", "status_code": 400}

    cat_cols = [c for c in X.columns if not pd.api.types.is_numeric_dtype(X[c])]
    if cat_cols:
        X = pd.get_dummies(X, columns=cat_cols, prefix_sep="_", dtype=int)

    X = X.fillna(X.median(numeric_only=True)).fillna(0)
    X = X.dropna()
    y = y[X.index]
    y = y.dropna()
    X = X.loc[y.index]

    if len(X) < 5:
        return {"error": "Temizlik/imputation sonrası yeterli veri kalmadı.", "status_code": 400}

    class_names = None
    if is_classification:
        y_le = LabelEncoder()
        y_enc = y_le.fit_transform(y.astype(str))
        class_names = [str(c) for c in y_le.classes_]
        y = y_enc
        if len(class_names) < 2:
            return {"error": "Hedef değişkende en az 2 sınıf olmalı.", "status_code": 400}

    feature_names = list(X.columns)

    stratify = None
    if not use_ts and is_classification and len(pd.Series(y).value_counts()) > 1 and min(pd.Series(y).value_counts()) >= 2:
        stratify = y
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, train_size=train_ratio, random_state=42, shuffle=not use_ts, stratify=stratify)

    models = CLASS_MODELS if is_classification else REGR_MODELS
    n_splits = max(2, min(cv_k, min(pd.Series(y).value_counts().min(), len(X)) if is_classification else len(X)))

    def _safe_float(v) -> Optional[float]:
        if v is None:
            return None
        try:
            f = float(v)
            if np.isnan(f) or np.isinf(f):
                return None
            return f
        except Exception:
            return None

    def _safe_float_list(arr) -> list:
        res = []
        for x in arr:
            sf = _safe_float(x)
            res.append(sf if sf is not None else 0.0)
        return res

    results = []
    for mid in model_ids:
        if mid not in models:
            continue
        cfg = models[mid]
        row = {"id": mid, "name": cfg["name"], "metrics": {}, "cv_mean": None, "cv_std": None,
               "model_error": None, "confusion": None, "roc": None, "actual_vs_predicted": None, "feature_importance": []}
        user_hypers = req.get("hyperparams", {}) or {}
        model_hypers = user_hypers.get(mid, {}) if isinstance(user_hypers, dict) else {}
        params = dict(cfg["kwargs"])
        allowed = ALLOWED_HYPERPARAMS.get(mid, [])
        for k, v in model_hypers.items():
            if k in allowed:
                coerced = coerce_hyper(k, v)
                if k == "n_estimators" and coerced is not None:
                    params[k] = max(10, min(500, coerced))
                elif k == "max_depth":
                    params[k] = max(1, min(50, coerced)) if coerced is not None else None
                elif k == "C" and coerced is not None:
                    params[k] = max(0.001, min(1000.0, coerced))

        try:
            model = cfg["cls"](**params)
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            if is_classification:
                row["metrics"]["accuracy"] = _safe_float(accuracy_score(y_test, y_pred))
                row["metrics"]["precision"] = _safe_float(precision_score(y_test, y_pred, average="macro", zero_division=0))
                row["metrics"]["recall"] = _safe_float(recall_score(y_test, y_pred, average="macro", zero_division=0))
                row["metrics"]["f1"] = _safe_float(f1_score(y_test, y_pred, average="macro", zero_division=0))
                try:
                    if hasattr(model, "predict_proba"):
                        proba = model.predict_proba(X_test)
                        row["metrics"]["roc_auc"] = _safe_float(roc_auc_score(y_test, proba, multi_class="ovr", average="macro"))
                    else:
                        row["metrics"]["roc_auc"] = None
                except Exception:
                    row["metrics"]["roc_auc"] = None
                try:
                    if use_ts:
                        cv = TimeSeriesSplit(n_splits=n_splits)
                    else:
                        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
                    scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy")
                    row["cv_mean"], row["cv_std"] = _safe_float(scores.mean()), _safe_float(scores.std())
                except Exception:
                    pass
                cm = confusion_matrix(y_test, y_pred, labels=list(range(len(class_names))))
                row["confusion"] = {"matrix": [[int(val) for val in row_cm] for row_cm in cm], "labels": class_names}
                if hasattr(model, "predict_proba"):
                    try:
                        proba = model.predict_proba(X_test)
                        roc_curves = []
                        if len(class_names) == 2:
                            fpr, tpr, _ = roc_curve(y_test, proba[:, 1])
                            roc_curves.append({"label": f"{class_names[1]} (AUC)", "fpr": _safe_float_list(fpr), "tpr": _safe_float_list(tpr)})
                        else:
                            for i, cls in enumerate(class_names):
                                y_bin = (y_test == i).astype(int)
                                fpr, tpr, _ = roc_curve(y_bin, proba[:, i])
                                roc_curves.append({"label": cls, "fpr": _safe_float_list(fpr), "tpr": _safe_float_list(tpr)})
                        row["roc"] = roc_curves
                    except Exception:
                        row["roc"] = None
            else:
                row["metrics"]["r2"] = _safe_float(r2_score(y_test, y_pred))
                row["metrics"]["mae"] = _safe_float(mean_absolute_error(y_test, y_pred))
                row["metrics"]["mse"] = _safe_float(mean_squared_error(y_test, y_pred))
                row["metrics"]["rmse"] = _safe_float(np.sqrt(mean_squared_error(y_test, y_pred)))
                try:
                    if use_ts:
                        cv = TimeSeriesSplit(n_splits=n_splits)
                    else:
                        cv = KFold(n_splits=n_splits, shuffle=True, random_state=42)
                    scores = cross_val_score(model, X, y, cv=cv, scoring="r2")
                    row["cv_mean"], row["cv_std"] = _safe_float(scores.mean()), _safe_float(scores.std())
                except Exception:
                    pass
                n = len(y_test)
                idx = list(range(n))
                if n > 400:
                    step = n / 400.0
                    idx = [int(i * step) for i in range(400)]
                row["actual_vs_predicted"] = {
                    "actual": _safe_float_list([y_test.iloc[i] for i in idx]),
                    "predicted": _safe_float_list([y_pred[i] for i in idx]),
                }

            if hasattr(model, "feature_importances_"):
                imp = model.feature_importances_
            elif hasattr(model, "coef_"):
                coef = model.coef_
                imp = np.abs(coef).mean(axis=0) if coef.ndim > 1 else np.abs(coef)
            else:
                imp = np.zeros(len(feature_names))
            row["feature_importance"] = sorted(
                [{"feature": str(f), "importance": _safe_float(v) or 0.0} for f, v in zip(feature_names, imp)],
                key=lambda x: x["importance"], reverse=True)[:15]
        except Exception as e:
            row["model_error"] = f"{cfg['name']}: {str(e)}"

        results.append(row)

    if not results:
        return {"error": "Seçilen modeller geçersiz.", "status_code": 400}

    healthy = [r for r in results if r["model_error"] is None]
    if not healthy:
        return {
            "error": "Seçilen hiçbir model eğitilemedi.",
            "detail": "; ".join(r["model_error"] for r in results if r.get("model_error")),
            "status_code": 500
        }

    if is_classification:
        def _score(r): return (r["metrics"].get("accuracy") or 0, r["metrics"].get("f1") or 0)
    else:
        def _score(r): return (r["metrics"].get("r2") or -999, 0)
    best = max(healthy, key=_score)

    return {
        "problem_type": "classification" if is_classification else "regression",
        "target": target,
        "data_source": ml_data_source(),
        "is_time_series": is_ts,
        "time_series_suspected": ts_suspected,
        "time_column": ts_col,
        "cv_method": "time_series_split" if use_ts else ("stratified_kfold" if is_classification else "kfold"),
        "imbalanced": imbalanced,
        "imbalance_ratio": top_class,
        "excluded_columns": excluded,
        "feature_count": len(feature_names),
        "total_rows": int(len(X)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "cv_k": n_splits,
        "models": results,
        "best_model": best["id"],
    }
