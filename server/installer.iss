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
; Windows Firewall: kiosklar serverga ulana olishi uchun KIRISH ruxsati
; (TCP 8765 API/WS + UDP 8766 discovery). Aks holda kiosklar "ulanib bo'lmadi".
Filename: "{sys}\netsh.exe"; \
    Parameters: "advfirewall firewall add rule name=""KioskServer"" dir=in action=allow program=""{app}\{#AppExe}"" enable=yes profile=any"; \
    Flags: runhidden
Filename: "{sys}\netsh.exe"; \
    Parameters: "advfirewall firewall add rule name=""KioskServer-8765"" dir=in action=allow protocol=TCP localport=8765 enable=yes profile=any"; \
    Flags: runhidden
; UDP 8766: imzolangan discovery beacon (kiosklar serverni avto-topadi)
Filename: "{sys}\netsh.exe"; \
    Parameters: "advfirewall firewall add rule name=""KioskServer-8766"" dir=in action=allow protocol=UDP localport=8766 enable=yes profile=any"; \
    Flags: runhidden
; TCP 80: veb kiosk (poyezd.uz) — kiosklar/telefonlar brauzerdan ochadi
Filename: "{sys}\netsh.exe"; \
    Parameters: "advfirewall firewall add rule name=""KioskServer-Web80"" dir=in action=allow protocol=TCP localport=80 enable=yes profile=any"; \
    Flags: runhidden
Filename: "{app}\{#AppExe}"; Description: "Kiosk Serverni hozir ishga tushirish"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM {#AppExe} /F"; Flags: runhidden; RunOnceId: "StopKioskServer"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""KioskServer"""; Flags: runhidden; RunOnceId: "DelFwKioskServer"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""KioskServer-8765"""; Flags: runhidden; RunOnceId: "DelFwKioskServer8765"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""KioskServer-8766"""; Flags: runhidden; RunOnceId: "DelFwKioskServer8766"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""KioskServer-Web80"""; Flags: runhidden; RunOnceId: "DelFwKioskServerWeb80"

[UninstallDelete]
Type: files; Name: "{app}\data.db-wal"
Type: files; Name: "{app}\data.db-shm"
Type: files; Name: "{app}\logs\server.log"
Type: files; Name: "{app}\logs\server.log.1"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: dirifempty; Name: "{app}"
