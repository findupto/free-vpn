#define MyAppName "Findupto Free VPN"
#define MyAppVersion "0.5.0"
#define MyAppPublisher "Findupto"
#define MyAppExeName "FinduptoVPN.exe"

[Setup]
AppId={{9C3D0A2B-1A22-4D3A-8B5B-7B1F4D9E12A0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Findupto Free VPN
DefaultGroupName={#MyAppName}
OutputDir=dist
OutputBaseFilename=Findupto-Free-VPN-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\dist\FinduptoVPN.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "wireguard-amd64.msi"; DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "openvpn-amd64.msi"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{autodesktop}\Findupto Free VPN"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Findupto Free VPN"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\wireguard-amd64.msi"" /qn /norestart"; StatusMsg: "Installing WireGuard networking driver..."; Flags: waituntilterminated
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\openvpn-amd64.msi"" /qn /norestart"; StatusMsg: "Installing OpenVPN Community..."; Flags: waituntilterminated
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""$ovpn=@('{autopf}\OpenVPN\bin\openvpn.exe','{autopf32}\OpenVPN\bin\openvpn.exe'); if(-not ($ovpn | Where-Object { Test-Path $_ })){ [System.Windows.Forms.MessageBox]::Show('OpenVPN Community installation could not be verified. Please run the installer again as Administrator.','Findupto Free VPN','OK','Error'); exit 1 }"""; StatusMsg: "Verifying OpenVPN Community installation..."; Flags: waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Findupto Free VPN"; Flags: nowait postinstall skipifsilent; Check: RuntimeReady

[Code]
function RuntimeReady(): Boolean;
begin
  Result := FileExists(ExpandConstant('{autopf}\OpenVPN\bin\openvpn.exe')) or
            FileExists(ExpandConstant('{autopf32}\OpenVPN\bin\openvpn.exe'));
end;
