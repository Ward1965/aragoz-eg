#!/usr/bin/env bash
# Aragoz Lite - macOS build
# Usage:
#   ./build_mac.sh x86_64      -> Mac Intel (النظام القديم)
#   ./build_mac.sh arm64       -> Mac Apple Silicon M (النظام الجديد)
#   ./build_mac.sh universal2  -> نسخة واحدة تعمل على الاثنين (الافتراضي)
#
# ملاحظة: لا يمكن البناء من ويندوز؛ يجب تشغيل هذا السكربت على جهاز Mac.
# يتطلب: Xcode Command Line Tools (xcode-select --install)
set -e
cd "$(dirname "$0")"

ARCH="${1:-universal2}"
echo "==> Building macOS for arch: $ARCH"

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
pip install "pyinstaller>=6.0" "pywebview>=5.0" "aiohttp>=3.9" "requests>=2.31" "qrcode>=7.4"
pip install pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-WebKit pyobjc-framework-Quartz

rm -rf build dist
pyinstaller --noconfirm --windowed --onefile \
    --name "Aragoz Lite" \
    --icon "aragoz.icns" \
    --add-data "frontend:frontend" \
    --collect-all webview --collect-all aiohttp \
    --hidden-import webview.platforms.cocoa \
    --target-arch "$ARCH" \
    main.py

# توقيع مؤقت (ad-hoc) يساعد في فك حظر التشغيل المحلي
codesign --force --deep --sign - "dist/Aragoz Lite.app" 2>/dev/null || true

echo "==> Done: dist/Aragoz Lite.app  ($ARCH)"
echo "    إن اعترضك Gatekeeper: click-right > Open  أو:"
echo "    xattr -dr com.apple.quarantine \"dist/Aragoz Lite.app\""
echo "    ملاحظة: إن فشل universal2 مع aiohttp، ابنِ نسختين: ./build_mac.sh x86_64 و ./build_mac.sh arm64"