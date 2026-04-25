@echo off
:: ============================================================
::  Instalar tarea programada Windows — WWLLN Updater
::  CU Tlaquepaque · Centro de Estudios Medioambientales
::
::  Ejecuta wwlln_updater.py cada 6 horas:
::    00:00 · 06:00 · 12:00 · 18:00 (hora local)
::
::  IMPORTANTE: Ejecutar este script UNA SOLA VEZ como
::  Administrador (clic derecho → Ejecutar como administrador).
:: ============================================================

:: Verificar que se ejecuta como Administrador
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Este script requiere privilegios de Administrador.
    echo  Haz clic derecho sobre este archivo y elige
    echo  "Ejecutar como administrador".
    echo.
    pause
    exit /b 1
)

:: Ruta absoluta al directorio del backend (donde vive este .bat)
set "BACKEND_DIR=%~dp0"
:: Quitar la barra final si existe
if "%BACKEND_DIR:~-1%"=="\" set "BACKEND_DIR=%BACKEND_DIR:~0,-1%"

set "SCRIPT=%BACKEND_DIR%\wwlln_updater.py"
set "LOG=%BACKEND_DIR%\..\wwlln_log.txt"
set "TAREA=WWLLN_CUTlaquepaque"

echo.
echo ============================================================
echo   Instalando tarea programada: %TAREA%
echo   Script : %SCRIPT%
echo   Horario: 00:00, 06:00, 12:00, 18:00 (cada dia)
echo ============================================================
echo.

:: Eliminar tarea anterior si existe (para actualizarla sin error)
schtasks /delete /tn "%TAREA%" /f >nul 2>&1

:: Crear la tarea — corre python en segundo plano, sin ventana visible
schtasks /create ^
  /tn "%TAREA%" ^
  /tr "cmd /c python \"%SCRIPT%\" >> \"%LOG%\" 2>&1" ^
  /sc DAILY ^
  /st 00:00 ^
  /ri 360 ^
  /du 9999:59 ^
  /f ^
  /rl HIGHEST ^
  /ru "%USERNAME%"

if %errorlevel% equ 0 (
    echo.
    echo  OK  Tarea instalada correctamente.
    echo.
    echo  Proximas ejecuciones automaticas:
    echo    00:00 · 06:00 · 12:00 · 18:00 cada dia
    echo.
    echo  Para verificar: Programador de Tareas ^> %TAREA%
    echo  Para desinstalar: schtasks /delete /tn "%TAREA%" /f
    echo.
    echo  Ejecutando ahora por primera vez...
    echo  ^(El resultado se guardara en wwlln_log.txt^)
    echo.
    python "%SCRIPT%"
) else (
    echo.
    echo  ERROR al crear la tarea. Revisa los permisos e intenta
    echo  ejecutar de nuevo como Administrador.
    echo.
)

pause
