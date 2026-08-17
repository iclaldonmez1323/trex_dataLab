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
    print(f"[OK] GET /api/preprocessing OK (Processed rows: {prep_data['processed']['rows']}, missing: {prep_data['processed']['missing']})")

    print("Testing POST /api/preprocessing/apply (fill_missing) ...")
    r = client.post("/api/preprocessing/apply", json={"op": "fill_missing", "method": "median"})
    assert r.status_code == 200
    assert r.json()["after"]["missing"] == 0
    print("[OK] POST /api/preprocessing/apply OK")

    print("Testing POST /api/preprocessing/undo ...")
    r = client.post("/api/preprocessing/undo")
    assert r.status_code == 200
    assert r.json()["processed"]["missing"] == 3
    print("[OK] POST /api/preprocessing/undo OK")

    print("Testing GET /api/preprocessing/download ...")
    r = client.get("/api/preprocessing/download")
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    print("[OK] GET /api/preprocessing/download OK")

    print("Testing DELETE /api/reset ...")
    r = client.delete("/api/reset")
    assert r.status_code == 200
    r = client.get("/api/active-dataset")
    assert r.json()["active"] is False

    r_empty_prep = client.get("/api/preprocessing")
    assert r_empty_prep.status_code == 409
    print("[OK] DELETE /api/reset OK and /api/preprocessing returns 409 on empty")

    print("\nALL BACKEND TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_api()
