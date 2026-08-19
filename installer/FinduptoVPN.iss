#define MyAppName "Findupto Free VPN"
#define MyAppVersion "3.0.0"
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
DisableProgramGroupPage=yes

[Files]
Source: "..\dist\FinduptoVPN.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "openvpn-amd64.msi"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{autodesktop}\Findupto Free VPN"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Findupto Free VPN"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\openvpn-amd64.msi"" /qn /norestart"; StatusMsg: "Installing OpenVPN Community..."; Flags: waituntilterminated; Check: NeedOpenVPN
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Findupto Free VPN"; Flags: nowait postinstall skipifsilent; Check: RuntimeReady

[Code]
function OpenVPNPath(): String;
begin
  Result := ExpandConstant('{autopf}\OpenVPN\bin\openvpn.exe');
  if not FileExists(Result) then Result := ExpandConstant('{autopf32}\OpenVPN\bin\openvpn.exe');
end;

function NeedOpenVPN(): Boolean;
begin
  Result := not FileExists(OpenVPNPath());
end;

function RuntimeReady(): Boolean;
begin
  Result := FileExists(OpenVPNPath());
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  NeedsRestart := False;
  if not FileExists(ExpandConstant('{src}\..\dist\FinduptoVPN.exe')) then
    Result := 'FinduptoVPN.exe was not found. Build the client EXE first.'
  else if not FileExists(ExpandConstant('{src}\openvpn-amd64.msi')) then
    Result := 'OpenVPN MSI is missing. Run the Windows build first.';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpFinished then
  begin
    if not RuntimeReady() then
    begin
      MsgBox('OpenVPN could not be verified. Reboot Windows if a driver installation was pending, then run this installer again as Administrator.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;
