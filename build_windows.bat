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

 echo [4/6] Downloading official VPN runtimes...
if not exist installer mkdir installer
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://download.wireguard.com/windows-client/wireguard-amd64-1.0.1.msi' -OutFile 'installer\wireguard-amd64.msi'"
if errorlevel 1 exit /b 1
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.5-I001-amd64.msi' -OutFile 'installer\openvpn-amd64.msi'"
if errorlevel 1 exit /b 1

 echo [5/6] Locating Inno Setup...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
  echo Inno Setup 6 is not installed.
  echo Install it from the official Inno Setup website, then run this script again.
  exit /b 2
)

 echo [6/6] Building installer...
"%ISCC%" installer\FinduptoVPN.iss
if errorlevel 1 exit /b 1
if not exist installer\dist\Findupto-Free-VPN-Setup.exe (echo Installer build failed.& exit /b 1)

echo.
echo BUILD SUCCESSFUL
 echo Client:  dist\FinduptoVPN.exe
 echo Installer: installer\dist\Findupto-Free-VPN-Setup.exe
endlocal
