import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_quality_full_lifecycle():
    # 1. Prepare synthetic dataset with known missing, duplicates, outliers, high cardinality
    df = pd.DataFrame({
        "ID": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 12],
        "Age": [25.0, 30.0, np.nan, 45.0, 50.0, 35.0, 40.0, 60.0, 28.0, 32.0, 32.0, 99.0],
        "Salary": [50000.0, 60000.0, 70000.0, np.nan, 90000.0, 65000.0, 80000.0, 120000.0, 55000.0, 62000.0, 62000.0, 500000.0],
        "City": ["Istanbul", "Ankara", "Izmir", "Bursa", "Antalya", "Istanbul", "Ankara", "Izmir", "Bursa", "Adana", "Adana", "Samsun"],
        "HighCardCol": [f"Unique_{i}" if i != 10 else "Unique_9" for i in range(12)]
    })
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    # Upload
    r_upload = client.post("/api/upload", files={"file": ("test_quality.csv", csv_bytes, "text/csv")})
    assert r_upload.status_code == 200

    # Step 1: Initial Quality Report (Raw == Processed)
    r_q_init = client.get("/api/quality")
    assert r_q_init.status_code == 200
    q_init = r_q_init.json()
    assert "comparison" in q_init
    raw_score = q_init["comparison"]["raw_score"]
    assert q_init["comparison"]["processed_score"] == raw_score
    assert q_init["comparison"]["delta"] == 0
    assert q_init["comparison"]["raw_rows"] == 12
    assert q_init["comparison"]["processed_rows"] == 12
    assert q_init["missing"]["total_missing"] == 2
    assert q_init["duplicates"]["count"] == 1

    # Step 2: Fill missing values with mean
    r_fill = client.post("/api/preprocessing/apply", json={"op": "fill_missing", "method": "mean"})
    assert r_fill.status_code == 200
    r_q_fill = client.get("/api/quality")
    q_fill = r_q_fill.json()
    assert q_fill["missing"]["total_missing"] == 0
    assert q_fill["comparison"]["raw_score"] == raw_score
    assert q_fill["comparison"]["processed_score"] > raw_score
    assert q_fill["comparison"]["delta"] > 0
    score_after_fill = q_fill["comparison"]["processed_score"]

    # Step 3: Remove duplicate records
    r_dedup = client.post("/api/preprocessing/apply", json={"op": "drop_duplicates"})
    assert r_dedup.status_code == 200
    r_q_dedup = client.get("/api/quality")
    q_dedup = r_q_dedup.json()
    assert q_dedup["duplicates"]["count"] == 0
    assert q_dedup["comparison"]["processed_rows"] == 11
    assert q_dedup["comparison"]["raw_rows"] == 12
    assert q_dedup["comparison"]["processed_score"] >= score_after_fill
    score_after_dedup = q_dedup["comparison"]["processed_score"]

    # Step 4: Cardinality stability check during row removal
    high_card_item = next((c for c in q_dedup["cardinality"]["columns"] if c["name"] == "HighCardCol"), None)
    assert high_card_item is not None
    city_item = next((c for c in q_dedup["cardinality"]["columns"] if c["name"] == "City"), None)
    assert city_item is not None

    # Step 5: Drop high cardinality column
    r_drop_col = client.post("/api/preprocessing/apply", json={"op": "drop_column", "column": "HighCardCol"})
    assert r_drop_col.status_code == 200
    r_q_drop_col = client.get("/api/quality")
    q_drop_col = r_q_drop_col.json()
    assert not any(c["name"] == "HighCardCol" for c in q_drop_col["cardinality"]["columns"])
    assert q_drop_col["comparison"]["processed_score"] >= score_after_dedup
    score_after_drop_col = q_drop_col["comparison"]["processed_score"]

    # Step 6: Test Undo
    r_undo = client.post("/api/preprocessing/undo")
    assert r_undo.status_code == 200
    r_q_undo = client.get("/api/quality")
    q_undo = r_q_undo.json()
    assert q_undo["comparison"]["processed_score"] == score_after_dedup
    assert any(c["name"] == "HighCardCol" for c in q_undo["cardinality"]["columns"])

    # Step 7: Test Reset
    r_reset = client.post("/api/preprocessing/reset")
    assert r_reset.status_code == 200
    r_q_reset = client.get("/api/quality")
    q_reset = r_q_reset.json()
    assert q_reset["comparison"]["raw_score"] == raw_score
    assert q_reset["comparison"]["processed_score"] == raw_score
    assert q_reset["comparison"]["delta"] == 0
    assert q_reset["comparison"]["processed_rows"] == 12
    assert q_reset["missing"]["total_missing"] == 2

    # Step 8: Test fill_missing with method="unknown" on numeric column (Age)
    r_unknown = client.post("/api/preprocessing/apply", json={"op": "fill_missing", "method": "unknown", "column": "Age"})
    assert r_unknown.status_code == 200
    r_q_unknown = client.get("/api/quality")
    q_unknown = r_q_unknown.json()
    age_dtype = next((d for d in q_unknown["dtypes"] if d["name"] == "Age"), None)
    assert age_dtype is not None
    assert age_dtype["ok"] is True
    assert "int64" in age_dtype["current"] or "float64" in age_dtype["current"]
    assert q_unknown["metrics"]["type_issues"] == 0

    print("All quality lifecycle scenarios verified successfully!")

