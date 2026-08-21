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

import json
import pandas as pd
from fastapi.testclient import TestClient
from main import app

def test_dataset_with_trex_datalab():
    client = TestClient(app)
    
    print("=" * 70)
    print("  trex_dataLab PLATFORMU İLE VERİ KALİTESİ & TEMİZLEME TESTİ")
    print("=" * 70)
    
    # 1. Upload sample dataset
    data_file = get_data_path("ornek_veri_seti.csv")
    with open(data_file, "rb") as f:
        r_up = client.post("/api/upload", files={"file": ("ornek_veri_seti.csv", f, "text/csv")})
    
    print("\n[1] Veri Seti Yüklendi:")
    print(f" -> Yanıt: {r_up.status_code}, Dosya: ornek_veri_seti.csv")
    
    # 2. Initial Quality Report
    r_q = client.get("/api/quality").json()
    print("\n[2] Başlangıç Kalite Raporu:")
    print(f" -> Başlangıç Kalite Skoru : {r_q['score']}/100 ({r_q['score_status']})")
    print(f" -> Toplam Eksik Hücre    : {r_q['missing']['total_missing']}")
    print(f" -> Eksik Kolonlar        : {[c['name'] for c in r_q['missing']['columns']]}")
    print(f" -> Aykırı Değer Sayısı   : {r_q['outliers']['total_outliers']}")
    print(f" -> Aykırı İçeren Kolonlar: {[c['name'] for c in r_q['outliers']['columns']]}")
    
    # 3. Preprocessing: Eksik Değerleri Medyan ile Doldur
    client.post("/api/preprocessing/apply", json={"op": "fill_missing", "method": "median"})
    r_q1 = client.get("/api/quality").json()
    print("\n[3] 1. Adım: Eksik Değerler Medyan ile Dolduruldu:")
    print(f" -> Yeni Skor: {r_q1['score']} (Artış: +{r_q1['comparison']['delta']})")
    print(f" -> Kalan Eksik: {r_q1['missing']['total_missing']}")
    
    # 4. Preprocessing: Aykırı Değerleri IQR ile Yönet / Sil
    client.post("/api/preprocessing/apply", json={
        "op": "outlier_management",
        "method": "remove_iqr",
        "columns": ["Yas", "Gelir", "Aylik_Harcama"]
    })
    r_q2 = client.get("/api/quality").json()
    print("\n[4] 2. Adım: Yas, Gelir ve Aylik_Harcama Aykırı Değerleri Temizlendi:")
    print(f" -> Yeni Skor: {r_q2['score']} (Artış: +{r_q2['comparison']['delta']})")
    print(f" -> Kalan Aykırı Sayısı: {r_q2['outliers']['total_outliers']}")
    print(f" -> Kalan Satır: {r_q2['comparison']['processed_rows']} / {r_q2['comparison']['raw_rows']}")

    print("\n" + "=" * 70)
    print("  trex_dataLab ENTEGRASYON TESTİ BAŞARIYLA TAMAMLANDI")
    print("=" * 70)

if __name__ == "__main__":
    test_dataset_with_trex_datalab()
