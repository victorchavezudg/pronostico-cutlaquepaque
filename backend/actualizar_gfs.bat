@echo off
echo ============================================
echo   Actualizando malla GFS para Mexico
echo ============================================
echo.
cd /d "%~dp0"
python actualizar_gfs.py
echo.
pause
