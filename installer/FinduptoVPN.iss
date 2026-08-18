#define MyAppName "Findupto Free VPN"
#define MyAppVersion "0.3.0"
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

[Icons]
Name: "{autodesktop}\Findupto Free VPN"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Findupto Free VPN"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\wireguard-amd64.msi"" /qn /norestart"; StatusMsg: "Installing WireGuard networking driver..."; Flags: waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Findupto Free VPN"; Flags: nowait postinstall skipifsilent
