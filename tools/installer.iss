#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef ReleaseDir
  #error ReleaseDir is required
#endif
#ifndef Bootstrapper
  #error Bootstrapper is required
#endif
#ifndef ProductName
  #define ProductName "EchoCue"
#endif
#ifndef ProductId
  #define ProductId "5F021B01-4F3C-47A3-BBC8-A0C922C52E45"
#endif
#ifndef PackageName
  #define PackageName "EchoCue"
#endif
#ifndef OutputFolder
  #define OutputFolder "..\dist"
#endif

[Setup]
AppId={#ProductId}
AppName={#ProductName}
AppVersion={#AppVersion}
AppPublisher=EchoCue
AppVerName={#ProductName} {#AppVersion}
DefaultDirName={localappdata}\Programs\{#ProductName}
DefaultGroupName={#ProductName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
SetupIconFile=..\app\assets\echocue.ico
UninstallDisplayIcon={app}\EchoCue.exe
UninstallDisplayName={#ProductName}
OutputDir={#OutputFolder}
OutputBaseFilename={#PackageName}-{#AppVersion}-Setup-x64
Compression=lzma2/fast
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
VersionInfoVersion={#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#ReleaseDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "installed.flag"; DestDir: "{app}\_internal"; Flags: ignoreversion
Source: "{#Bootstrapper}"; DestDir: "{tmp}"; Flags: dontcopy

[Icons]
Name: "{group}\{#ProductName}"; Filename: "{app}\EchoCue.exe"; WorkingDir: "{app}"; AppUserModelID: "{#PackageName}.Desktop"
Name: "{autodesktop}\{#ProductName}"; Filename: "{app}\EchoCue.exe"; WorkingDir: "{app}"; Tasks: desktopicon; AppUserModelID: "{#PackageName}.Desktop"
Name: "{group}\Uninstall EchoCue"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\EchoCue.exe"; Description: "{cm:LaunchProgram,{#ProductName}}"; Flags: nowait postinstall skipifsilent

[Code]
function HasWebView2At(RootKey: Integer): Boolean;
var
  Keys: TArrayOfString;
  I: Integer;
  Name, Version, Key: String;
begin
  Result := False;
  if RegGetSubkeyNames(RootKey, 'Software\Microsoft\EdgeUpdate\Clients', Keys) then
    for I := 0 to GetArrayLength(Keys) - 1 do begin
      Key := 'Software\Microsoft\EdgeUpdate\Clients\' + Keys[I];
      if RegQueryStringValue(RootKey, Key, 'name', Name) and
         RegQueryStringValue(RootKey, Key, 'pv', Version) then
        if (Pos('WebView2', Name) > 0) and (Version <> '') and (Version <> '0.0.0.0') then begin
          Result := True;
          Exit;
        end;
    end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExitCode: Integer;
begin
  Result := '';
  if HasWebView2At(HKCU32) or HasWebView2At(HKLM32) then Exit;
  ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
  if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install',
      '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
    Result := 'Unable to start Microsoft Edge WebView2 setup. Please install the WebView2 Runtime and retry.'
  else if (ExitCode <> 0) and (ExitCode <> 3010) then
    Result := 'Microsoft Edge WebView2 setup failed. Check your connection, install the WebView2 Runtime, and retry.';
end;
