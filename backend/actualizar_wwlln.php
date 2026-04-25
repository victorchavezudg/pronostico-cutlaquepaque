<?php
/**
 * actualizar_wwlln.php
 * ─────────────────────────────────────────────────────────────────────────────
 * Endpoint llamado automáticamente por la página cuando alguien la visita.
 * Verifica si los datos WWLLN tienen más de 6 horas; si es así, ejecuta el
 * script Python que los descarga y procesa.
 *
 * La página llama a este script en segundo plano (sin bloquear la UI).
 * El script Python solo corre si los datos están desactualizados, por lo que
 * las visitas frecuentes no generan trabajo innecesario.
 *
 * Requisitos del servidor:
 *   - PHP con shell_exec() habilitado
 *   - Python 3 instalado en el servidor
 *   - Permisos de escritura en la carpeta wwlln/
 * ─────────────────────────────────────────────────────────────────────────────
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');

// ── Rutas ──────────────────────────────────────────────────────────────────
$dirPagina  = realpath(dirname(__FILE__) . '/..');
$indexFile  = $dirPagina . '/wwlln/index.json';
$scriptPy   = dirname(__FILE__) . '/wwlln_updater.py';
$maxEdadSeg = 6 * 3600;   // actualizar si los datos tienen más de 6 horas

// ── ¿Los datos ya son recientes? ───────────────────────────────────────────
if (file_exists($indexFile)) {
    $edadSeg = time() - filemtime($indexFile);
    if ($edadSeg < $maxEdadSeg) {
        echo json_encode([
            'status'     => 'ok',
            'mensaje'    => 'Datos recientes — sin actualización necesaria',
            'edad_h'     => round($edadSeg / 3600, 1),
            'proximo_h'  => round(($maxEdadSeg - $edadSeg) / 3600, 1),
        ]);
        exit;
    }
}

// ── Verificar que shell_exec esté disponible ───────────────────────────────
if (!function_exists('shell_exec') || ini_get('safe_mode')) {
    echo json_encode([
        'status'  => 'no_disponible',
        'mensaje' => 'shell_exec no está habilitado en este servidor. '
                   . 'Configura un cron job para ejecutar wwlln_updater.py.',
    ]);
    exit;
}

// ── Detectar Python ────────────────────────────────────────────────────────
$python = trim((string) shell_exec('which python3 2>/dev/null'));
if (!$python) {
    $python = trim((string) shell_exec('which python 2>/dev/null'));
}
if (!$python) {
    echo json_encode([
        'status'  => 'error',
        'mensaje' => 'Python no encontrado en el servidor (probado: python3, python)',
    ]);
    exit;
}

// ── Ejecutar el actualizador ───────────────────────────────────────────────
$cmd    = $python . ' ' . escapeshellarg($scriptPy) . ' 2>&1';
$output = (string) shell_exec($cmd);

// ── Verificar resultado ────────────────────────────────────────────────────
if (file_exists($indexFile) && (time() - filemtime($indexFile)) < 120) {
    echo json_encode([
        'status'  => 'actualizado',
        'mensaje' => 'Datos WWLLN descargados y procesados correctamente',
    ]);
} else {
    echo json_encode([
        'status'   => 'error',
        'mensaje'  => 'El script terminó pero no generó index.json',
        'detalle'  => substr($output, 0, 600),
    ]);
}
