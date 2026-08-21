import os
import sys

# Ensure root directory is in sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pandas as pd
import numpy as np
from scripts.create_sample_dataset import create_sample_dataset

def main():
    print("=" * 70)
    print("      VERİ ANALİZİ: EKSİK VE AYKIRI DEĞERLERİN MANTIĞI VE TESTİ")
    print("=" * 70)
    
    # 1. Veri Setini Yükle
    df = create_sample_dataset()
    print("\n--- 1. HAM VERİ ÖNİZLEMESİ (İlk 8 Satır) ---")
    print(df.head(8).to_string(index=False))
    print(f"\nToplam Satır: {len(df)}, Toplam Sütun: {len(df.columns)}")
    
    # =========================================================================
    # 2. EKSİK DEĞER (MISSING VALUES) ANALİZİ VE MANTIĞI
    # =========================================================================
    print("\n" + "=" * 70)
    print("2. EKSİK DEĞER (MISSING VALUE / NaN) ANALİZİ")
    print("=" * 70)
    print("""
    [EKSİK DEĞER TÜRLERİ VE MANTIĞI]:
    1. MCAR (Missing Completely at Random): Eksiklik tamamen rastgeledir. (Örn: Yaş bilgisi teknik arızadan girilmedi)
    2. MAR (Missing at Random): Eksiklik başka bir sütunla ilişkilidir. (Örn: Stajyerlerin kredi geçmişi olmadığı için Kredi_Skoru eksik)
    3. MNAR (Missing Not at Random): Eksikliğin nedeni değişkenin kendi değeridir. (Örn: Çok yüksek gelirlilerin gelirini belirtmek istememesi)
    """)
    
    missing_summary = pd.DataFrame({
        "Eksik_Sayisi": df.isna().sum(),
        "Eksik_Orani (%)": (df.isna().sum() / len(df) * 100).round(1),
        "Veri_Tipi": df.dtypes
    })
    missing_summary = missing_summary[missing_summary["Eksik_Sayisi"] > 0]
    print("--- Sütun Bazında Eksik Değer Raporu ---")
    print(missing_summary.to_string())
    
    # Eksik Değerleri Ele Alma Yöntemleri
    print("\n[Eksik Değer Çözüm Stratejileri]:")
    print(" -> Sayısal (Normal dağılım/Simetrik): Ortalama (Mean) ile doldurma")
    print(" -> Sayısal (Aykırı değer içeren / Çarpık): Medyan (Median) ile doldurma (Aykırılıktan etkilenmez)")
    print(" -> Kategorik: Mod (En çok tekrar eden) veya 'Bilinmeyen' ile doldurma")
    
    df_filled = df.copy()
    
    # Sayısal eksikleri doldurma (Aykırılık ihtimaline karşı medyan tercih edilir)
    for col in ["Yas", "Gelir", "Kredi_Skoru", "Aylik_Harcama"]:
        med_val = df_filled[col].median()
        df_filled[col] = df_filled[col].fillna(med_val)
        print(f" -> '{col}' sütunundaki eksikler Medyan ({med_val:.1f}) ile dolduruldu.")
        
    # Kategorik eksikleri doldurma (Mod)
    mode_dep = df_filled["Departman"].mode()[0]
    df_filled["Departman"] = df_filled["Departman"].fillna("Bilinmiyor")
    print(f" -> 'Departman' sütunundaki eksikler 'Bilinmiyor' olarak etiketlendi.")
    
    print(f"\nEksik Değer Doldurma Sonrası Toplam Eksik: {df_filled.isna().sum().sum()}")
    
    # =========================================================================
    # 3. AYKIRI DEĞER (OUTLIER) ANALİZİ VE MANTIĞI
    # =========================================================================
    print("\n" + "=" * 70)
    print("3. AYKIRI DEĞER (OUTLIER) ANALİZİ (1.5 x IQR KURALI)")
    print("=" * 70)
    print("""
    [IQR (Interquartile Range) YÖNTEMİ]:
    - Q1: 25. Yüzdelik Dilim (Verinin ilk %25'lik kısmı)
    - Q3: 75. Yüzdelik Dilim (Verinin ilk %75'lik kısmı)
    - IQR = Q3 - Q1
    - Alt Eşik: Q1 - 1.5 * IQR
    - Üst Eşik: Q3 + 1.5 * IQR
    """)
    
    def detect_outliers_iqr(series, name):
        s = series.dropna()
        q1 = s.quantile(0.25)
        q3 = s.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        
        outliers = s[(s < lower) | (s > upper)]
        return {
            "col": name,
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
            "lower": lower,
            "upper": upper,
            "outliers": outliers.tolist(),
            "count": len(outliers)
        }
        
    outlier_cols = ["Yas", "Gelir", "Kredi_Skoru", "Aylik_Harcama"]
    for c in outlier_cols:
        res = detect_outliers_iqr(df[c], c)
        print(f"\n--- {c} Kolonu Aykırı Değer İncelemesi ---")
        print(f" -> Q1: {res['q1']:.2f}, Q3: {res['q3']:.2f}, IQR: {res['iqr']:.2f}")
        print(f" -> Alt Sınır: {res['lower']:.2f}, Üst Sınır: {res['upper']:.2f}")
        print(f" -> Tespit Edilen Aykırı Sayısı: {res['count']}")
        if res["count"] > 0:
            print(f" -> Aykırı Değerler: {res['outliers']}")
            
    # =========================================================================
    # 4. AYKIRI DEĞERLERİN İSTATİSTİĞE ETKİSİ VE ÇÖZÜMLER
    # =========================================================================
    print("\n" + "=" * 70)
    print("4. AYKIRI DEĞERLERİN İSTATİSTİĞE ETKİSİ (GELİR KOLONU ÖRNEĞİ)")
    print("=" * 70)
    
    s_gelir = df["Gelir"].dropna()
    print(f"Ham Gelir Ortalaması : {s_gelir.mean():,.2f} TL (950.000 TL ortalamayı yukarı çekiyor)")
    print(f"Ham Gelir Medyanı     : {s_gelir.median():,.2f} TL (Aykırılıktan etkilenmedi)")
    
    # 1. Yöntem: Aykırı Değeri Silme (Trimming)
    res_gelir = detect_outliers_iqr(df["Gelir"], "Gelir")
    s_trimmed = s_gelir[(s_gelir >= res_gelir["lower"]) & (s_gelir <= res_gelir["upper"])]
    print(f"\n[Yöntem 1 - Aykırı Silme]:")
    print(f" -> Kalan Veri Boyutu: {len(s_trimmed)} / {len(s_gelir)}")
    print(f" -> Yeni Ortalama     : {s_trimmed.mean():,.2f} TL")
    
    # 2. Yöntem: Baskılama (Winsorization / Capping)
    s_capped = s_gelir.clip(lower=res_gelir["lower"], upper=res_gelir["upper"])
    print(f"\n[Yöntem 2 - Baskılama (Capping/Winsorization)]:")
    print(f" -> 950.000 TL değeri üst sınır olan {res_gelir['upper']:,.2f} TL'ye baskılandı.")
    print(f" -> Yeni Ortalama     : {s_capped.mean():,.2f} TL")
    
    print("\n" + "=" * 70)
    print("                    ANALİZ VE DOĞRULAMA TAMAMLANDI")
    print("=" * 70)

if __name__ == "__main__":
    main()
