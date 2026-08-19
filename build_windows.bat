@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [1/5] Checking Python and PyInstaller...
where py >nul 2>nul || (echo Python launcher not found.& exit /b 1)
pyinstaller --version >nul 2>nul || (echo PyInstaller not found. Run: py -m pip install pyinstaller& exit /b 1)

echo [2/5] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist FinduptoVPN.spec del /q FinduptoVPN.spec
if exist installer\dist rmdir /s /q installer\dist

if not exist installer mkdir installer

echo [3/5] Building Fast VPN 2.2.0 client...
pyinstaller --noconfirm --clean --onefile --windowed --name FinduptoVPN client\app.py
if errorlevel 1 exit /b 1
if not exist dist\FinduptoVPN.exe (echo EXE build failed.& exit /b 1)

echo [4/5] Downloading official OpenVPN MSI...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $urls=@('https://build.openvpn.net/downloads/releases/latest/openvpn-latest-stable-amd64.msi','https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.5-I001-amd64.msi','https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.4-I002-amd64.msi'); $out=(Join-Path (Get-Location) 'installer\openvpn-amd64.msi'); foreach($u in $urls){Remove-Item $out -Force -ErrorAction SilentlyContinue; try{Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $out -TimeoutSec 20 -ErrorAction Stop;if((Get-Item $out).Length -gt 4000000){exit 0}}catch{}; Remove-Item $out -Force -ErrorAction SilentlyContinue; try{curl.exe --fail --silent --show-error --location --connect-timeout 5 --max-time 30 -A 'Findupto-Free-VPN-Build' -o $out $u;if($LASTEXITCODE -eq 0 -and (Get-Item $out).Length -gt 4000000){exit 0}}catch{}}; exit 1"
if errorlevel 1 (echo OpenVPN MSI download failed.& exit /b 1)
if not exist installer\openvpn-amd64.msi (echo OpenVPN MSI missing.& exit /b 1)

echo [5/5] Building installer...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (echo Inno Setup 6 is not installed.& exit /b 2)
"%ISCC%" installer\FinduptoVPN.iss
if errorlevel 1 exit /b 1
if not exist installer\dist\Findupto-Free-VPN-Setup.exe (echo Installer build failed.& exit /b 1)

echo BUILD SUCCESSFUL
echo Client: dist\FinduptoVPN.exe
echo Installer: installer\dist\Findupto-Free-VPN-Setup.exe
endlocal
