@echo off
:: ============================================================
::  Pronóstico Climatológico — CU Tlaquepaque
::  Abre la página principal y actualiza los datos WWLLN
::  (rayos) en segundo plano sin bloquear la apertura.
:: ============================================================

cd /d "%~dp0"

:: -- Actualizar datos WWLLN en segundo plano ----------------
::    El script descarga el KMZ de WWLLN y genera wwlln/index.json
::    El log queda en wwlln_log.txt para diagnóstico.
echo Actualizando datos de rayos WWLLN...
start /B "" python backend\wwlln_updater.py > wwlln_log.txt 2>&1

:: -- Abrir la página principal ------------------------------
start "" "%~dp0index.html"
