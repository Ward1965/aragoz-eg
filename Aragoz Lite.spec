# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_all

spec_dir = os.path.abspath(SPECPATH)

datas = [(os.path.join(spec_dir, "frontend"), "frontend")]
binaries = []
hiddenimports = []

for pkg in ("webview", "aiohttp", "qrcode", "requests"):
    tmp = collect_all(pkg)
    datas += tmp[0]
    binaries += tmp[1]
    hiddenimports += tmp[2]

if sys.platform == "win32":
    hiddenimports += ["webview.platforms.edgechromium", "webview.platforms.winforms"]
    icon = os.path.join(spec_dir, "aragoz.ico")
elif sys.platform == "darwin":
    hiddenimports += ["webview.platforms.cocoa"]
    icon = os.path.join(spec_dir, "aragoz.icns")
else:
    hiddenimports += ["webview.platforms.gtk"]
    icon = None

a = Analysis(
    [os.path.join(spec_dir, "main.py")],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Aragoz Lite",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[icon] if icon else None,
)