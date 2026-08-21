import os
import pandas as pd
import numpy as np

def create_sample_dataset():
    """
    Eksik ve Aykırı Değer Mantığını Test Etmek İçin Örnek Müşteri/Çalışan Veri Seti
    """
    np.random.seed(42)
    
    data = {
        "Musteri_ID": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 
                       111, 112, 113, 114, 115, 116, 117, 118, 119, 120],
        
        # Yas: 22-65 arası normal; 145 (Veri Giriş Hatası / Aykırı), 8 (Hatalı Giriş), NaN (MCAR/Eksik)
        "Yas": [25, 32, np.nan, 45, 52, 29, 38, 145, 24, 41, 
                36, np.nan, 48, 27, 8, 33, 58, 26, 35, 39],
        
        # Gelir (TL): 30k-120k normal; 950.000 (Üst Düzey Yönetici/Uç Değer), NaN (MNAR - Yüksek gelirliler bazen beyan etmez)
        "Gelir": [35000, 48000, 72000, np.nan, 95000, 32000, 68000, 950000, 28000, 62000, 
                  51000, 42000, 88000, 36000, 18000, 53000, np.nan, 38000, 60000, 75000],
        
        # Kredi_Skoru (0-100): Normal dağılım; NaN (Henüz kredi geçmişi yok - MAR)
        "Kredi_Skoru": [72.5, 84.0, 91.2, 68.0, 96.0, 55.4, 88.5, 99.0, 62.0, 78.4, 
                        81.0, np.nan, 92.8, 65.2, 45.0, 79.5, 94.0, 60.5, 82.0, np.nan],
        
        # Aylik_Harcama (TL): 1000-25000 arası; 180.000 (Aykırı harcama)
        "Aylik_Harcama": [3200, 4500, 6800, 5100, 8900, 2900, 6400, 180000, 2600, 5800, 
                          4900, 3900, 8200, 3400, 1500, 5000, 8800, 3600, 5600, 7100],
        
        # Departman: Kategorik; NaN (Atanmamış / Eksik değer)
        "Departman": ["Yazilim", "Satis", "Pazarlama", "Yazilim", "Yonetim", 
                      "IK", "Finans", "Yonetim", "Satis", np.nan, 
                      "Finans", "Yazilim", "Satis", "IK", "Stajyer", 
                      "Yazilim", np.nan, "Satis", "IK", "Pazarlama"],
        
        # Durum: Kategorik
        "Durum": ["Aktif", "Aktif", "Pasif", "Aktif", "Aktif", 
                  "Aktif", "Aktif", "Aktif", "Pasif", "Aktif", 
                  "Aktif", "Aktif", "Aktif", "Aktif", "Pasif", 
                  "Aktif", "Aktif", "Aktif", "Aktif", "Aktif"]
    }
    
    df = pd.DataFrame(data)
    return df

if __name__ == "__main__":
    df = create_sample_dataset()
    
    # Save to data/ and root
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    data_dir = os.path.join(root_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    target_data_file = os.path.join(data_dir, "ornek_veri_seti.csv")
    df.to_csv(target_data_file, index=False, encoding="utf-8")
    
    target_root_file = os.path.join(root_dir, "ornek_veri_seti.csv")
    df.to_csv(target_root_file, index=False, encoding="utf-8")
    
    print(f"'{target_data_file}' başarıyla oluşturuldu! ({len(df)} satır, {len(df.columns)} kolon)")
