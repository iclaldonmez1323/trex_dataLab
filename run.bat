@echo off
echo trex DataLab baslatiliyor...
if exist "C:\Users\iclal\miniconda3\python.exe" (
    "C:\Users\iclal\miniconda3\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
) else (
    python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
)
pause
