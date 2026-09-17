$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

py -3.12 -m venv .venv-desktop
& .\.venv-desktop\Scripts\python.exe -m pip install --upgrade pip
& .\.venv-desktop\Scripts\python.exe -m pip install -r desktop\requirements.txt
& .\.venv-desktop\Scripts\pyinstaller.exe --noconfirm --clean desktop\RunningDashboard.spec

Write-Host "Build completata in $Root\dist"
