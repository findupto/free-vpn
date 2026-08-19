@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [1/6] Checking Python and PyInstaller...
where py >nul 2>nul || (echo Python launcher not found.& exit /b 1)
pyinstaller --version >nul 2>nul || (echo PyInstaller not found. Run: py -m pip install pyinstaller& exit /b 1)

if not exist client\launcher.py (echo client\launcher.py missing.& exit /b 1)
if not exist client\resilient.py (echo client\resilient.py missing.& exit /b 1)

echo [2/6] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist FinduptoVPN.spec del /q FinduptoVPN.spec
if exist installer\dist rmdir /s /q installer\dist
if not exist installer mkdir installer

echo [3/6] Building resilient Fast VPN 4.0.0 client...
pyinstaller --noconfirm --clean --onefile --windowed --name FinduptoVPN --paths client client\launcher.py
if errorlevel 1 exit /b 1
if not exist dist\FinduptoVPN.exe (echo EXE build failed.& exit /b 1)

echo [4/6] Downloading official OpenVPN MSI with multi-method fallback...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $urls=@('https://build.openvpn.net/downloads/releases/latest/openvpn-latest-stable-amd64.msi','https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.5-I001-amd64.msi','https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.4-I002-amd64.msi'); $out=(Join-Path (Get-Location) 'installer\openvpn-amd64.msi'); foreach($u in $urls){Remove-Item $out -Force -ErrorAction SilentlyContinue; try{Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $out -TimeoutSec 30 -ErrorAction Stop;if((Get-Item $out).Length -gt 4000000){exit 0}}catch{}; Remove-Item $out -Force -ErrorAction SilentlyContinue; try{curl.exe --fail --silent --show-error --location --connect-timeout 8 --max-time 45 -A 'Findupto-Free-VPN-Build/4.0' -o $out $u;if($LASTEXITCODE -eq 0 -and (Get-Item $out).Length -gt 4000000){exit 0}}catch{}}; exit 1"
if errorlevel 1 (echo OpenVPN MSI download failed.& exit /b 1)
if not exist installer\openvpn-amd64.msi (echo OpenVPN MSI missing.& exit /b 1)

for %%F in (installer\openvpn-amd64.msi) do if %%~zF LSS 4000000 (echo OpenVPN MSI is suspiciously small.& exit /b 1)

echo [5/6] Building installer...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (echo Inno Setup 6 is not installed.& exit /b 2)
"%ISCC%" installer\FinduptoVPN.iss
if errorlevel 1 exit /b 1
if not exist installer\dist\Findupto-Free-VPN-Setup.exe (echo Installer build failed.& exit /b 1)

echo [6/6] BUILD SUCCESSFUL
echo Client: dist\FinduptoVPN.exe
echo Installer: installer\dist\Findupto-Free-VPN-Setup.exe
endlocal
