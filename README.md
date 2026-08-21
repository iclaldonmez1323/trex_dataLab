# trex DataLab - Precision Data Platform 🚀

Her türlü tabular (tablo yapısındaki) veri setini otomatik olarak analiz eden, veri kalitesini denetleyen, görselleştiren ve makine öğrenmesi modelleriyle uçtan uca tahminleme sunan dinamik bir veri analitiği web platformu.

## 📌 Proje Özeti
trex DataLab; kullanıcıların yüklediği herhangi bir `.csv` veri setini anında işleyerek eksik veri kontrollerinden istatistiksel dağılımlara, keşifsel veri analizinden (EDA) makine öğrenmesi tabanlı sınıflandırma ve regresyon modellerine kadar tüm analitik süreçleri tek bir çatı altında otomatize eder.

## ✨ Öne Çıkan Özellikler
* **Evrensel Veri Yükleme & Kalite Kontrolü:** Yüklenen herhangi bir CSV dosyasının satır/sütun boyutlarını, eksik/tekrar eden verilerini, sayısal ve kategorik değişken dağılımlarını anında raporlama.
* **Otomatik Veri Hazırlama & Ön İşleme:** Standartlaştırma (Scaling), kategorik kodlama (One-Hot Encoding) ve veri temizleme adımlarını dinamik yönetme.
* **İstatistiksel Analiz & Görselleştirme:** Değişkenler arası korelasyon haritaları, dağılım histogramları ve kutu grafikleri (Boxplot) ile derinlemesine analiz.
* **Makine Öğrenmesi & Model Eğitimi:** Sınıflandırma ve regresyon algoritmalarını (Logistic Regression, Decision Tree, Random Forest vb.) otomatik eğitme, karşılaştırma ve metrik analizi (Recall, F1-Score, PR-AUC).
* **Model Optimizasyonu:** Stratified K-Fold Cross Validation ve GridSearchCV ile otomatik hiperparametre optimizasyonu.

## 🛠️ Kullanılan Teknolojiler
* **Programlama Dili:** Python
* **Veri Analitiği & Modelleme:** Pandas, NumPy, Scikit-learn, SciPy
* **Görselleştirme:** Matplotlib, Seaborn

## 🚀 Kurulum ve Çalıştırma
```bash
# Projeyi klonlayın
git clone [https://github.com/iclaldonmez1323/trex_dataLab.git](https://github.com/iclaldonmez1323/trex_dataLab.git)

# Proje dizinine geçin
cd trex_dataLab

# Gerekli paketleri yükleyin
pip install -r requirements.txt

# Uygulamayı başlatın
python main.py