def test_outlier_management_consistency():
    print("Testing Outlier Management Consistency (1.5xIQR & User Selection) ...")
    # Dataset with single-column outlier, ID-like column with outlier, and normal data
    df = pd.DataFrame({
        "Customer_ID": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 9999], # 9999 is outlier in ID column
        "Price": [100.0, 102.0, 101.0, 99.0, 102.0, 98.0, 100.0, 101.0, 99.0, 102.0, 1500.0], # 1500 is outlier (single column)
        "Score": [80.0, 82.0, 81.0, 79.0, 83.0, 80.0, 82.0, 81.0, 78.0, 84.0, 80.0] # Normal column
    })
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    r_upload = client.post("/api/upload", files={"file": ("test_outliers.csv", csv_bytes, "text/csv")})
    assert r_upload.status_code == 200

    # 1. Test remove_iqr on Price (single column outlier, 1.5xIQR)
    r_remove_iqr = client.post("/api/preprocessing/apply", json={
        "op": "outlier_management",
        "method": "remove_iqr",
        "columns": ["Price"]
    })
    assert r_remove_iqr.status_code == 200
    res_iqr = r_remove_iqr.json()
    assert res_iqr["after"]["rows"] == 10  # 1500 outlier row removed
    assert "1.5×IQR" in res_iqr["history"][0]["description"]
    print("[OK] remove_iqr removed single-column outlier with 1.5xIQR threshold")

    # 2. Test user selection on ID-like column (Customer_ID)
    client.post("/api/preprocessing/reset")
    r_id_outlier = client.post("/api/preprocessing/apply", json={
        "op": "outlier_management",
        "method": "remove_iqr",
        "columns": ["Customer_ID"]
    })
    assert r_id_outlier.status_code == 200
    res_id = r_id_outlier.json()
    # Explicitly selected Customer_ID must NOT be skipped
    assert res_id["after"]["rows"] == 10
    print("[OK] Explicitly selected ID column processed without being skipped")

    # 3. Test Capping (1.5xIQR)
    client.post("/api/preprocessing/reset")
    r_cap = client.post("/api/preprocessing/apply", json={
        "op": "outlier_management",
        "method": "cap",
        "columns": ["Price"]
    })
    assert r_cap.status_code == 200
    r_q = client.get("/api/quality")
    q_data = r_q.json()
    price_outliers = next((o for o in q_data["outliers"]["columns"] if o["name"] == "Price"), None)
    assert price_outliers is None or price_outliers["count"] == 0
    print("[OK] cap clipped Price outliers to 1.5xIQR bounds")

    # 4. Test Replace with Median (1.5xIQR)
    client.post("/api/preprocessing/reset")
    r_med = client.post("/api/preprocessing/apply", json={
        "op": "outlier_management",
        "method": "replace_median",
        "columns": ["Price"]
    })
    assert r_med.status_code == 200
    r_q_med = client.get("/api/quality")
    q_med_data = r_q_med.json()
    price_outliers_med = next((o for o in q_med_data["outliers"]["columns"] if o["name"] == "Price"), None)
    assert price_outliers_med is None or price_outliers_med["count"] == 0
    print("[OK] replace_median replaced Price outliers with median")

    # 5. Test remove_zscore
    client.post("/api/preprocessing/reset")
    r_z = client.post("/api/preprocessing/apply", json={
        "op": "outlier_management",
        "method": "remove_zscore",
        "columns": ["Price"]
    })
    assert r_z.status_code == 200
    assert r_z.json()["after"]["rows"] == 10
    print("[OK] remove_zscore removed outlier row (Z > 3)")

    print("All outlier management consistency scenarios verified successfully!")

if __name__ == "__main__":
    test_quality_full_lifecycle()
    test_outlier_management_consistency()
