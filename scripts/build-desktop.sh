#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m venv .venv-desktop
.venv-desktop/bin/python -m pip install --upgrade pip
.venv-desktop/bin/python -m pip install -r desktop/requirements.txt
.venv-desktop/bin/pyinstaller --noconfirm --clean desktop/RunningDashboard.spec

echo "Build completata in $ROOT/dist"
