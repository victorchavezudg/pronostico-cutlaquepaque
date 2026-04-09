#!/usr/bin/env python3
"""
wwlln_updater.py
================
Descarga el KMZ público del World Wide Lightning Location Network (WWLLN),
extrae los rayos sobre México y región, y guarda un archivo GeoJSON por
cada descarga. Mantiene los últimos 80 archivos (≈ 20 días a 4 descargas/día).

URL pública WWLLN: https://wwlln.net/WWLLN.kmz
  → Se actualiza cada hora con 1 hora de datos globales (retraso ~6 h)

Archivos de salida:
  ../wwlln/wwlln_YYYY-MM-DD_HH00.geojson   → snapshot por descarga
  ../wwlln/index.json                        → índice de archivos disponibles

Uso manual:
  python wwlln_updater.py

Programar 4 veces al día (cada 6 horas):
  - Windows: Programador de Tareas → 00:00, 06:00, 12:00, 18:00
  - Linux/Mac: crontab -e  →  0 */6 * * * /usr/bin/python3 /ruta/wwlln_updater.py

Con esto se generan ~4 archivos/día → 80 archivos = 20 días de historial.

Dependencias:
  pip install requests
"""

import json
import os
import sys
import zipfile
import datetime
import re
import io

try:
    import requests
except ImportError:
    print("ERROR: Instala requests primero:")
    print("  pip install requests")
    sys.exit(1)

# ── Configuración ──────────────────────────────────────────────────────────────
WWLLN_URL  = "https://wwlln.net/WWLLN.kmz"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR    = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "wwlln"))
MAX_FILES  = 80   # 4 descargas/día × 20 días

# Bounding box: México + Centroamérica + Caribe + sur EE.UU.
LAT_MIN = 10.0
LAT_MAX = 36.0
LON_MIN = -122.0
LON_MAX = -76.0

# Colores por antigüedad dentro de la hora (r1=más reciente → amarillo)
COLORES = {
    "r1": "#FFFF00",
    "r2": "#00FF00",
    "r3": "#00CDFF",
    "r4": "#007FFF",
    "r5": "#0000FF",
    "r6": "#00008B",
}
ETIQUETAS = {
    "r1": "0-10 min",
    "r2": "10-20 min",
    "r3": "20-30 min",
    "r4": "30-40 min",
    "r5": "40-50 min",
    "r6": "50-60 min",
}

# ── Descarga ───────────────────────────────────────────────────────────────────

def descargar_kmz():
    print(f"  Descargando {WWLLN_URL} ...")
    try:
        r = requests.get(WWLLN_URL, timeout=30)
        r.raise_for_status()
        print(f"  ✓ Descargado ({len(r.content)/1024:.1f} KB)")
        return r.content
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None

# ── Parseo KML ─────────────────────────────────────────────────────────────────

def parsear_kml(kml_texto):
    """Extrae rayos del KML filtrando por bounding box."""
    rayos = []
    for pm in re.findall(r'<Placemark>(.*?)</Placemark>', kml_texto, re.DOTALL):
        try:
            lat_m = re.search(r'Lat:\s*([-\d.]+)', pm)
            lon_m = re.search(r'Lon:\s*([-\d.]+)', pm)
            if not lat_m or not lon_m:
                continue
            lat = float(lat_m.group(1))
            lon = float(lon_m.group(1))
            if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
                continue

            nombre_m  = re.search(r'<name>(.*?)</name>', pm)
            res_m     = re.search(r'Residual:\s*([\d.]+)', pm)
            est_m     = re.search(r'detected at (\d+) WWLLN', pm)
            style_m   = re.search(r'<styleUrl>#(r\d+)</styleUrl>', pm)
            style     = style_m.group(1) if style_m else "r6"

            rayos.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "hora":       nombre_m.group(1).strip() if nombre_m else "",
                    "residual":   float(res_m.group(1)) if res_m else None,
                    "estaciones": int(est_m.group(1))   if est_m else None,
                    "style":      style,
                    "color":      COLORES.get(style, "#FFFFFF"),
                    "antiguedad": ETIQUETAS.get(style, ""),
                }
            })
        except Exception:
            continue
    return rayos

# ── Gestión de archivos ────────────────────────────────────────────────────────

def limpiar_archivos_viejos():
    """Elimina archivos más allá del límite MAX_FILES."""
    archivos = sorted([
        f for f in os.listdir(OUT_DIR)
        if re.match(r'wwlln_\d{4}-\d{2}-\d{2}_\d{4}\.geojson', f)
    ])
    eliminados = 0
    while len(archivos) > MAX_FILES:
        viejo = archivos.pop(0)
        try:
            os.remove(os.path.join(OUT_DIR, viejo))
            print(f"  🗑  Eliminado: {viejo}")
            eliminados += 1
        except Exception as e:
            print(f"  ✗ No se pudo eliminar {viejo}: {e}")
    return eliminados


