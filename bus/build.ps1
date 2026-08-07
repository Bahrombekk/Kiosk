# ============================================================================
#  build.ps1 — Avtobus'ni Docker'siz, HIMOYALANGAN Windows dasturiga yig'adi.
#
#  Bosqichlar:
#    1) Web (Nuxt) build            -> bus\web\.output
#    2) Maxfiy modullar Nuitka .pyd -> mashina kodi (dekompilyatsiya bo'lmaydi)
#    3) PyInstaller                 -> Avtobus.exe (+ _internal), .py chiqmaydi
#    4) release\Avtobus\ yig'iladi  -> exe + node.exe + ffmpeg.exe + web + kontent
#
#  Keyin: installer.iss ni Inno Setup bilan kompilyatsiya qiling (3-bosqich)
#         -> Output\AvtobusSetup.exe
#
#  Ishlatish (PowerShell, dasturchi mashinasida — MIJOZDA EMAS):
#      .\build.ps1                 # to'liq (Nuitka bilan)
#      .\build.ps1 -NoHarden       # Nuitka'siz (tez, faqat PyInstaller)
#      .\build.ps1 -SkipWeb        # web .output tayyor bo'lsa qayta qurmaslik
#
#  Talablar (dasturchi mashinasida):
#    - Python 3.11 (py -3.11), `pip install pyinstaller nuitka`
#    - Node.js + npm (web build uchun)
#    - Visual Studio Build Tools (MSVC) — Nuitka C kompilyatori uchun
#    - bus\vendor\node.exe va bus\vendor\ffmpeg.exe (pastdagi izohga qarang)
# ============================================================================
param(
  [switch]$NoHarden,      # Nuitka bosqichini o'tkazib yuborish
  [switch]$SkipWeb,       # web\.output tayyor bo'lsa qayta build qilmaslik
  [string]$Python = ""    # aniq Python (masalan "py -3.11"); bo'sh = avto
)
# "Stop" EMAS: PyInstaller/nuitka/npm kabi native buyruqlar INFO/warn'ni
# stderr'ga yozadi; WinPS 5.1 "Stop"да buni halokatli NativeCommandError deb
# to'xtatadi. RunPy $LASTEXITCODE ni o'zi tekshiradi, muhim qadamlar Die bilan.
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

function Say($m){ Write-Host $m -ForegroundColor Cyan }
function Ok($m){  Write-Host $m -ForegroundColor Green }
function Warn($m){ Write-Host $m -ForegroundColor Yellow }
function Die($m){ Write-Host $m -ForegroundColor Red; exit 1 }

$Root    = $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Web     = Join-Path $Root "web"
$Vendor  = Join-Path $Root "vendor"
$Build   = Join-Path $Root "build"
$AppDir  = Join-Path $Build "app"        # backend'ning toza vaqtinchalik nusxasi
$Release = Join-Path $Root "release\Avtobus"

# Maxfiy modullar — Nuitka .pyd ga aylanadi (manbasi exe'ga TUSHMAYDI).
$Secret = @("licensing.py", "security.py", "cloud_client.py")

Say "════════════════════════════════════════════"
Say "   AVTOBUS — himoyalangan build"
Say "════════════════════════════════════════════"

# ── Python topish ────────────────────────────────────────────────────────
if (-not $Python) {
  if (Get-Command py -ErrorAction SilentlyContinue) { $Python = "py -3.11" }
  elseif (Get-Command python -ErrorAction SilentlyContinue) { $Python = "python" }
  else { Die "Python topilmadi. Python 3.11 o'rnating." }
}
# `py -3.11` ni tekshirish; bo'lmasa oddiy `py`/`python`
$pyExe = ($Python -split ' ')[0]
$pyArgs = @($Python -split ' ' | Select-Object -Skip 1)
try { & $pyExe @pyArgs --version | Out-Null } catch {
  Warn "«$Python» ishlamadi — python ga qaytamiz"; $Python="python"; $pyExe="python"; $pyArgs=@()
}
Ok "✓ Python: $Python"

function RunPy { param([Parameter(ValueFromRemainingArguments=$true)]$a)
  & $pyExe @pyArgs @a; if ($LASTEXITCODE -ne 0){ Die "Python buyrug'i xato: $a" } }

