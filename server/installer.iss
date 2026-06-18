; ============================================================================
;  installer.iss - Kiosk Server/Admin o'rnatuvchisi (Inno Setup 6)
;
;  Kompilyatsiya:
;    "C:\Users\User\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss
;  Natija: Output\KioskServerSetup.exe
; ============================================================================

#define AppName "Kiosk Server"
#define AppVer "1.0.0"
#define AppExe "KioskServer.exe"

#define InstallPassword GetEnv("KIOSK_SERVER_SETUP_PASS")
#if InstallPassword == ""
  #error KIOSK_SERVER_SETUP_PASS berilmagan! Build oldidan o'rnating: $env:KIOSK_SERVER_SETUP_PASS="..."
#endif

[Setup]
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=O'zbekiston Temir Yo'llari
DefaultDirName=C:\KioskServer
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=no
Password={#InstallPassword}
Encryption=yes
OutputDir=Output
OutputBaseFilename=KioskServerSetup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
SetupIconFile=..\user\assets\design\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}

[Languages]
Name: "uz"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart"; Description: "Windows bilan birga server/admin oynasini ishga tushirish"

[Dirs]
Name: "{app}\content"
Name: "{app}\content\ads"
Name: "{app}\content\books"
Name: "{app}\content\covers"
Name: "{app}\content\media"
Name: "{app}\logs"

[Files]
Source: "release\KioskServer\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"

[Registry]
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "KioskServer"; ValueData: """{app}\{#AppExe}"""; \
    Flags: uninsdeletevalue; Tasks: autostart

[InstallDelete]
Type: files; Name: "{app}\data.db"
Type: files; Name: "{app}\data.db-wal"
Type: files; Name: "{app}\data.db-shm"
Type: filesandordirs; Name: "{app}\content\ads"
Type: filesandordirs; Name: "{app}\content\books"
Type: filesandordirs; Name: "{app}\content\covers"
Type: filesandordirs; Name: "{app}\content\media"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Kiosk Serverni hozir ishga tushirish"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM {#AppExe} /F"; Flags: runhidden; RunOnceId: "StopKioskServer"

[UninstallDelete]
Type: files; Name: "{app}\data.db-wal"
Type: files; Name: "{app}\data.db-shm"
Type: files; Name: "{app}\logs\server.log"
Type: files; Name: "{app}\logs\server.log.1"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: dirifempty; Name: "{app}"
