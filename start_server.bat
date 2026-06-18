@echo off
echo ============================================
echo   SCM ERP Local Server Starting...
echo ============================================

cd /d "%~dp0"

echo [INFO] Checking virtual environment...

if not exist "venv\Scripts\activate.bat" (
    echo [INFO] venv not found. Creating virtual environment...
    where py >nul 2>nul
    if %errorlevel%==0 (
        py -3 -m venv venv
    ) else (
        where python >nul 2>nul
        if %errorlevel%==0 (
            python -m venv venv
        ) else (
            echo [ERROR] Python not found. Please install Python 3.8+
            pause
            exit /b 1
        )
    )

    if not exist "venv\Scripts\activate.bat" (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )

    echo [OK] Virtual environment created.

    call venv\Scripts\activate.bat
    echo [INFO] Installing dependencies...
    python -m pip install --upgrade pip
    if exist "requirements.txt" (
        pip install -r requirements.txt
    )
    echo [OK] Dependencies installed.
) else (
    call venv\Scripts\activate.bat
    echo [OK] Virtual environment activated.
)

echo [INFO] Starting Uvicorn on 0.0.0.0:8000 ...
echo [INFO] Open browser: http://localhost:8000
uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
