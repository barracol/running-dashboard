# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

ROOT = Path(SPEC).resolve().parent.parent
VERSION_NAMESPACE = {}
exec((ROOT / "desktop" / "version.py").read_text(encoding="utf-8"), VERSION_NAMESPACE)
APP_VERSION = VERSION_NAMESPACE["APP_VERSION"]
WINDOWS_ICON = ROOT / "desktop" / "assets" / "RunningDashboard.ico"
MACOS_ICON = ROOT / "desktop" / "assets" / "RunningDashboard.icns"

a = Analysis(
    [str(ROOT / "desktop" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "app" / "static"), "app/static"),
        (str(ROOT / "app" / "migrations"), "app/migrations"),
        (str(ROOT / "desktop" / "static"), "desktop/static"),
    ],
    # pywebview and pythonnet ship their own PyInstaller hooks. Using
    # collect_all("webview") here duplicated Python.Runtime.dll as package
    # data and produced an unusable Windows bundle.
    hiddenimports=["app.main"],
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
    icon=str(WINDOWS_ICON if sys.platform == "win32" else MACOS_ICON),
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
        icon=str(MACOS_ICON),
        bundle_identifier="it.leobarra.runningdashboard",
        info_plist={
            "CFBundleDisplayName": "Running Dashboard",
            "CFBundleShortVersionString": APP_VERSION,
            "NSHighResolutionCapable": True,
        },
    )
