import sys
import pandas as pd
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_api():
    print("Testing GET / ...")
    r = client.get("/")
    assert r.status_code == 200, f"GET / failed: {r.status_code}"
    assert "trex DataLab" in r.text
    print("[OK] GET / OK")

    print("Testing GET /data-quality ...")
    r = client.get("/data-quality")
    assert r.status_code == 200, f"GET /data-quality failed: {r.status_code}"
    assert "Data Quality" in r.text
    print("[OK] GET /data-quality OK")

    print("Testing POST /api/upload with test_data.csv ...")
    with open("test_data.csv", "rb") as f:
        r = client.post("/api/upload", files={"file": ("test_data.csv", f, "text/csv")})
    assert r.status_code == 200, f"Upload failed: {r.status_code} - {r.text}"
    data = r.json()
    print("Upload response:", data)
    assert data["filename"] == "test_data.csv"
    assert data["rows"] == 12
    assert data["columns"] == 7
    assert data["missing"] == 3
    assert data["duplicates"] == 1
    assert data["numeric_cols"] == 4
    assert data["categorical_cols"] == 3
    assert len(data["preview"]) == 10
    print("[OK] POST /api/upload stats validated OK")

    print("Testing GET /api/active-dataset ...")
    r = client.get("/api/active-dataset")
    assert r.status_code == 200
    assert r.json()["active"] is True
    print("[OK] GET /api/active-dataset OK")

    print("Testing GET /api/session ...")
    r = client.get("/api/session")
    assert r.status_code == 200
    assert r.json()["filename"] == "test_data.csv"
    print("[OK] GET /api/session OK")

    print("Testing GET /api/search ...")
    # Empty query (returns preview 10 rows)
    r_search_empty = client.get("/api/search")
    assert r_search_empty.status_code == 200
    s_data = r_search_empty.json()
    assert s_data["total_matches"] == 12
    assert len(s_data["results"]) == 10

    # Query with match (case-insensitive)
    r_search_ankara = client.get("/api/search?q=ankara")
    assert r_search_ankara.status_code == 200
    assert r_search_ankara.json()["total_matches"] == 2

    # Query with numeric match
    r_search_num = client.get("/api/search?q=82500")
    assert r_search_num.status_code == 200
    assert r_search_num.json()["total_matches"] == 1

    # Query with no match
    r_search_none = client.get("/api/search?q=nonexistent_xyz")
    assert r_search_none.status_code == 200
    assert r_search_none.json()["total_matches"] == 0
    assert len(r_search_none.json()["results"]) == 0
    print("[OK] GET /api/search tests passed")

    print("Testing GET /api/quality ...")
    r = client.get("/api/quality")
    assert r.status_code == 200
    q_data = r.json()
    assert "score" in q_data
    assert "score_breakdown" in q_data
    assert "metrics" in q_data
    assert "missing" in q_data
    assert "duplicates" in q_data
    assert "cardinality" in q_data
    assert "outliers" in q_data
    assert "dtypes" in q_data
    print(f"[OK] GET /api/quality OK (Score: {q_data['score']}, Status: {q_data['score_status']})")

    print("Testing GET /preprocessing ...")
    r = client.get("/preprocessing")
    assert r.status_code == 200
    assert "Veri Hazırlama" in r.text
    print("[OK] GET /preprocessing OK")

    print("Testing GET /api/preprocessing ...")
    with open("test_data.csv", "rb") as f:
        client.post("/api/upload", files={"file": ("test_data.csv", f, "text/csv")})
    r = client.get("/api/preprocessing")
    assert r.status_code == 200
    prep_data = r.json()
    assert "original" in prep_data
    assert "processed" in prep_data
    assert "schema" in prep_data
    assert "history" in prep_data
    assert "outliers" in prep_data
    assert "total_outliers" in prep_data["outliers"]
    assert "columns" in prep_data["outliers"]
    print(f"[OK] GET /api/preprocessing OK (Processed rows: {prep_data['processed']['rows']}, missing: {prep_data['processed']['missing']}, outliers: {prep_data['outliers']['total_outliers']})")

    print("Testing POST /api/preprocessing/apply (fill_missing) ...")
    r = client.post("/api/preprocessing/apply", json={"op": "fill_missing", "method": "median"})
    assert r.status_code == 200
    assert r.json()["after"]["missing"] == 0
    print("[OK] POST /api/preprocessing/apply (fill_missing) OK")

    print("Testing POST /api/preprocessing/apply (outlier_management - remove_iqr & undo) ...")
    r = client.post("/api/preprocessing/apply", json={"op": "outlier_management", "method": "remove_iqr"})
    assert r.status_code == 200
    assert r.json()["history"][0]["op"] == "outlier_management"
    # Undo outlier operation
    r_undo = client.post("/api/preprocessing/undo")
    assert r_undo.status_code == 200
    # Undo fill missing
    r_undo2 = client.post("/api/preprocessing/undo")
    assert r_undo2.status_code == 200
    assert r_undo2.json()["processed"]["missing"] == 3
    print("[OK] POST /api/preprocessing/apply (outlier_management) and undo OK")

    print("Testing GET /api/preprocessing/download ...")
    r = client.get("/api/preprocessing/download")
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    print("[OK] GET /api/preprocessing/download OK")

    print("Testing GET /api/export/csv ...")
    r_export = client.get("/api/export/csv")
    assert r_export.status_code == 200
    assert "text/csv" in r_export.headers.get("content-type", "")
    assert "test_data_aktarilan.csv" in r_export.headers.get("content-disposition", "")
    assert len(r_export.content) > 0
    print("[OK] GET /api/export/csv OK")

    print("Testing GET /visualization ...")
    r = client.get("/visualization")
    assert r.status_code == 200
    assert "Görselleştirme" in r.text
    print("[OK] GET /visualization OK")

    print("Testing GET /api/visualization/overview ...")
    with open("test_data.csv", "rb") as f:
        client.post("/api/upload", files={"file": ("test_data.csv", f, "text/csv")})
    r = client.get("/api/visualization/overview")
    assert r.status_code == 200
    viz_data = r.json()
    assert "numeric_columns" in viz_data
    assert "categorical_columns" in viz_data
    assert "stats" in viz_data
    assert "correlation" in viz_data
    assert "suggestions" in viz_data
    print(f"[OK] GET /api/visualization/overview OK ({len(viz_data['suggestions'])} suggestions)")

    print("Testing GET /api/visualization/chart (all chart types) ...")
    r_hist = client.get(f"/api/visualization/chart?type=histogram&column={viz_data['numeric_columns'][0]}")
    assert r_hist.status_code == 200
    assert "bins" in r_hist.json()

    r_boxplot = client.get(f"/api/visualization/chart?type=boxplot&column={viz_data['numeric_columns'][0]}")
    assert r_boxplot.status_code == 200
    bp_json = r_boxplot.json()
    assert "box" in bp_json
    assert "q1" in bp_json
    assert "q3" in bp_json
    assert "iqr" in bp_json
    assert "lower_bound" in bp_json
    assert "upper_bound" in bp_json
    assert "outlier_count" in bp_json
    assert "total" in bp_json

    r_bar = client.get(f"/api/visualization/chart?type=bar&column={viz_data['categorical_columns'][0]}")
    assert r_bar.status_code == 200
    assert "items" in r_bar.json()

    r_scat = client.get(f"/api/visualization/chart?type=scatter&x={viz_data['numeric_columns'][0]}&y={viz_data['numeric_columns'][1]}")
    assert r_scat.status_code == 200
    assert "x" in r_scat.json()

    r_box = client.get(f"/api/visualization/chart?type=grouped_boxplot&cat={viz_data['categorical_columns'][0]}&num={viz_data['numeric_columns'][0]}")
    assert r_box.status_code == 200
    assert "groups" in r_box.json()
    print("[OK] GET /api/visualization/chart types OK (including boxplot metrics)")

    print("Testing GET /api/visualization/focus (numeric and categorical) ...")
    num_col = viz_data['numeric_columns'][0]
    r_focus_num = client.get(f"/api/visualization/focus?column={num_col}")
    assert r_focus_num.status_code == 200
    focus_num_data = r_focus_num.json()
    assert focus_num_data["is_numeric"] is True
    assert len(focus_num_data["suggestions"]) > 0
    assert "stats" in focus_num_data["univariate"]
    assert "histogram" in focus_num_data["univariate"]

    cat_col = viz_data['categorical_columns'][0]
    r_focus_cat = client.get(f"/api/visualization/focus?column={cat_col}")
    assert r_focus_cat.status_code == 200
    focus_cat_data = r_focus_cat.json()
    assert focus_cat_data["is_numeric"] is False
    assert "bar" in focus_cat_data["univariate"]
    assert focus_cat_data["note"] is not None

    r_focus_inv = client.get("/api/visualization/focus?column=NON_EXISTENT_COL")
    assert r_focus_inv.status_code == 400
    print("[OK] GET /api/visualization/focus OK")

    print("Testing GET /portfolio ...")
    r = client.get("/portfolio")
    assert r.status_code == 200
    assert "Staj Çalışmaları" in r.text
    print("[OK] GET /portfolio OK")

    print("Testing GET /machine-learning and /machine-learning.html ...")
    r_ml = client.get("/machine-learning")
    assert r_ml.status_code == 200
    assert "Makine Öğrenmesi" in r_ml.text
    r_ml_html = client.get("/machine-learning.html")
    assert r_ml_html.status_code == 200
    print("[OK] GET /machine-learning and /machine-learning.html OK")

    print("Testing GET /api/ml/config ...")
    r_ml_cfg = client.get("/api/ml/config")
    assert r_ml_cfg.status_code == 200
    ml_cfg_data = r_ml_cfg.json()
    assert ml_cfg_data["active"] is True
    assert ml_cfg_data["total_rows"] > 0
    assert len(ml_cfg_data["columns"]) > 0
    assert "default_target" in ml_cfg_data
    print(f"[OK] GET /api/ml/config OK ({len(ml_cfg_data['columns'])} columns)")

    print("Testing POST /api/ml/train (Regression) ...")
    r_train_reg = client.post("/api/ml/train", json={
        "target": "Gelir",
        "problem_type": "regression",
        "train_ratio": 0.8,
        "missing_strategy": "fill",
        "models": ["linear", "dtree_reg", "rf_reg"],
        "cv_k": 3
    })
    assert r_train_reg.status_code == 200
    res_reg = r_train_reg.json()
    assert res_reg["problem_type"] == "regression"
    assert len(res_reg["models"]) == 3
    assert "best_model" in res_reg
    assert "actual_vs_predicted" in res_reg["models"][0]
    assert "feature_importance" in res_reg["models"][0]
    print(f"[OK] POST /api/ml/train (Regression) OK - Best: {res_reg['best_model']}")

    print("Testing POST /api/ml/train (Classification) ...")
    r_train_clf = client.post("/api/ml/train", json={
        "target": "Segment",
        "problem_type": "classification",
        "train_ratio": 0.8,
        "missing_strategy": "fill",
        "models": ["logistic", "dtree_clf", "rf_clf"],
        "cv_k": 3
    })
    assert r_train_clf.status_code == 200
    res_clf = r_train_clf.json()
    assert res_clf["problem_type"] == "classification"
    assert len(res_clf["models"]) == 3
    assert "confusion" in res_clf["models"][0]
    assert "roc" in res_clf["models"][0]
    print(f"[OK] POST /api/ml/train (Classification) OK - Best: {res_clf['best_model']}")

    print("Testing static image serving for portfolio ...")
    r_img = client.get("/portfolio/grafikler/oee_timeseries.png")
    assert r_img.status_code == 200
    print("[OK] GET /portfolio/grafikler/oee_timeseries.png OK")

    print("Testing GET /settings ...")
    r_settings = client.get("/settings")
    assert r_settings.status_code == 200
    assert "Uygulama Ayarları" in r_settings.text
    r_settings_html = client.get("/settings.html")
    assert r_settings_html.status_code == 200
    print("[OK] GET /settings and /settings.html OK")

    print("Testing GET /support ...")
    r_support = client.get("/support")
    assert r_support.status_code == 200
    assert "Destek & Yardım" in r_support.text
    r_support_html = client.get("/support.html")
    assert r_support_html.status_code == 200
    print("[OK] GET /support and /support.html OK")

    print("Testing AI Assistant endpoints (with active dataset) ...")
    r_ai_sett_get = client.get("/api/ai-assistant/settings")
    assert r_ai_sett_get.status_code == 200
    assert "has_key" in r_ai_sett_get.json()

    # Test chat fallback when no key is set or passed
    import main
    main.user_gemini_api_key = ""
    r_chat_fallback = client.post("/api/ai-assistant/chat", json={"message": "Veri kalitesini özetle", "page": "data-quality.html"})
    assert r_chat_fallback.status_code == 200
    res_fb = r_chat_fallback.json()
    assert res_fb["source"] == "fallback"
    assert "reply" in res_fb
    assert "session_id" in res_fb
    assert res_fb["context"]["dataset_loaded"] is True
    ds_meta = res_fb["context"]["dataset"]
    assert "test_data.csv" in ds_meta["filename"]
    assert "dtypes" in ds_meta
    assert "preview_first_3_rows" in ds_meta
    assert "top_correlations" in ds_meta
    assert "missing_counts" in ds_meta

    sess_id = res_fb["session_id"]

    # Test multi-turn with invalid api_key passed in request -> should return source: "error"
    r_chat_err = client.post("/api/ai-assistant/chat", json={
        "message": "En önemli değişkenler hangileri?",
        "page": "visualization.html",
        "session_id": sess_id,
        "api_key": "AIzaSyFakeKey123456789"
    })
    assert r_chat_err.status_code == 200
    res_err = r_chat_err.json()
    assert res_err["source"] == "error"
    assert "Gemini API hatası" in res_err["reply"]
    assert res_err["session_id"] == sess_id

    # Test empty message validation
    r_chat_empty = client.post("/api/ai-assistant/chat", json={"message": ""})
    assert r_chat_empty.status_code == 400

    # Test session reset
    r_ai_reset = client.post("/api/ai-assistant/reset", json={"session_id": sess_id})
    assert r_ai_reset.status_code == 200
    assert r_ai_reset.json()["ok"] is True
    print("[OK] AI Assistant endpoints validated OK (rich context, request api_key, error capture & reset)")

    print("Testing DELETE /api/reset ...")
    r = client.delete("/api/reset")
    assert r.status_code == 200
    r = client.get("/api/active-dataset")
    assert r.json()["active"] is False

    r_empty_viz = client.get("/api/visualization/overview")
    assert r_empty_viz.status_code == 409

    r_empty_export = client.get("/api/export/csv")
    assert r_empty_export.status_code == 409
    assert "İndirilecek veri seti bulunamadı." in r_empty_export.json()["detail"]
    print("[OK] DELETE /api/reset OK and /api/visualization/overview, /api/export/csv return 409 on empty")

    print("Testing AI Assistant chat (after reset / empty dataset) ...")
    r_chat_no_ds = client.post("/api/ai-assistant/chat", json={"message": "Veri kalitesini özetle", "page": "index.html"})
    assert r_chat_no_ds.status_code == 200
    assert "yüklenmemiş" in r_chat_no_ds.json()["reply"]
    print("[OK] AI Assistant empty dataset fallback OK")

    print("\nALL BACKEND TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_api()
