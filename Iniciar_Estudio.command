#!/bin/bash
# ==============================================================================
# Yield Video Studio — Launcher para macOS
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "======================================================"
echo "    🎬 Yield Video Studio — Pipeline de Vídeo con IA  "
echo "======================================================"
echo ""

# Comprobar si ya hay una instancia escuchando en el puerto 8020
if lsof -i :8020 >/dev/null 2>&1; then
    echo "-> El servidor ya está en marcha en el puerto 8020."
    echo "-> Abriendo navegador..."
    open "http://127.0.0.1:8020/"
    echo ""
    echo "Para detener la instancia actual ejecuta: lsof -ti:8020 | xargs kill -9"
    exit 0
fi

echo "[1/2] Iniciando servidor FastAPI en http://127.0.0.1:8020..."
python3 app.py --puerto 8020 &
SERVER_PID=$!

echo "[2/2] Abriendo el estudio en tu navegador..."
sleep 2
open "http://127.0.0.1:8020/"

echo ""
echo "-> Estudio de Vídeo activo en: http://127.0.0.1:8020"
echo "-> Pulsa Ctrl+C para detener el servidor."
echo ""

trap "echo ''; echo 'Cerrando servidor...'; kill $SERVER_PID 2>/dev/null; exit" INT TERM EXIT
wait $SERVER_PID
