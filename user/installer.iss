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
#define WatchdogExe "KioskWatchdog.exe"

; O'rnatish paroli muhit o'zgaruvchisidan olinadi (git'da saqlanmasin):
;   PowerShell:  $env:KIOSK_SETUP_PASS = "yangi-parol"; ISCC.exe installer.iss
; Berilmasa eski parol ishlatiladi (ogohlantirish bilan).
#define InstallPassword GetEnv("KIOSK_SETUP_PASS")
#if InstallPassword == ""
  #pragma warning "KIOSK_SETUP_PASS berilmagan — standart parol ishlatilyapti!"
  #define InstallPassword "kiosk2026"
#endif

[Setup]
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=O'zbekiston Temir Yo'llari
DefaultDirName=C:\Kiosk
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=no
; O'rnatish uchun parol (foydalanuvchi installer ochilganda kiritadi).
; Encryption=yes — fayllar parol bilan haqiqatan shifrlanadi (parolsiz
; installer ichidan fayllarni ajratib olib bo'lmaydi).
Password={#InstallPassword}
Encryption=yes
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

[Tasks]
; Kiosk qulflash siyosatlari (Task Manager, Win tugmalari, ekran qulfi o'chadi).
; Texnik kompyuterga o'rnatishda belgini olib tashlash mumkin.
Name: "lockdown"; Description: "Kiosk qulflash siyosatlarini yoqish (Task Manager, Win tugmalari, ekran qulfini o'chirish)"

[Files]
; Butun PyInstaller build'i (release\Kiosk\* -> {app})
Source: "release\Kiosk\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; Texnik xizmat uchun qulflashni yoqish/o'chirish reg fayllari
Source: "lockdown_on.reg"; DestDir: "{app}"; Flags: ignoreversion
Source: "lockdown_off.reg"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\_internal\assets\design\app.ico"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\_internal\assets\design\app.ico"

[Registry]
; Autostart — Windows ishga tushganda WATCHDOG ochiladi (u Kiosk.exe'ni
; ishga tushiradi va qulasa avtomatik qayta ko'taradi)
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "Kiosk"; ValueData: """{app}\{#WatchdogExe}"""; \
    Flags: uninsdeletevalue

; --- Kiosk qulflash siyosatlari (lockdown vazifasi belgilangan bo'lsa) ---
; Ctrl+Alt+Del ni dasturdan bloklab bo'lmaydi (Windows himoyalangan
; ketma-ketligi) — buning o'rniga u ochadigan xavfli yo'llarni o'chiramiz:
; Task Manager, ekran qulfi (Win+L), tez foydalanuvchi almashish.
; Win tugmalari kombinatsiyalari (Win+R, Win+E...) ham o'chadi.
; O'chirishda (uninstall) qiymatlar avtomatik olib tashlanadi.
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"; \
    ValueType: dword; ValueName: "DisableTaskMgr"; ValueData: 1; \
    Flags: uninsdeletevalue; Tasks: lockdown
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"; \
    ValueType: dword; ValueName: "DisableLockWorkstation"; ValueData: 1; \
    Flags: uninsdeletevalue; Tasks: lockdown
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"; \
    ValueType: dword; ValueName: "HideFastUserSwitching"; ValueData: 1; \
    Flags: uninsdeletevalue; Tasks: lockdown
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer"; \
    ValueType: dword; ValueName: "NoWinKeys"; ValueData: 1; \
    Flags: uninsdeletevalue; Tasks: lockdown

[Run]
; 1) VLC plagin keshini o'rnatilgan yo'lga moslab generatsiya qilamiz
;    (video startupida 'stale cache' xatosi bo'lmasin, tez ochilsin)
Filename: "{app}\_internal\vlc\vlc-cache-gen.exe"; \
    Parameters: """{app}\_internal\vlc\plugins"""; \
    StatusMsg: "Video kutubxonasi sozlanmoqda..."; Flags: runhidden waituntilterminated
; 2) O'rnatish tugagach kioskni darhol ishga tushirish (watchdog orqali —
;    qulasa avtomatik qayta ko'tariladi)
Filename: "{app}\{#WatchdogExe}"; Description: "Kioskni hozir ishga tushirish"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Runtime'da yozilgan fayllar (uninstaller ularni avtomatik kuzatmaydi)
Type: files; Name: "{app}\server.txt"
Type: files; Name: "{app}\trust.json"
Type: files; Name: "{app}\server_cert.crt"
Type: files; Name: "{app}\crash.log"
Type: files; Name: "{app}\crash.log.1"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\cache"
Type: filesandordirs; Name: "{app}\_internal\vlc\plugins\plugins.dat"
Type: dirifempty; Name: "{app}"

[UninstallRun]
; O'chirishdan oldin AVVAL watchdog'ni to'xtatamiz (aks holda u kioskni
; qayta ishga tushirib yuboradi), keyin kioskning o'zini
Filename: "{cmd}"; Parameters: "/C taskkill /IM {#WatchdogExe} /F"; Flags: runhidden; RunOnceId: "StopWatchdog"
Filename: "{cmd}"; Parameters: "/C taskkill /IM {#AppExe} /F"; Flags: runhidden; RunOnceId: "StopKiosk"

; ----------------------------------------------------------------------------
;  Xavfsiz ulanish: trust.json (tavsiya) yoki qo'lda URL+kalit (eski usul)
;
;  trust.json — server admin oynasidan eksport qilinadi. Tanlansa:
;    * {app}\trust.json ga nusxalanadi (kiosk serverni IMZO bilan topadi),
;    * ichidagi TLS sertifikat Windows "Trusted Root"ga qo'shiladi
;      (HTTPS/WSS va VLC striming self-signed sertifikatga ishonadi).
;  Berilmasa — eski usul: server.txt ga URL+kalit yoziladi (HTTP).
; ----------------------------------------------------------------------------
[Code]
var
  TrustPage: TInputFileWizardPage;
  ServerPage: TInputQueryWizardPage;

procedure InitializeWizard();
begin
  TrustPage := CreateInputFilePage(wpSelectDir,
    'Kiosk ishonch fayli (tavsiya etiladi)',
    'Server bilan xavfsiz, shifrlangan ulanish uchun trust.json',
    'Server admin oynasi -> Boshqaruv -> "Kiosk ishonch faylini eksport" ' +
    'tugmasi bilan olingan trust.json faylini tanlang.' + #13#10 + #13#10 +
    'Bu fayl bo''lsa server IP va kalitni qo''lda yozish SHART EMAS: kiosk ' +
    'serverni imzolangan signal orqali topadi va ulanishni sertifikatga ' +
    'pin qiladi (eng xavfsiz). Faylingiz bo''lmasa — keyingi sahifada IP ' +
    'kiriting.');
  TrustPage.Add('Ishonch fayli:', 'JSON fayllar|*.json|Barcha fayllar|*.*', '.json');

  ServerPage := CreateInputQueryPage(TrustPage.ID,
    'Server manzili (ixtiyoriy)',
    'trust.json tanlamagan bo''lsangiz to''ldiring',
    'Yuqorida trust.json tanlagan bo''lsangiz, bu sahifani BO''SH qoldiring.' +
    #13#10 + #13#10 +
    'Aks holda server IP/port va API kalitni kiriting (eski usul, HTTP).' +
    #13#10 + 'Masalan: http://192.168.136.69:8765');
  ServerPage.Add('Server manzili (URL):', False);
  ServerPage.Add('API kalit:', False);
end;

function NormalizeUrl(S: string): string;
begin
  S := Trim(S);
  if (Pos('http://', S) <> 1) and (Pos('https://', S) <> 1) then
    S := 'http://' + S;
  Result := S;
end;

// trust.json YOKI (URL+kalit) bo'lishi shart — ikkalasi ham bo'sh bo'lmasin
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = ServerPage.ID then
  begin
    if (Trim(TrustPage.Values[0]) = '') and (Trim(ServerPage.Values[0]) = '') then
    begin
      MsgBox('Avvalgi sahifada trust.json tanlang YOKI bu yerda server ' +
             'manzilini kiriting.', mbError, MB_OK);
      Result := False;
    end
    else if (Trim(TrustPage.Values[0]) = '') and (Trim(ServerPage.Values[1]) = '') then
    begin
      MsgBox('API kalitni kiriting (yoki trust.json tanlang).', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

// O'rnatish tugagach: trust.json nusxalash + sertifikatni Root'ga qo'shish,
// va/yoki server.txt yozish.
procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDir, TrustSrc, CertPath, PS: string;
  RC: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    AppDir := ExpandConstant('{app}');
    TrustSrc := Trim(TrustPage.Values[0]);

    if TrustSrc <> '' then
    begin
      // 1) trust.json -> {app}\trust.json
      FileCopy(TrustSrc, AppDir + '\trust.json', False);
      // 2) Sertifikatni ajratib (PowerShell JSON o'qiydi) Trusted Root'ga
      //    qo'shamiz — VLC striming ham, requests/ws ham ishonsin.
      CertPath := AppDir + '\server_cert.crt';
      PS := '$ErrorActionPreference=''Stop'';' +
            '$j=Get-Content -Raw -LiteralPath ''' + AppDir + '\trust.json'' | ConvertFrom-Json;' +
            'if($j.cert_pem){[IO.File]::WriteAllText(''' + CertPath + ''',$j.cert_pem);' +
            'certutil -addstore -f Root ''' + CertPath + '''}';
      if (not Exec('powershell.exe',
            '-NoProfile -ExecutionPolicy Bypass -Command "' + PS + '"',
            '', SW_HIDE, ewWaitUntilTerminated, RC)) or (RC <> 0) then
        MsgBox('Diqqat: server sertifikatini Trusted Root''ga qo''shib ' +
               'bo''lmadi. Kiosk ishlaydi, lekin video striming self-signed ' +
               'sertifikatda muammo berishi mumkin (lokal kesh baribir ' +
               'ishlaydi).', mbInformation, MB_OK);
    end;

    // URL kiritilgan bo'lsa server.txt (override / eski HTTP usul). trust.json
    // berilgan bo'lsa va URL bo'sh bo'lsa — yozmaymiz (discovery topadi).
    if Trim(ServerPage.Values[0]) <> '' then
      SaveStringToFile(AppDir + '\server.txt',
        '# Kiosk server manzili. Tahrirlab qayta ishga tushiring (qayta o''rnatish shart emas).' + #13#10 +
        NormalizeUrl(ServerPage.Values[0]) + #13#10 +
        'key=' + Trim(ServerPage.Values[1]) + #13#10, False);
  end;
end;
