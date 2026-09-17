# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPEC).resolve().parent.parent
webview_datas, webview_binaries, webview_hidden = collect_all("webview")

a = Analysis(
    [str(ROOT / "desktop" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=webview_binaries,
    datas=[
        (str(ROOT / "app" / "static"), "app/static"),
        (str(ROOT / "app" / "migrations"), "app/migrations"),
        (str(ROOT / "desktop" / "static"), "desktop/static"),
    ] + webview_datas,
    hiddenimports=webview_hidden + ["app.main"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RunningDashboard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
collection = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="RunningDashboard",
)

if sys.platform == "darwin":
    app = BUNDLE(
        collection,
        name="Running Dashboard.app",
        bundle_identifier="it.leobarra.runningdashboard",
        info_plist={
            "CFBundleDisplayName": "Running Dashboard",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
        },
    )
