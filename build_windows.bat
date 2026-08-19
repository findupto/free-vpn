@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [1/6] Checking Python and PyInstaller...
where py >nul 2>nul || (echo Python launcher not found.& exit /b 1)
pyinstaller --version >nul 2>nul || (echo PyInstaller not found. Run: py -m pip install pyinstaller& exit /b 1)

echo [2/6] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist FinduptoVPN.spec del /q FinduptoVPN.spec
if exist installer\dist rmdir /s /q installer\dist

echo [3/6] Building Windows client...
pyinstaller --noconfirm --clean --onefile --windowed --name FinduptoVPN client\app.py
if errorlevel 1 exit /b 1
if not exist dist\FinduptoVPN.exe (echo EXE build failed.& exit /b 1)

echo [4/6] Downloading official VPN runtimes with fallback methods...
if not exist installer mkdir installer
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; function D($urls,$out){foreach($u in $urls){try{Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $out -ErrorAction Stop;if((Get-Item $out).Length -gt 100000){return}}catch{};try{curl.exe --fail --location --retry 4 --retry-all-errors --connect-timeout 10 -o $out $u;if($LASTEXITCODE -eq 0 -and (Get-Item $out).Length -gt 100000){return}}catch{};try{Start-BitsTransfer -Source $u -Destination $out -ErrorAction Stop;if((Get-Item $out).Length -gt 100000){return}}catch{}};throw 'All download methods failed'}; D @('https://download.wireguard.com/windows-client/wireguard-amd64-1.0.1.msi') 'installer\wireguard-amd64.msi'; D @('https://build.openvpn.net/downloads/releases/latest/openvpn-latest-stable-amd64.msi','https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.5-I001-amd64.msi','https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.4-I002-amd64.msi','https://swupdate.openvpn.org/community/releases/OpenVPN-2.6.22-I001-amd64.msi') 'installer\openvpn-amd64.msi'"
if errorlevel 1 exit /b 1
if not exist installer\openvpn-amd64.msi (echo OpenVPN MSI missing.& exit /b 1)
if not exist installer\wireguard-amd64.msi (echo WireGuard MSI missing.& exit /b 1)

echo [5/6] Locating Inno Setup...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (echo Inno Setup 6 is not installed.& exit /b 2)

echo [6/6] Building installer...
"%ISCC%" installer\FinduptoVPN.iss
if errorlevel 1 exit /b 1
if not exist installer\dist\Findupto-Free-VPN-Setup.exe (echo Installer build failed.& exit /b 1)

echo BUILD SUCCESSFUL
echo Client: dist\FinduptoVPN.exe
echo Installer: installer\dist\Findupto-Free-VPN-Setup.exe
endlocal