# ── Vendor binarlar (node.exe, ffmpeg.exe, nssm.exe) ─────────────────────
$NodeExe   = Join-Path $Vendor "node.exe"
$FfmpegExe = Join-Path $Vendor "ffmpeg.exe"
$NssmExe   = Join-Path $Vendor "nssm.exe"
# node.exe va ffmpeg.exe MAJBURIY (exe yoniga bundle). nssm.exe faqat Inno
# installer (NSSM xizmat) yo'li uchun — Task Scheduler bilan o'rnatilsa shart
# emas, shuning uchun yo'q bo'lsa faqat ogohlantiramiz.
$missing = @()
if (-not (Test-Path $NodeExe))   { $missing += "node.exe" }
if (-not (Test-Path $FfmpegExe)) { $missing += "ffmpeg.exe" }
if ($missing.Count -gt 0) {
  Warn "`nbus\vendor\ ичida yetishmaydi: $($missing -join ', ')"
  Warn "  • node.exe   — https://nodejs.org/dist/  (LTS, win-x64 zip ичidagi node.exe)"
  Warn "  • ffmpeg.exe — https://www.gyan.dev/ffmpeg/builds/ (essentials, bin\ffmpeg.exe)"
  Warn "  Papka: $Vendor"
  Die  "node.exe va ffmpeg.exe shart. Joylashtirib qayta ishga tushiring."
}
$HasNssm = Test-Path $NssmExe
if ($HasNssm) { Ok "✓ Vendor: node.exe, ffmpeg.exe, nssm.exe" }
else { Ok "✓ Vendor: node.exe, ffmpeg.exe"; Warn "  (nssm.exe yo'q — Inno installer o'rniga Task Scheduler bilan o'rnatiladi)" }

# ── 1) WEB BUILD ──────────────────────────────────────────────────────────
$WebOut = Join-Path $Web ".output\server\index.mjs"
if ($SkipWeb -and (Test-Path $WebOut)) {
  Ok "✓ Web build o'tkazib yuborildi (-SkipWeb, .output mavjud)"
} else {
  Say "`n[1/4] Web (Nuxt) build..."
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Die "npm topilmadi. Node.js o'rnating." }
  Push-Location $Web
  try {
    if (Test-Path "package-lock.json") { npm ci; if ($LASTEXITCODE -ne 0){ npm install } }
    else { npm install }
    if ($LASTEXITCODE -ne 0){ Die "npm install xato" }
    npm run build; if ($LASTEXITCODE -ne 0){ Die "npm run build xato" }
  } finally { Pop-Location }
  if (-not (Test-Path $WebOut)) { Die "Web build tugadi-yu, .output\server\index.mjs topilmadi." }
  Ok "✓ Web build tayyor"
}

# ── 2) BACKEND TOZA NUSXA + NUITKA ─────────────────────────────────────────
Say "`n[2/4] Backend nusxa + kod himoyasi..."
if (Test-Path $Build) { Remove-Item $Build -Recurse -Force }
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null

# Faqat kod: .py fayllar (data.db, content, .pem, license.key, __pycache__ EMAS)
Get-ChildItem $Backend -Filter *.py | Copy-Item -Destination $AppDir
Copy-Item (Join-Path $Backend "avtobus.spec") $AppDir
Copy-Item (Join-Path $Backend "requirements.txt") $AppDir -ErrorAction SilentlyContinue
# Ixtiyoriy ikonka (favicon -> app.ico bo'lmasa e'tiborsiz)
$FaviconIco = Join-Path $Web "public\favicon.ico"
if (Test-Path $FaviconIco) { Copy-Item $FaviconIco (Join-Path $AppDir "app.ico") }

if ($NoHarden) {
  Warn "  ⚠ Nuitka o'tkazib yuborildi (-NoHarden). Maxfiy modullar .pyc holida"
  Warn "    qoladi (manba emas, lekin ilg'or hujumchi dekompilyatsiya urinishi mumkin)."
} else {
  $hasNuitka = $true
  try { RunPy -c "import nuitka" 2>$null } catch { $hasNuitka = $false }
  if (-not $hasNuitka) {
    Warn "  ⚠ Nuitka o'rnatilmagan (pip install nuitka). Bu bosqich o'tkazib"
    Warn "    yuboriladi — build davom etadi (faqat PyInstaller himoyasi)."
  } else {
    Push-Location $AppDir
    try {
      # 1) Avval HAMMASINI kompilyatsiya qilamiz (manba .py lar hali joyida —
      #    bog'liq modullar Nuitka tahliliga ko'rinib tursin).
      $compiled = @()
      foreach ($src in $Secret) {
        if (-not (Test-Path $src)) { continue }
        $mod = [IO.Path]::GetFileNameWithoutExtension($src)
        Say "    • Nuitka: $mod -> $mod.pyd (mashina kodi)"
        # --module: bitta modulni .pyd ga kompilyatsiya. --remove-output: temp tozalash.
        RunPy -m nuitka --module $src --output-dir="." --remove-output --assume-yes-for-downloads
        $pyd = Get-ChildItem -Filter "$mod*.pyd" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($pyd) { $compiled += $src; Ok "      ✓ $($pyd.Name)" }
        else { Warn "      ⚠ $mod.pyd yaratilmadi — .py holida qoladi (himoyasiz)." }
      }
      # 2) Endi kompilyatsiya BO'LGAN modullarning manba .py va .pyi sini
      #    o'chiramiz — exe'ga faqat .pyd tushsin (manba/pyc CHIQMAYDI).
      foreach ($src in $compiled) {
        $mod = [IO.Path]::GetFileNameWithoutExtension($src)
        Remove-Item $src -Force
        Remove-Item "$mod.pyi" -Force -ErrorAction SilentlyContinue
        Ok "      ✓ manba $src o'chirildi"
      }
    } finally { Pop-Location }
  }
}

