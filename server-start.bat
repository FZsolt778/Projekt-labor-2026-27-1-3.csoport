@echo off
setlocal
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" (echo Nincs .venv mappa. Hozd letre a virtualis kornyezetet. & goto :err)
if not exist ".env" (echo Nincs .env fajl. & goto :err)

"%PY%" -m alembic upgrade head
if errorlevel 1 (echo A migracio nem futott le. Fut az adatbazis? Inditsd: db-start.bat & goto :err)

echo.
echo  API:          http://127.0.0.1:8000
echo  Dokumentacio: http://127.0.0.1:8000/docs
echo  Leallitas:    Ctrl+C
echo.
"%PY%" -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir server
exit /b 0

:err
echo.
echo MEGSZAKADT.
pause
exit /b 1
