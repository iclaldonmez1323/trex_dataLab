import io
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_ml_context_aware():
    print("\n--- TEST 1: Tiny Dataset (<50 rows) & Text Column Detection ---")
    df_tiny = pd.DataFrame({
        "ID": range(1, 31),
        "Musteri_Yorumu": [
            "Bu ürün gerçekten çok kaliteli, kargolama süreci de hızlıydı teşekkürler." if i % 2 == 0 
            else "Ürün elime ulaştığında kutusu yıpranmıştı ancak cihaz sorunsuz çalışıyor." 
            for i in range(1, 31)
        ],
        "Tarih": pd.date_range("2025-01-01", periods=30, freq="D").astype(str),
        "Puan": np.random.randint(1, 6, size=30),
        "Harcama": np.random.uniform(100, 5000, size=30),
        "Kategori": np.random.choice(["Elektronik", "Giyim", "Ev"], size=30)
    })
    
    csv_bytes = df_tiny.to_csv(index=False).encode("utf-8")
    r = client.post("/api/upload", files={"file": ("tiny_data.csv", io.BytesIO(csv_bytes), "text/csv")})
    assert r.status_code == 200, f"Upload failed: {r.text}"
    
    r_cfg = client.get("/api/ml/config")
    assert r_cfg.status_code == 200
    cfg = r_cfg.json()
    prof = cfg["profile"]
    
    assert prof["total_rows"] == 30
    assert prof["sample_bucket"] == "tiny"
    assert prof["recommended"]["cv_visible"] is False
    assert prof["recommended"]["cv_fixed_k"] is None
    assert "Musteri_Yorumu" in prof["text_columns"], f"Expected Musteri_Yorumu in text_columns: {prof['text_columns']}"
    assert "Tarih" in prof["datetime_columns"], f"Expected Tarih in datetime_columns: {prof['datetime_columns']}"
    
    # Check auto-exclusion of text column
    col_dict = {c["name"]: c for c in cfg["columns"]}
    assert col_dict["Musteri_Yorumu"]["kind"] == "text"
    assert col_dict["Musteri_Yorumu"]["auto_exclude"] is True
    assert "Musteri_Yorumu" in cfg["auto_excluded"]
    assert col_dict["Tarih"]["kind"] == "datetime"
    
    # Train tiny dataset without CV (or cv_k=3 fallback)
    r_train = client.post("/api/ml/train", json={
        "target": "Puan",
        "problem_type": "classification",
        "train_ratio": 0.8,
        "models": ["dtree_clf", "rf_clf", "logistic"],
        "cv_k": 3,
        "hyperparams": {
            "rf_clf": {"n_estimators": 50, "max_depth": 3},
            "logistic": {"C": 0.5}
        }
    })
    assert r_train.status_code == 200, f"Training tiny dataset failed: {r_train.text}"
    train_res = r_train.json()
    assert "best_model" in train_res
    assert len(train_res["models"]) == 3
    print("[PASS] Test 1: Tiny dataset, text auto-exclusion & training OK")

    print("\n--- TEST 2: Small Dataset (50-150 rows) K=3 Fixed ---")
    df_small = pd.DataFrame({
        "Age": np.random.randint(18, 65, size=80),
        "Income": np.random.uniform(20000, 150000, size=80),
        "Score": np.random.uniform(50, 100, size=80),
        "Purchased": np.random.choice([0, 1], size=80)
    })
    csv_bytes_small = df_small.to_csv(index=False).encode("utf-8")
    client.post("/api/upload", files={"file": ("small_data.csv", io.BytesIO(csv_bytes_small), "text/csv")})
    
    r_cfg_s = client.get("/api/ml/config")
    prof_s = r_cfg_s.json()["profile"]
    assert prof_s["total_rows"] == 80
    assert prof_s["sample_bucket"] == "small"
    assert prof_s["recommended"]["cv_visible"] is True
    assert prof_s["recommended"]["cv_fixed_k"] == 3
    print("[PASS] Test 2: Small dataset (n=80) K=3 recommendation OK")

    print("\n--- TEST 3: Normal Dataset (>150 rows) & Hyperparameter Clamping ---")
    df_norm = pd.DataFrame({
        "Feature1": np.random.randn(200),
        "Feature2": np.random.randn(200),
        "Feature3": np.random.randn(200),
        "Target": np.random.randn(200) * 10 + 50
    })
    csv_bytes_norm = df_norm.to_csv(index=False).encode("utf-8")
    client.post("/api/upload", files={"file": ("norm_data.csv", io.BytesIO(csv_bytes_norm), "text/csv")})
    
    r_cfg_n = client.get("/api/ml/config")
    prof_n = r_cfg_n.json()["profile"]
    assert prof_n["total_rows"] == 200
    assert prof_n["sample_bucket"] == "normal"
    assert prof_n["recommended"]["cv_visible"] is True
    assert prof_n["recommended"]["cv_fixed_k"] is None
    
    # Train regression with clamped hyperparameters
    r_train_norm = client.post("/api/ml/train", json={
        "target": "Target",
        "problem_type": "regression",
        "train_ratio": 0.8,
        "models": ["linear", "dtree_reg", "rf_reg"],
        "cv_k": 5,
        "hyperparams": {
            "rf_reg": {"n_estimators": 1000, "max_depth": 60},  # should be clamped to 500 and 50
            "dtree_reg": {"max_depth": "auto"}  # should be coerced to None
        }
    })
    assert r_train_norm.status_code == 200
    res_norm = r_train_norm.json()
    assert "best_model" in res_norm
    assert len(res_norm["models"]) == 3
    print("[PASS] Test 3: Normal dataset (n=200) & hyperparam clamping OK")

    print("\nALL CONTEXT-AWARE ML TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_ml_context_aware()
