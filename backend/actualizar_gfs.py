#!/usr/bin/env python3
"""
actualizar_gfs.py
=================
Descarga la malla de pronóstico GFS 0.25° (NOAA) para México
vía OpenDAP y genera ../datos_malla.json para la página de climatología.

Dependencias:
    pip install xarray pydap numpy requests

Uso manual:
    python actualizar_gfs.py

Programar automáticamente cada 6 horas:
    - Windows: Programador de Tareas → cada 6h → python actualizar_gfs.py
    - Linux/Mac: crontab -e → 0 */6 * * * /usr/bin/python3 /ruta/actualizar_gfs.py

El archivo datos_malla.json se guarda en la carpeta padre (junto al HTML).
La página web lo detecta automáticamente al cargar.
"""

import json
import math
import datetime
import os
import sys

# ── Verificar dependencias ─────────────────────────────────────────────────────
try:
    import xarray as xr
    import numpy as np
except ImportError:
    print("ERROR: Instala las dependencias primero:")
    print("  pip install xarray pydap numpy")
    sys.exit(1)

# ── Configuración ──────────────────────────────────────────────────────────────
# Bounding box México con margen (en convención 0-360° para NOMADS)
LAT_MAX     = 33.0    # Norte
LAT_MIN     = 14.0    # Sur
LON_MIN_360 = 240.0   # Oeste (-120°)
LON_MAX_360 = 276.5   # Este  (-83.5°)

# Ruta de salida: carpeta padre del script (misma que el HTML)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT     = os.path.join(SCRIPT_DIR, "..", "datos_malla.json")

