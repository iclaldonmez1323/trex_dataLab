import json
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# 1. Upload
with open('trex_datalab_test_rehberi.csv', 'rb') as f:
    r_up = client.post('/api/upload', files={'file': ('trex_datalab_test_rehberi.csv', f, 'text/csv')})
print('=== 1. YUKLEME (UPLOAD) ===')
print(json.dumps(r_up.json(), indent=2, ensure_ascii=False))

# 2. Initial Quality
r_q = client.get('/api/quality')
print('\n=== 2. ILK VERI KALITESI RAPORU ===')
q_data = r_q.json()
print('Score:', q_data['score'], 'Status:', q_data['score_status'])
print('Comparison:', q_data['comparison'])
print('Metrics:', q_data['metrics'])
print('Score Breakdown:', json.dumps(q_data['score_breakdown'], indent=2, ensure_ascii=False))
print('Outliers:', q_data['outliers'])
print('Cardinality:', q_data['cardinality'])
print('Constant cols:', q_data['constant_cols'])
print('Dtypes:', q_data['dtypes'])

# 3. Preprocessing Steps & Quality progression
print('\n=== 3. ADIM ADIM ON ISLEME VE KALITE SKORU DEGISIMI ===')
# Step A: Fill missing
client.post('/api/preprocessing/apply', json={'op': 'fill_missing', 'method': 'median'})
r_qa = client.get('/api/quality').json()
print(f"A) Eksik Doldurma Sonrasi -> Skor: {r_qa['score']} (Delta: +{r_qa['comparison']['delta']}), Eksik: {r_qa['missing']['total_missing']}")

# Step B: Drop duplicates
client.post('/api/preprocessing/apply', json={'op': 'drop_duplicates'})
r_qb = client.get('/api/quality').json()
print(f"B) Tekrar Silme Sonrasi -> Skor: {r_qb['score']} (Delta: +{r_qb['comparison']['delta']}), Satir: {r_qb['comparison']['processed_rows']}/{r_qb['comparison']['raw_rows']}, Tekrar: {r_qb['duplicates']['count']}")

# Step C: Outlier removal
client.post('/api/preprocessing/apply', json={'op': 'outlier_management', 'method': 'remove_iqr', 'columns': ['Yas', 'Gelir']})
r_qc = client.get('/api/quality').json()
print(f"C) Aykiri Deger Silme Sonrasi -> Skor: {r_qc['score']} (Delta: +{r_qc['comparison']['delta']}), Aykiri Sayisi: {r_qc['outliers']['total_outliers']}")

# Step D: Drop constant column
client.post('/api/preprocessing/apply', json={'op': 'drop_column', 'column': 'Ulke_Kodu'})
r_qd = client.get('/api/quality').json()
print(f"D) Sabit Kolon Silme Sonrasi -> Skor: {r_qd['score']} (Delta: +{r_qd['comparison']['delta']}), Sabit Kolon: {r_qd['metrics']['constant_cols']}")

# 4. ML Config
r_ml = client.get('/api/ml/config').json()
print('\n=== 4. ML KONFIGURASYONU & OTOMATIK HARIC TUTMA ===')
print('Auto Excluded:', r_ml['auto_excluded'])
for c in r_ml['columns']:
    print(f"- {c['name']}: should_exclude={c['should_exclude']}, reason='{c.get('exclude_reason')}', unique_ratio={c['unique_ratio']}")
