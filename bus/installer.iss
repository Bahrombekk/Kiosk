; ============================================================================
;  installer.iss — Avtobus o'rnatuvchisi (Inno Setup 6)
;
;  OLDIN: build.ps1 ni ishga tushiring (release\Avtobus\ tayyor bo'lsin).
;  Kompilyatsiya (parol standart "Kiosk2026"):
;      & "C:\Users\<user>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss
;  Natija: Output\AvtobusSetup.exe  (shifrlangan, parol bilan)
;
;  O'rnatgich:
;    - release\Avtobus\ ni  C:\Avtobus  ga ko'chiradi (exe manba .py TUSHMAYDI)
;    - bulut (super-admin) manzili / avtobus nomi so'raydi
;    - so'ng ORNAT.PS1 (-InPlace) ni chaqiradi — u Task Scheduler bilan:
;        * boot'da avto-start (login SHART EMAS)
;        * qulasa/o'chsa avto-restart + watchdog (osilsa qayta yoqadi)
;        * firewall 80, cloud.txt
;    - yangilashda data.db / content SAQLANADI
;
;  Litsenziya: qurilma bulutga ulanadi -> super-admin panelида TASDIQLAGACH
;  bulut litsenziyани avtomatik imzolab yuboradi (qo'lда fayl KERAK EMAS).
; ============================================================================

#define AppName "Avtobus"
#define AppVer "1.0.0"
#define AppExe "Avtobus.exe"

; Parol: standart "Kiosk2026". Build oldidan $env:AVTOBUS_SETUP_PASS bilan
; boshqa parol berish mumkin (u holda o'sha ustun turadi).
#define InstallPassword GetEnv("AVTOBUS_SETUP_PASS")
#if InstallPassword == ""
  #define InstallPassword "Kiosk2026"
#endif

[Setup]
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=Avtobus.uz
DefaultDirName=C:\Avtobus
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=no
Password={#InstallPassword}
Encryption=yes
OutputDir=Output
OutputBaseFilename=AvtobusSetup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequired=admin
UninstallDisplayName={#AppName}

[Languages]
Name: "uz"; MessagesFile: "compiler:Default.isl"

[Dirs]
Name: "{app}\content"
Name: "{app}\content\media"
Name: "{app}\content\covers"
Name: "{app}\content\books"
Name: "{app}\content\ads"
Name: "{app}\content\branding"
Name: "{app}\logs"

[Files]
; build.ps1 tayyorlagan release: Avtobus.exe + _internal + node.exe + ffmpeg.exe
; + web\.output + ornat.ps1 + watchdog.ps1 + holat.bat
Source: "release\Avtobus\*"; DestDir: "{app}"; \
    Flags: recursesubdirs createallsubdirs ignoreversion

; Eski PyInstaller _internal / web build'ini tozalaymiz (yangi bilan aralashmasin).
; data.db / content / license.key / cloud.txt TEGILMAYDI — ma'lumot saqlanadi.
[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\web\.output"

[Icons]
Name: "{group}\Avtobus holat (HW ID va litsenziya)"; Filename: "{app}\holat.bat"
Name: "{commondesktop}\Avtobus holat"; Filename: "{app}\holat.bat"

[Run]
; O'rnatishning oxirida ornat.ps1 (-InPlace) — Task Scheduler xizmati, firewall,
; cloud.txt. Sehrgardagi qiymatlar {code:PsArgs} orqali uzatiladi.
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\ornat.ps1"" {code:PsArgs}"; \
    StatusMsg: "Xizmat sozlanmoqda (boot autostart + watchdog)..."; \
    Flags: runhidden waituntilterminated

[UninstallDelete]
Type: files; Name: "{app}\data.db-wal"
Type: files; Name: "{app}\data.db-shm"
Type: dirifempty; Name: "{app}"

[Code]
var
  CfgPage: TInputQueryWizardPage;

{ Sehrgar sahifasi: bulut (super-admin) manzili + avtobus nomi + ulash kaliti }
procedure InitializeWizard;
begin
  CfgPage := CreateInputQueryPage(wpSelectDir,
    'Avtobus sozlamalari',
    'Markaziy bulut (super-admin) va shu avtobus nomi',
    'Keyin {app}\cloud.txt dan yoki panelдан o''zgartirilishi mumkin.');
  CfgPage.Add('Bulut (super-admin) domeni, masalan cloud.poyezd.uz:', False);
  CfgPage.Add('Avtobus nomi (panelда ko''rinadi):', False);
  CfgPage.Add('Ulash kaliti (ixtiyoriy — darhol tasdiq uchun):', False);
  CfgPage.Values[0] := 'cloud.poyezd.uz';
  CfgPage.Values[1] := 'Avtobus-01';
  CfgPage.Values[2] := '';
end;

{ ornat.ps1 uchun argument satri (sehrgar qiymatlaridan) }
function PsArgs(Param: String): String;
var a: String;
begin
  a := '-InPlace';
  if Trim(CfgPage.Values[0]) <> '' then a := a + ' -CloudUrl "' + Trim(CfgPage.Values[0]) + '"';
  if Trim(CfgPage.Values[1]) <> '' then a := a + ' -Name "' + Trim(CfgPage.Values[1]) + '"';
  if Trim(CfgPage.Values[2]) <> '' then a := a + ' -Enroll "' + Trim(CfgPage.Values[2]) + '"';
  Result := a;
end;

{ Yangilash: ishlab turган jarayonni to'xtatamiz (fayllar qulflanmasin) }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var rc: Integer;
begin
  Exec(ExpandConstant('{sys}\schtasks.exe'), '/End /TN "Avtobus"', '', SW_HIDE, ewWaitUntilTerminated, rc);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM Avtobus.exe /F', '', SW_HIDE, ewWaitUntilTerminated, rc);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM node.exe /F', '', SW_HIDE, ewWaitUntilTerminated, rc);
  Sleep(1200);
  Result := '';
end;

{ Deinstalyatsiya: vazifalar, jarayonlar, firewall'ni tozalaymiz }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var rc: Integer;
begin
  if CurUninstallStep <> usUninstall then exit;
  Exec(ExpandConstant('{sys}\schtasks.exe'), '/Delete /TN "Avtobus" /F', '', SW_HIDE, ewWaitUntilTerminated, rc);
  Exec(ExpandConstant('{sys}\schtasks.exe'), '/Delete /TN "AvtobusWatchdog" /F', '', SW_HIDE, ewWaitUntilTerminated, rc);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM Avtobus.exe /F', '', SW_HIDE, ewWaitUntilTerminated, rc);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM node.exe /F', '', SW_HIDE, ewWaitUntilTerminated, rc);
  Exec(ExpandConstant('{sys}\netsh.exe'), 'advfirewall firewall delete rule name="Avtobus-Web80"', '', SW_HIDE, ewWaitUntilTerminated, rc);
end;