# ── Funciones auxiliares ───────────────────────────────────────────────────────
def ciclo_disponible():
    """
    Determina el ciclo GFS más reciente disponible.
    GFS se publica con ~4.5h de retraso tras el tiempo de análisis.
    Ciclos: 00z, 06z, 12z, 18z
    """
    utc = datetime.datetime.utcnow() - datetime.timedelta(hours=4, minutes=30)
    ciclo_h = (utc.hour // 6) * 6
    return utc.strftime("%Y%m%d"), f"{ciclo_h:02d}"

def url_opendap(fecha, hora):
    return (
        f"https://nomads.ncep.noaa.gov/dods/gfs_0p25"
        f"/gfs{fecha}/gfs_0p25_{hora}z"
    )

def arr_a_lista(arr, transform=None):
    """Convierte numpy array a lista Python plana con transformación opcional."""
    if arr is None:
        return None
    result = []
    for v in arr.flatten():
        try:
            fv = float(v)
            if math.isnan(fv) or math.isinf(fv):
                result.append(None)
            else:
                result.append(round(transform(fv) if transform else fv, 2))
        except Exception:
            result.append(None)
    return result

# ── Lógica principal ───────────────────────────────────────────────────────────
def main():
    fecha, hora = ciclo_disponible()
    url = url_opendap(fecha, hora)

    print("=" * 60)
    print("  Actualización malla GFS México")
    print("=" * 60)
    print(f"  Ciclo: {fecha} {hora}z")
    print(f"  URL  : {url}")
    print()

    # ── Abrir dataset remoto (OpenDAP, solo metadatos) ─────────────────────────
    try:
        print("Conectando al servidor NOMADS...")
        ds = xr.open_dataset(url, engine="pydap", mask_and_scale=True)
        print("  ✓ Conexión exitosa")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        print()
        print("Posibles causas:")
        print("  - Sin conexión a internet")
        print("  - El ciclo aún no está disponible (espera 30 min y reintenta)")
        print("  - Servidor NOMADS en mantenimiento")
        sys.exit(1)

    # ── Selección geográfica México ────────────────────────────────────────────
    lat_sel = slice(LAT_MAX, LAT_MIN)       # GFS: lat decreciente (N→S)
    lon_sel = slice(LON_MIN_360, LON_MAX_360)

    # Usar análisis (t=0) para temperatura/humedad,
    # y pronóstico f006 (t=1) para precipitación acumulada
    print("Extrayendo variables para México...")

    VARS = {
        # nombre_gfs: (nombre_salida, índice_tiempo, función_transformación)
        "tmp2m":   ("temperatura",  0, lambda k: k - 273.15),  # K → °C
        "dpt2m":   ("rocio",        0, lambda k: k - 273.15),  # K → °C
        "rh2m":    ("humedad",      0, None),                   # %
        "ugrd10m": ("_u",           0, None),                   # m/s (componente)
        "vgrd10m": ("_v",           0, None),                   # m/s (componente)
        "apcpsfc": ("precip_mm",    1, None),                   # kg/m² = mm
        "tcdcclm": ("nubosidad",    0, None),                   # %
        "pressfc": ("presion_hpa",  0, lambda p: p / 100),      # Pa → hPa
    }

    datos = {}
    for var_gfs, (nombre, t_idx, transform) in VARS.items():
        try:
            arr = (
                ds[var_gfs]
                .isel(time=t_idx)
                .sel(lat=lat_sel, lon=lon_sel)
                .values
            )
            datos[nombre] = arr_a_lista(arr, transform)
            n_validos = sum(1 for x in datos[nombre] if x is not None)
            print(f"  ✓ {var_gfs:12s} → {nombre} ({n_validos} puntos válidos)")
        except Exception as e:
            print(f"  ✗ {var_gfs:12s}: {e}")
            datos[nombre] = None

    # ── Calcular velocidad y dirección del viento ──────────────────────────────
    u_list = datos.pop("_u", None)
    v_list = datos.pop("_v", None)
    if u_list and v_list:
        datos["viento_kmh"] = []
        datos["viento_dir"] = []
        for u, v in zip(u_list, v_list):
            if u is None or v is None:
                datos["viento_kmh"].append(None)
                datos["viento_dir"].append(None)
            else:
                spd = math.sqrt(u**2 + v**2) * 3.6         # m/s → km/h
                # Dirección meteorológica: 0=N, 90=E, 180=S, 270=O
                direc = (270 - math.degrees(math.atan2(v, u))) % 360
                datos["viento_kmh"].append(round(spd, 1))
                datos["viento_dir"].append(round(direc, 0))
        print(f"  ✓ viento calculado (speed + dirección)")

    # ── Coordenadas de la malla seleccionada ───────────────────────────────────
    lats_arr = ds.lat.sel(lat=lat_sel).values          # N → S
    lons_arr = ds.lon.sel(lon=lon_sel).values - 360    # 0-360 → -180 a +180

    ds.close()

    # ── Construir JSON de salida ───────────────────────────────────────────────
    ny = len(lats_arr)
    nx = len(lons_arr)

    resultado = {
        "fuente":    "NOAA GFS 0.25°",
        "ciclo":     f"{fecha} {hora}z",
        "generado":  datetime.datetime.utcnow().isoformat() + "Z",
        "ny":        ny,
        "nx":        nx,
        "lats":      [round(float(x), 4) for x in lats_arr],   # N → S
        "lons":      [round(float(x), 4) for x in lons_arr],   # W → E
        **datos,
    }

    # ── Guardar ───────────────────────────────────────────────────────────────
    out_path = os.path.normpath(OUTPUT)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, separators=(",", ":"))

    size_kb = os.path.getsize(out_path) / 1024
    print()
    print("=" * 60)
    print(f"  ✅ LISTO")
    print(f"  Archivo : {out_path}")
    print(f"  Tamaño  : {size_kb:.1f} KB")
    print(f"  Malla   : {ny} filas × {nx} columnas = {ny*nx} puntos")
    print(f"  Lat     : {lats_arr[0]:.2f}°N → {lats_arr[-1]:.2f}°N")
    print(f"  Lon     : {lons_arr[0]:.2f}° → {lons_arr[-1]:.2f}°")
    print(f"  Ciclo   : {resultado['ciclo']}")
    print("=" * 60)

if __name__ == "__main__":
    main()
