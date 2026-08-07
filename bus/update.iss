; ============================================================================
;  update.iss — Avtobus KOD-ONLY yangilanish paketi (Inno Setup 6)
;
;  installer.iss dan farqi: node.exe/ffmpeg.exe KIRMAYDI (ular o'rnatishда bor,
;  kamdan-kam o'zgaradi) -> paket ~kichik. Parol/shifr YO'Q — yetkazish bulut
;  IMZOLANGAN buyrug'i + sha256 bilan himoyalangan. Sehrgar YO'Q — mavjud
;  cloud.txt (bulut manzili/nom) saqlanadi.
;
;  Qurilma buni JIMGINA ishga tushiradi:
;     AvtobusUpdate.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
;  -> xizmat to'xtaydi, kod almashadi (data.db/content/license SAQLANADI),
;     ornat.ps1 -InPlace xizmatni qayta yoqadi.
;
;  OLDIN: build.ps1 (release\Avtobus tayyor). Kompilyatsiya:
;     & "...\Inno Setup 6\ISCC.exe" update.iss   ->  Output\AvtobusUpdate.exe
; ============================================================================

#define AppName "Avtobus"
#define AppVer "1.0.0"

[Setup]
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=Avtobus.uz
DefaultDirName=C:\Avtobus
DisableProgramGroupPage=yes
DisableDirPage=yes
OutputDir=Output
OutputBaseFilename=AvtobusUpdate
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequired=admin
Uninstallable=no

[Languages]
Name: "uz"; MessagesFile: "compiler:Default.isl"

[Files]
; FAQAT kod: node.exe / ffmpeg.exe CHIQARIB tashlanadi (Excludes).
Source: "release\Avtobus\*"; DestDir: "{app}"; \
    Excludes: "node.exe,ffmpeg.exe,license.key,cloud.txt,data.db"; \
    Flags: recursesubdirs createallsubdirs ignoreversion

; Eski kod qoldiqlari yangisi bilan aralashmasin. Data TEGILMAYDI.
[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\web\.output"

[Run]
; Xizmatni qayta sozlab yoqamiz (mavjud cloud.txt saqlanadi — sehrgar yo'q).
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\ornat.ps1"" -InPlace"; \
    StatusMsg: "Yangilanish qo'llanmoqda..."; Flags: runhidden waituntilterminated

[Code]
{ Ishlab turган jarayonni to'xtatamiz (kod fayllari qulflanmasin) }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var rc: Integer;
begin
  Exec(ExpandConstant('{sys}\schtasks.exe'), '/End /TN "Avtobus"', '', SW_HIDE, ewWaitUntilTerminated, rc);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM Avtobus.exe /F', '', SW_HIDE, ewWaitUntilTerminated, rc);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM node.exe /F', '', SW_HIDE, ewWaitUntilTerminated, rc);
  Sleep(1500);
  Result := '';
end;
