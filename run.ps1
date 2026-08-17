Write-Host "trex DataLab baslatiliyor..." -ForegroundColor Green

$pythonPath = "C:\Users\iclal\miniconda3\python.exe"

if (Test-Path $pythonPath) {
    & $pythonPath -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
} else {
    python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
}
