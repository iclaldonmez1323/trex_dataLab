import os
import sys

# Ensure root directory is in sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

def get_data_path(filename: str) -> str:
    candidates = [
        os.path.join(ROOT_DIR, "data", filename),
        os.path.join(ROOT_DIR, filename),
        filename,
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return filename

import io
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from main import app
from app.services.ml_service import monotonic_ratio, auto_exclude_reason, auto_exclude_column, col_kind

client = TestClient(app)

def test_monotonic_guard_scenarios():
    print("=" * 70)
    print("TESTING MONOTONIC ID GUARD IN ML SERVICE")
    print("=" * 70)

    # -------------------------------------------------------------
    # Senaryo 1: ornek_veri_seti.csv
    # -------------------------------------------------------------
    print("\n--- Senaryo 1: ornek_veri_seti.csv ---")
    data_file = get_data_path("ornek_veri_seti.csv")
    with open(data_file, "rb") as f:
        r_up = client.post("/api/upload", files={"file": ("ornek_veri_seti.csv", f, "text/csv")})
    assert r_up.status_code == 200

    r_cfg = client.get("/api/ml/config")
    assert r_cfg.status_code == 200
    cfg = r_cfg.json()
    cols = {c["name"]: c for c in cfg["columns"]}

    print("Sütun dışlama durumları:")
    for name, c in cols.items():
        print(f" - {name}: should_exclude={c['should_exclude']}, reason={c['exclude_reason']}")

    assert cols["Musteri_ID"]["should_exclude"] is True, "Musteri_ID excluded olmalı"
    assert cols["Yas"]["should_exclude"] is False, "Yas dışlanmamalı"
    assert cols["Gelir"]["should_exclude"] is False, "Gelir dışlanmamalı"
    assert cols["Aylik_Harcama"]["should_exclude"] is False, "Aylik_Harcama dışlanmamalı"
    assert cols["Kredi_Skoru"]["should_exclude"] is False, "Kredi_Skoru dışlanmamalı"
    print("[PASS] Senaryo 1: ornek_veri_seti.csv testi başarılı!")

    # -------------------------------------------------------------
    # Senaryo 2: ai4i2020 UDI (1..10000 artan)
    # -------------------------------------------------------------
    print("\n--- Senaryo 2: ai4i2020 UDI düzenli artan ---")
    n_ai = 100
    df_ai = pd.DataFrame({
        "UDI": range(1, n_ai + 1),
        "Product_ID": [f"L{47180 + i}" for i in range(n_ai)],
        "Air_temperature": np.random.uniform(295.0, 305.0, size=n_ai),
        "Failure": np.random.choice([0, 1], size=n_ai)
    })
    csv_bytes_ai = df_ai.to_csv(index=False).encode("utf-8")
    client.post("/api/upload", files={"file": ("ai4i.csv", io.BytesIO(csv_bytes_ai), "text/csv")})

    r_cfg_ai = client.get("/api/ml/config").json()
    cols_ai = {c["name"]: c for c in r_cfg_ai["columns"]}
    assert cols_ai["UDI"]["should_exclude"] is True, "UDI dışlanmalı"
    print(f"UDI exclude reason: {cols_ai['UDI']['exclude_reason']}")
    print("[PASS] Senaryo 2: UDI testi başarılı!")

    # -------------------------------------------------------------
    # Senaryo 3: Melbourne (Postcode, Rooms, Price, Distance)
    # -------------------------------------------------------------
    print("\n--- Senaryo 3: Melbourne Veri Seti Regresyon Testi ---")
    n_melb = 100
    df_melb = pd.DataFrame({
        "Postcode": np.random.choice([3000, 3001, 3051, 3121, 3141, 3182], size=n_melb),
        "Rooms": np.random.randint(1, 6, size=n_melb),
        "Price": np.random.uniform(300000, 2500000, size=n_melb),
        "Distance": np.random.uniform(1.0, 25.0, size=n_melb),
        "Address": [f"Address {i}" for i in range(n_melb)],
    })
    csv_bytes_melb = df_melb.to_csv(index=False).encode("utf-8")
    client.post("/api/upload", files={"file": ("melbourne.csv", io.BytesIO(csv_bytes_melb), "text/csv")})

    r_cfg_melb = client.get("/api/ml/config").json()
    cols_melb = {c["name"]: c for c in r_cfg_melb["columns"]}
    assert cols_melb["Postcode"]["should_exclude"] is False, "Postcode dışlanmamalı"
    assert cols_melb["Rooms"]["should_exclude"] is False, "Rooms dışlanmamalı"
    assert cols_melb["Price"]["should_exclude"] is False, "Price dışlanmamalı"
    assert cols_melb["Distance"]["should_exclude"] is False, "Distance dışlanmamalı"
    print("[PASS] Senaryo 3: Melbourne testi başarılı!")

    # -------------------------------------------------------------
    # Senaryo 4: Ters-sırada ID (120 -> 101 azalan, regex'e takılmayan isim)
    # -------------------------------------------------------------
    print("\n--- Senaryo 4: Ters-sırada azalan ID (ör. Sira_Degeri: 200..101) ---")
    n_rev = 50
    df_rev = pd.DataFrame({
        "Sira_Degeri": list(range(200, 200 - n_rev, -1)),
        "Feature_X": np.random.uniform(10, 50, size=n_rev),
        "Target": np.random.choice([0, 1], size=n_rev)
    })
    csv_bytes_rev = df_rev.to_csv(index=False).encode("utf-8")
    client.post("/api/upload", files={"file": ("reverse_id.csv", io.BytesIO(csv_bytes_rev), "text/csv")})

    r_cfg_rev = client.get("/api/ml/config").json()
    cols_rev = {c["name"]: c for c in r_cfg_rev["columns"]}
    assert cols_rev["Sira_Degeri"]["should_exclude"] is True, "Ters sıradaki azalan ID dışlanmalı"
    assert "Sayısal kimlik" in cols_rev["Sira_Degeri"]["exclude_reason"]
    print(f"Sira_Degeri exclude reason: {cols_rev['Sira_Degeri']['exclude_reason']}")
    print("[PASS] Senaryo 4: Ters sırada azalan ID testi başarılı!")

    # -------------------------------------------------------------
    # Senaryo 5: ML Eğitimi (ornek_veri_seti.csv, hedef=Durum)
    # -------------------------------------------------------------
    print("\n--- Senaryo 5: ML Eğitimi (ornek_veri_seti.csv hedef=Durum) ---")
    with open(data_file, "rb") as f:
        client.post("/api/upload", files={"file": ("ornek_veri_seti.csv", f, "text/csv")})

    r_cfg_ornek = client.get("/api/ml/config").json()
    auto_excluded = [c["name"] for c in r_cfg_ornek["columns"] if c["should_exclude"]]
    print(f"Otomatik dışlanan sütunlar: {auto_excluded}")
    assert auto_excluded == ["Musteri_ID"], f"Sadece Musteri_ID dışlanmalıydı, dışlananlar: {auto_excluded}"

    r_train = client.post("/api/ml/train", json={
        "target": "Durum",
        "problem_type": "classification",
        "train_ratio": 0.8,
        "models": ["dtree_clf", "logistic"],
        "cv_k": 3,
        "exclude_columns": auto_excluded
    })
    assert r_train.status_code == 200, f"Eğitim başarısız: {r_train.text}"
    train_res = r_train.json()
    print(f"Eğitim başarılı! En iyi model: {train_res.get('best_model')}")
    print(f"Model sayısı: {len(train_res.get('models', []))}")
    print("[PASS] Senaryo 5: ML Eğitimi testi başarılı!")

    # -------------------------------------------------------------
    # Senaryo 6: monotonic_ratio Birim Fonksiyon Testleri
    # -------------------------------------------------------------
    print("\n--- Senaryo 6: monotonic_ratio birim testleri ---")
    s_empty = pd.Series([], dtype=float)
    assert monotonic_ratio(s_empty) == 0.0

    s_single = pd.Series([42])
    assert monotonic_ratio(s_single) == 0.0

    s_inc = pd.Series([10, 20, 30, 40, 50])
    assert monotonic_ratio(s_inc) == 1.0

    s_dec = pd.Series([50, 40, 30, 20, 10])
    assert monotonic_ratio(s_dec) == 1.0

    s_with_nan = pd.Series([10, np.nan, 20, 30, np.nan, 40])
    assert monotonic_ratio(s_with_nan) == 1.0

    s_random = pd.Series([25, 32, 45, 12, 67, 18, 90])
    assert monotonic_ratio(s_random) < 0.95
    print("[PASS] Senaryo 6: monotonic_ratio birim testleri başarılı!")

    print("\n" + "=" * 70)
    print("TÜM DOĞRULAMA SENARYOLARI EKSİKSİZ GEÇTİ!")
    print("=" * 70)

if __name__ == "__main__":
    test_monotonic_guard_scenarios()
