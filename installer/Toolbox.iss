#define AppVersion "0.4.0"
#ifndef Payload
  #define Payload "..\release\v0.4.0"
#endif

[Setup]
AppId={{C1B10776-C1D5-4B13-BE8E-75D1D3ECA906}
AppName=Toolbox
AppVersion={#AppVersion}
AppPublisher=Toolbox
DefaultDirName={localappdata}\Programs\Toolbox
DefaultGroupName=Toolbox
UsePreviousGroup=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\release\v0.4.0
OutputBaseFilename=Toolbox-Setup-0.4.0-x64
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\Toolbox.exe
UninstallDisplayName=Toolbox
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ChangesAssociations=yes
VersionInfoVersion=0.4.0.0
VersionInfoDescription=Toolbox安装程序

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimp"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："
Name: "contextmenu"; Description: "添加图片 / PDF 右键菜单及“发送到”入口"; GroupDescription: "系统集成："
Name: "autostart"; Description: "登录 Windows 后在托盘中启动"; GroupDescription: "启动选项："; Flags: unchecked

[Files]
Source: "{#Payload}\Toolbox.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\使用说明.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\Toolbox-source.zip"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Toolbox"; Filename: "{app}\Toolbox.exe"
Name: "{group}\卸载Toolbox"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Toolbox"; Filename: "{app}\Toolbox.exe"; Tasks: desktopicon
Name: "{usersendto}\Toolbox"; Filename: "{app}\Toolbox.exe"; Tasks: contextmenu

[InstallDelete]
Type: files; Name: "{app}\ShiguangToolbox.exe"
Type: files; Name: "{app}\ShiguangToolbox-source.zip"
Type: files; Name: "{userdesktop}\拾光工具箱.lnk"
Type: files; Name: "{userprograms}\拾光工具箱\拾光工具箱.lnk"
Type: files; Name: "{userprograms}\拾光工具箱\卸载拾光工具箱.lnk"
Type: files; Name: "{usersendto}\拾光工具箱.lnk"
Type: dirifempty; Name: "{userprograms}\拾光工具箱"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Toolbox"; ValueData: """{app}\Toolbox.exe"" --background"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Toolbox.exe"; Parameters: "--register-menu"; Check: ShouldRegisterMenu; Flags: runhidden waituntilterminated
Filename: "{app}\Toolbox.exe"; Description: "启动Toolbox"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\Toolbox.exe"; Parameters: "--quit"; Flags: runhidden waituntilterminated; RunOnceId: "QuitToolbox"
Filename: "{app}\Toolbox.exe"; Parameters: "--unregister-menu"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveShellMenu"

[Code]
function ShouldRegisterMenu(): Boolean;
begin
  Result := WizardIsTaskSelected('contextmenu') or RegKeyExists(HKEY_CURRENT_USER, 'Software\Classes\*\shell\ShiguangToolbox');
end;
procedure InitializeWizard();
var PreviousStartup: String;
begin
  if RegQueryStringValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'ShiguangToolbox', PreviousStartup) then
    WizardSelectTasks('autostart');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'ShiguangToolbox');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Toolbox');
end;
