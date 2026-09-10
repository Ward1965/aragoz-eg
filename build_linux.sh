#!/usr/bin/env bash
# Aragoz Lite - Linux build (Ubuntu/Debian)
# Usage: ./build_linux.sh
#
# المتطلبات قبل التشغيل على Ubuntu/Debian:
#   sudo apt update && sudo apt install -y python3 python3-pip python3-venv \
#       libgtk-3-0t64 libwebkit2gtk-4.1-0 gir1.2-webkit2-4.1 gir1.2-gtk-3.0
#
# ملاحظة: لا يمكن البناء من ويندوز؛ يجب التشغيل على Linux.
set -e
cd "$(dirname "$0")"

echo "==> Building Linux binary..."

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
pip install "pyinstaller>=6.0" "pywebview[gtk]>=5.0" "aiohttp>=3.9" "requests>=2.31" "qrcode>=7.4"

rm -rf build dist
pyinstaller --noconfirm --windowed --onefile \
    --name "Aragoz Lite" \
    --add-data "frontend:frontend" \
    --collect-all webview --collect-all aiohttp \
    --hidden-import webview.platforms.gtk \
    main.py

echo "==> Done: dist/Aragoz Lite"
echo "    لتشغيل: ./dist/'Aragoz Lite'  (يحتاج مكتبات WebKit2GTK مثبتة)"