def actualizar_indice():
    """
    Genera index.json con la lista de archivos disponibles,
    agrupados por fecha para facilitar la navegación en la página.
    """
    archivos = sorted([
        f for f in os.listdir(OUT_DIR)
        if re.match(r'wwlln_\d{4}-\d{2}-\d{2}_\d{4}\.geojson', f)
    ], reverse=True)

    # Agrupar por fecha
    por_fecha = {}
    for nombre in archivos:
        # wwlln_YYYY-MM-DD_HHMM.geojson
        m = re.match(r'wwlln_(\d{4}-\d{2}-\d{2})_(\d{4})\.geojson', nombre)
        if not m:
            continue
        fecha = m.group(1)
        hora  = m.group(2)[:2] + ":" + m.group(2)[2:]

        # Leer total de rayos del archivo
        try:
            with open(os.path.join(OUT_DIR, nombre), "r", encoding="utf-8") as f:
                gj = json.load(f)
            total = gj.get("total_rayos", 0)
        except Exception:
            total = 0

        if fecha not in por_fecha:
            por_fecha[fecha] = []
        por_fecha[fecha].append({
            "archivo": nombre,
            "hora":    hora,
            "total":   total,
        })

    # Construir lista de días ordenados (más reciente primero)
    dias = []
    for fecha in sorted(por_fecha.keys(), reverse=True):
        snapshots = por_fecha[fecha]
        total_dia = sum(s["total"] for s in snapshots)
        dias.append({
            "fecha":      fecha,
            "snapshots":  snapshots,
            "total_dia":  total_dia,
        })

    indice = {
        "generado":   datetime.datetime.utcnow().isoformat() + "Z",
        "total_dias": len(dias),
        "max_files":  MAX_FILES,
        "fuente":     "WWLLN — World Wide Lightning Location Network",
        "creditos":   "University of Washington | CU Tlaquepaque UdeG",
        "dias":       dias,
    }

    ruta = os.path.join(OUT_DIR, "index.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(indice, f, separators=(",", ":"), ensure_ascii=False)

    return len(dias)

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  WWLLN Updater — CU Tlaquepaque")
    print("=" * 60)

    os.makedirs(OUT_DIR, exist_ok=True)

    # 1. Descargar KMZ
    kmz_bytes = descargar_kmz()
    if not kmz_bytes:
        sys.exit(1)

    # 2. Extraer KML
    print("  Extrayendo KML...")
    try:
        with zipfile.ZipFile(io.BytesIO(kmz_bytes)) as z:
            kml_nombre = [n for n in z.namelist() if n.endswith(".kml")][0]
            kml_texto  = z.read(kml_nombre).decode("utf-8")
        total_global = kml_texto.count('<Placemark>')
        print(f"  ✓ KML extraído ({len(kml_texto)/1024:.0f} KB, {total_global} rayos globales)")
    except Exception as e:
        print(f"  ✗ Error al extraer KML: {e}")
        sys.exit(1)

    # 3. Parsear y filtrar región
    print(f"  Filtrando región México y alrededores...")
    features = parsear_kml(kml_texto)
    print(f"  ✓ {len(features)} rayos en la región")

    # 4. Nombre de archivo: wwlln_YYYY-MM-DD_HHMM.geojson
    ahora    = datetime.datetime.utcnow()
    nombre   = ahora.strftime("wwlln_%Y-%m-%d_%H%M.geojson")
    ruta_out = os.path.join(OUT_DIR, nombre)

    # 5. Guardar GeoJSON
    geojson = {
        "type":         "FeatureCollection",
        "fecha":        ahora.strftime("%Y-%m-%d"),
        "hora_utc":     ahora.strftime("%H:%M UTC"),
        "generado":     ahora.isoformat() + "Z",
        "total_rayos":  len(features),
        "fuente":       "WWLLN — World Wide Lightning Location Network",
        "creditos":     "University of Washington | CU Tlaquepaque UdeG",
        "region":       "México y región (10°-36°N, 76°-122°W)",
        "features":     features,
    }

    with open(ruta_out, "w", encoding="utf-8") as f:
        json.dump(geojson, f, separators=(",", ":"), ensure_ascii=False)

    size_kb = os.path.getsize(ruta_out) / 1024
    print(f"  ✓ Guardado: {nombre} ({size_kb:.1f} KB)")

    # 6. Limpiar archivos viejos
    limpiar_archivos_viejos()

    # 7. Actualizar índice
    n_dias = actualizar_indice()

    print()
    print("=" * 60)
    print(f"  ✅ LISTO")
    print(f"  Archivo         : {nombre}")
    print(f"  Rayos en región : {len(features)}")
    print(f"  Días en archivo : {n_dias} (máx {MAX_FILES} archivos)")
    print("=" * 60)


if __name__ == "__main__":
    main()
