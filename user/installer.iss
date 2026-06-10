; ============================================================================
;  installer.iss — Kiosk (foydalanuvchi ilovasi) o'rnatuvchisi (Inno Setup 6)
;
;  Imkoniyatlari:
;    - o'rnatishda PAROL so'raydi (kiosk2026)
;    - server IP manzilini kiritish sahifasi (server.txt ga yoziladi)
;    - C:\Kiosk ga o'rnatadi, VLC birga (qurilmada VLC kerak emas)
;    - Windows bilan birga avtomatik ishga tushadi (autostart)
;    - logotipli ikonka, Ish stoli + Start menyu yorliqlari
;
;  Kompilyatsiya:
;    "C:\Users\User\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss
;  Natija:  Output\KioskSetup.exe
;
;  Parolni o'zgartirish: pastdagi [Setup] Password= qatorini tahrirlab,
;  qaytadan kompilyatsiya qiling.
; ============================================================================

#define AppName "Kiosk"
#define AppVer "1.0.0"
#define AppExe "Kiosk.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=O'zbekiston Temir Yo'llari
DefaultDirName=C:\Kiosk
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=no
; O'rnatish uchun parol (foydalanuvchi installer ochilganda kiritadi)
Password=kiosk2026
OutputDir=Output
OutputBaseFilename=KioskSetup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
SetupIconFile=assets\design\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}

[Languages]
Name: "uz"; MessagesFile: "compiler:Default.isl"

[Files]
; Butun PyInstaller build'i (release\Kiosk\* -> {app})
Source: "release\Kiosk\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\_internal\assets\design\app.ico"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\_internal\assets\design\app.ico"

[Registry]
; Autostart — Windows ishga tushganda kiosk o'zi ochiladi (barcha foydalanuvchilar)
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "Kiosk"; ValueData: """{app}\{#AppExe}"""; \
    Flags: uninsdeletevalue

[Run]
; 1) VLC plagin keshini o'rnatilgan yo'lga moslab generatsiya qilamiz
;    (video startupida 'stale cache' xatosi bo'lmasin, tez ochilsin)
Filename: "{app}\_internal\vlc\vlc-cache-gen.exe"; \
    Parameters: """{app}\_internal\vlc\plugins"""; \
    StatusMsg: "Video kutubxonasi sozlanmoqda..."; Flags: runhidden waituntilterminated
; 2) O'rnatish tugagach kioskni darhol ishga tushirish (ixtiyoriy)
Filename: "{app}\{#AppExe}"; Description: "Kioskni hozir ishga tushirish"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Runtime'da yozilgan fayllar (uninstaller ularni avtomatik kuzatmaydi)
Type: files; Name: "{app}\server.txt"
Type: files; Name: "{app}\crash.log"
Type: filesandordirs; Name: "{app}\_internal\vlc\plugins\plugins.dat"
Type: dirifempty; Name: "{app}"

[UninstallRun]
; O'chirishdan oldin ishlab turgan kioskni to'xtatamiz
Filename: "{cmd}"; Parameters: "/C taskkill /IM {#AppExe} /F"; Flags: runhidden; RunOnceId: "StopKiosk"

; ----------------------------------------------------------------------------
;  Server IP kiritish sahifasi + server.txt yozish
; ----------------------------------------------------------------------------
[Code]
var
  ServerPage: TInputQueryWizardPage;

procedure InitializeWizard();
begin
  ServerPage := CreateInputQueryPage(wpSelectDir,
    'Server manzili',
    'Kiosk qaysi serverga ulanadi?',
    'Server kompyuterining IP manzili va portini kiriting.' + #13#10 +
    'Masalan: http://192.168.136.69:8765');
  ServerPage.Add('Server manzili (URL):', False);
  ServerPage.Values[0] := 'http://192.168.136.69:8765';
end;

function NormalizeUrl(S: string): string;
begin
  S := Trim(S);
  if (Pos('http://', S) <> 1) and (Pos('https://', S) <> 1) then
    S := 'http://' + S;
  Result := S;
end;

// Server manzilini bo'sh qoldirmaslik
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = ServerPage.ID then
  begin
    if Trim(ServerPage.Values[0]) = '' then
    begin
      MsgBox('Iltimos, server manzilini kiriting.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

// O'rnatish tugagach server.txt ni Kiosk.exe yoniga yozamiz
procedure CurStepChanged(CurStep: TSetupStep);
var
  Path: string;
begin
  if CurStep = ssPostInstall then
  begin
    Path := ExpandConstant('{app}\server.txt');
    SaveStringToFile(Path,
      '# Kiosk server manzili. Tahrirlab qayta ishga tushiring (qayta o''rnatish shart emas).' + #13#10 +
      NormalizeUrl(ServerPage.Values[0]) + #13#10, False);
  end;
end;
