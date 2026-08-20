import io
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_ml_context_aware():
    print("\n--- TEST 1: Melbourne Housing Pattern (Address, Date, Suburb, Rooms, Constant) ---")
    n_melb = 200
    df_melb = pd.DataFrame({
        "Address": [f"Street {i}" for i in range(184)] + [f"Street {i%10}" for i in range(16)], # ~92% unique
        "Date": pd.date_range("2023-01-01", periods=n_melb, freq="D").astype(str),
        "Suburb": np.random.choice(["Richmond", "Carlton", "Fitzroy", "St Kilda"], size=n_melb),
        "Rooms": np.random.randint(1, 6, size=n_melb),
        "Price": np.random.uniform(300000, 2500000, size=n_melb),
        "Distance": np.random.uniform(1.0, 25.0, size=n_melb),
        "Constant_Col": ["TekDeger"] * n_melb,
        "Notes": np.random.choice(["Kısa not A", "Kısa not B", "Kısa not C"], size=n_melb) # should NOT be matched by ID_RE
    })
    
    csv_bytes = df_melb.to_csv(index=False).encode("utf-8")
    r = client.post("/api/upload", files={"file": ("melbourne.csv", io.BytesIO(csv_bytes), "text/csv")})
    assert r.status_code == 200
    
    r_cfg = client.get("/api/ml/config")
    assert r_cfg.status_code == 200
    cfg = r_cfg.json()
    cols = {c["name"]: c for c in cfg["columns"]}
    
    # 1. Address -> high cardinality text/categorical
    assert cols["Address"]["should_exclude"] is True
    assert "Yüksek benzersizlik" in cols["Address"]["exclude_reason"]
    
    # 2. Date -> datetime
    assert cols["Date"]["should_exclude"] is True
    assert "Tarih/zaman" in cols["Date"]["exclude_reason"]
    
    # 3. Suburb -> normal categorical, NOT excluded
    assert cols["Suburb"]["should_exclude"] is False
    assert cols["Suburb"]["exclude_reason"] is None
    
    # 4. Rooms, Price, Distance -> numerical, NOT excluded
    assert cols["Rooms"]["should_exclude"] is False
    assert cols["Price"]["should_exclude"] is False
    assert cols["Distance"]["should_exclude"] is False
    
    # 5. Constant_Col -> zero variance
    assert cols["Constant_Col"]["should_exclude"] is True
    assert "Sabit sütun" in cols["Constant_Col"]["exclude_reason"]
    
    # 6. Notes -> not ID, not high cardinality, NOT excluded
    assert cols["Notes"]["should_exclude"] is False
    print("[PASS] Test 1: Melbourne pattern (Address, Date, Constant, Suburb, Notes) OK")

    print("\n--- TEST 2: ai4i2020 Predictive Maintenance Pattern (UDI, Product ID, Type, Temp) ---")
    n_ai = 100
    df_ai = pd.DataFrame({
        "UDI": range(1, n_ai + 1), # integer-like ID 100% unique
        "Product_ID": [f"L{47180 + i}" for i in range(n_ai)], # string ID 100% unique
        "Type": np.random.choice(["L", "M", "H"], size=n_ai),
        "Air_temperature": np.random.uniform(295.0, 305.0, size=n_ai),
        "Excessive_Missing": [None if i < 90 else float(i) for i in range(n_ai)], # 90% missing, nunique=10
        "Failure": np.random.choice([0, 1], size=n_ai)
    })
    csv_bytes_ai = df_ai.to_csv(index=False).encode("utf-8")
    client.post("/api/upload", files={"file": ("ai4i.csv", io.BytesIO(csv_bytes_ai), "text/csv")})
    
    r_cfg_ai = client.get("/api/ml/config")
    cfg_ai = r_cfg_ai.json()
    cols_ai = {c["name"]: c for c in cfg_ai["columns"]}
    
    assert cols_ai["UDI"]["should_exclude"] is True
    assert "Sayısal kimlik" in cols_ai["UDI"]["exclude_reason"] or "Kimlik" in cols_ai["UDI"]["exclude_reason"]
    assert cols_ai["Product_ID"]["should_exclude"] is True
    assert cols_ai["Excessive_Missing"]["should_exclude"] is True
    assert "Aşırı eksik" in cols_ai["Excessive_Missing"]["exclude_reason"]
    assert cols_ai["Type"]["should_exclude"] is False
    assert cols_ai["Air_temperature"]["should_exclude"] is False
    print("[PASS] Test 2: ai4i2020 pattern (UDI, Product_ID, Excessive_Missing, Type, Temp) OK")

    print("\n--- TEST 3: User Manual Unchecking & Model Training ---")
    # User unchecks Product_ID and runs training -> Product_ID must be included in training without crashing
    r_train = client.post("/api/ml/train", json={
        "target": "Failure",
        "problem_type": "classification",
        "train_ratio": 0.8,
        "models": ["dtree_clf", "logistic"],
        "cv_k": 3,
        "exclude_columns": ["UDI", "Excessive_Missing"] # User included Product_ID & Type & Air_temperature
    })
    assert r_train.status_code == 200, f"Training failed: {r_train.text}"
    train_res = r_train.json()
    assert "best_model" in train_res
    print("[PASS] Test 3: User manual uncheck & training OK")

    print("\nALL CONTEXT-AWARE ML & EXCLUSION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_ml_context_aware()

    print("\nALL CONTEXT-AWARE ML TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_ml_context_aware()