# ── 3) PYINSTALLER ─────────────────────────────────────────────────────────
Say "`n[3/4] PyInstaller -> Avtobus.exe..."
try { RunPy -m PyInstaller --version | Out-Null } catch { Die "PyInstaller yo'q: pip install pyinstaller" }
Push-Location $AppDir
try {
  RunPy -m PyInstaller avtobus.spec --noconfirm --clean `
      --distpath (Join-Path $Build "dist") --workpath (Join-Path $Build "work")
} finally { Pop-Location }
$DistApp = Join-Path $Build "dist\Avtobus"
if (-not (Test-Path (Join-Path $DistApp "Avtobus.exe"))) { Die "Avtobus.exe yaratilmadi." }
Ok "✓ Avtobus.exe tayyor"

# ── 4) RELEASE YIG'ISH ─────────────────────────────────────────────────────
Say "`n[4/4] release\Avtobus\ yig'ilmoqda..."
if (Test-Path (Split-Path $Release)) { Remove-Item (Split-Path $Release) -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Release | Out-Null
Copy-Item "$DistApp\*" $Release -Recurse -Force            # exe + _internal
Copy-Item $NodeExe   (Join-Path $Release "node.exe")   -Force
Copy-Item $FfmpegExe (Join-Path $Release "ffmpeg.exe") -Force
if ($HasNssm) { Copy-Item $NssmExe (Join-Path $Release "nssm.exe") -Force }
Copy-Item (Join-Path $Root "watchdog.ps1") (Join-Path $Release "watchdog.ps1") -Force
Copy-Item (Join-Path $Root "holat.bat")    (Join-Path $Release "holat.bat")    -Force
if (Test-Path (Join-Path $Root "ornat.ps1")) {
  Copy-Item (Join-Path $Root "ornat.ps1") (Join-Path $Release "ornat.ps1") -Force
}
# Web build (exe YONIGA — kod web\.output ni sys.executable yonidan qidiradi)
New-Item -ItemType Directory -Force -Path (Join-Path $Release "web") | Out-Null
Copy-Item (Join-Path $Web ".output") (Join-Path $Release "web\.output") -Recurse -Force
# Bo'sh kontent papkalari (birinchi ishga tushishда to'ldiriladi / bulutdan)
foreach ($d in @("content","content\media","content\covers","content\books","content\ads","content\branding","logs")) {
  New-Item -ItemType Directory -Force -Path (Join-Path $Release $d) | Out-Null
}
# Litsenziya (bo'lsa) — HW-lock; mijoz uchun alohida license_tool bilan yaratiladi
$Lic = Join-Path $Backend "license.key"
if (Test-Path $Lic) { Copy-Item $Lic (Join-Path $Release "license.key") -Force; Ok "  ✓ license.key qo'shildi" }
else { Warn "  ⚠ license.key yo'q — frozen exe litsenziyasiz BLOKLANADI. license_tool bilan yarating." }

$sz = "{0:N0}" -f ((Get-ChildItem $Release -Recurse | Measure-Object Length -Sum).Sum / 1MB)
Ok "`n════════════════════════════════════════════"
Ok " ✓ TAYYOR — release\Avtobus\  (~$sz MB)"
Ok "════════════════════════════════════════════"
Write-Host "  Keyingi qadam (3-bosqich): installer yasash —"
Write-Host '    $env:AVTOBUS_SETUP_PASS="<parol>"'
Write-Host '    & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss'
Write-Host "  Natija: Output\AvtobusSetup.exe"
