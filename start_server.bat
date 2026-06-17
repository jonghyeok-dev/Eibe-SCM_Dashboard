@echo off
chcp 65001 >nul
echo ============================================
echo   SCM ERP Local Server Starting...
echo ============================================

REM 프로젝트 루트로 이동
cd /d "%~dp0"

REM 가상환경 활성화
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] Virtual environment activated.
) else (
    echo [WARN] Virtual environment not found. Using system Python.
)

REM Uvicorn 서버 구동
echo [INFO] Starting Uvicorn on 0.0.0.0:8000 ...
uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
