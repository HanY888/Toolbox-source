#define AppVersion "0.3.0"
#ifndef Payload
  #define Payload "..\release\v0.3.0"
#endif

[Setup]
AppId={{C1B10776-C1D5-4B13-BE8E-75D1D3ECA906}
AppName=拾光工具箱
AppVersion={#AppVersion}
AppPublisher=Shiguang Toolbox
DefaultDirName={localappdata}\Programs\ShiguangToolbox
DefaultGroupName=拾光工具箱
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\release\v0.3.0
OutputBaseFilename=ShiguangToolbox-Setup-0.3.0-x64
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\ShiguangToolbox.exe
UninstallDisplayName=拾光工具箱
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ChangesAssociations=yes
VersionInfoVersion=0.3.0.0
VersionInfoDescription=拾光工具箱安装程序

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimp"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："
Name: "contextmenu"; Description: "添加图片 / PDF 右键菜单及“发送到”入口"; GroupDescription: "系统集成："
Name: "autostart"; Description: "登录 Windows 后在托盘中启动"; GroupDescription: "启动选项："; Flags: unchecked

[Files]
Source: "{#Payload}\ShiguangToolbox.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\使用说明.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\ShiguangToolbox-source.zip"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\拾光工具箱"; Filename: "{app}\ShiguangToolbox.exe"
Name: "{group}\卸载拾光工具箱"; Filename: "{uninstallexe}"
Name: "{userdesktop}\拾光工具箱"; Filename: "{app}\ShiguangToolbox.exe"; Tasks: desktopicon
Name: "{usersendto}\拾光工具箱"; Filename: "{app}\ShiguangToolbox.exe"; Tasks: contextmenu

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "ShiguangToolbox"; ValueData: """{app}\ShiguangToolbox.exe"" --background"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\ShiguangToolbox.exe"; Parameters: "--register-menu"; Tasks: contextmenu; Flags: runhidden waituntilterminated
Filename: "{app}\ShiguangToolbox.exe"; Description: "启动拾光工具箱"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\ShiguangToolbox.exe"; Parameters: "--quit"; Flags: runhidden waituntilterminated; RunOnceId: "QuitToolbox"
Filename: "{app}\ShiguangToolbox.exe"; Parameters: "--unregister-menu"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveShellMenu"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'ShiguangToolbox');
end;
