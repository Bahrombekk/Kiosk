# ─────────────────────────────────────────────────────────────
#  AVTOBUS — bir buyruqli o'rnatgich (Windows qurilma)
#  Ishlatish (PowerShell):   .\setup.ps1
#  Docker Desktop talab qilinadi.
# ─────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Say($m){ Write-Host $m -ForegroundColor Cyan }
function Ok($m){  Write-Host $m -ForegroundColor Green }
function Err($m){ Write-Host $m -ForegroundColor Red }

Say "════════════════════════════════════════════"
Say "   AVTOBUS.UZ — qurilma o'rnatgichi"
Say "════════════════════════════════════════════"

# 1) Docker tekshiruvi
try { docker version | Out-Null } catch { Err "Docker topilmadi. Docker Desktop o'rnating: https://www.docker.com/products/docker-desktop/"; exit 1 }
try { docker compose version | Out-Null } catch { Err "Docker Compose topilmadi. Docker Desktop'ni yangilang."; exit 1 }
Ok "✓ Docker mavjud"

# 2) Mavjud .env
$keepKey = ""
if (Test-Path .env) {
  Say "`n.env allaqachon mavjud."
  $ans = Read-Host "Qayta sozlaymizmi? (kalit saqlanadi) [h/Y]"
  if ($ans -match '^[hH]') {
    Ok "Mavjud .env saqlanadi. Faqat qayta ishga tushiramiz."
    docker compose up -d --build
    exit 0
  }
  $line = (Get-Content .env | Where-Object { $_ -match '^KIOSK_API_KEY=' } | Select-Object -First 1)
  if ($line) { $keepKey = $line.Substring($line.IndexOf('=') + 1) }
}

# 3) Savollar
Say "`nSozlamalar (Enter = standart qiymat):"
$cloud = Read-Host "  Bulut domeni  [cloud.poyezd.uz]"; if (-not $cloud) { $cloud = "cloud.poyezd.uz" }
$name  = Read-Host "  Avtobus nomi  [Avtobus-01]";      if (-not $name)  { $name  = "Avtobus-01" }
$enroll = Read-Host "  Ulash kaliti (ixtiyoriy, darhol tasdiq uchun)"

# 4) API kalit
if ($keepKey) { $key = $keepKey }
else {
  $bytes = New-Object 'System.Byte[]' 18
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $key = ([Convert]::ToBase64String($bytes)) -replace '[/+=]',''
  $key = $key.Substring(0, [Math]::Min(24, $key.Length))
}

# 5) .env yozish (UTF-8)
$lines = @(
  "# AVTOBUS.UZ — avto-yaratilgan ($(Get-Date -Format yyyy-MM-dd))",
  "KIOSK_API_KEY=$key",
  "KIOSK_NAME=$name",
  "KIOSK_CLOUD_URL=$cloud"
)
if ($enroll) { $lines += "KIOSK_CLOUD_ENROLL=$enroll" } else { $lines += "# KIOSK_CLOUD_ENROLL=" }
$lines += "# KIOSK_CLOUD_STATS=60"
Set-Content -Path .env -Value $lines -Encoding utf8
Ok "✓ .env yaratildi"

# 6) Ishga tushirish
Say "`nDocker image quriladi va ishga tushiriladi (birinchi marta bir necha daqiqa)..."
docker compose up -d --build

# 7) Manzil
$ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
       Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.*' } |
       Select-Object -First 1 -ExpandProperty IPAddress)
if (-not $ip) { $ip = "<qurilma-IP>" }
Ok "`n════════════════════════════════════════════"
Ok " ✓ TAYYOR — Avtobus ishga tushdi"
Ok "════════════════════════════════════════════"
Write-Host "  Yo'lovchilar:   http://$ip/"
Write-Host "  Bulut:          $cloud  (panelда `"$name`" ko'rinadi)"
if (-not $enroll) { Write-Host "  Keyingi qadam:  bulut panelida `"Tasdiqlash`" tugmasini bosing" }
Write-Host ""
Write-Host "  Boshqarish:"
Write-Host "    docker compose logs -f        # loglar"
Write-Host "    docker compose restart        # qayta ishga tushirish"
Write-Host "    docker compose down           # to'xtatish"
Write-Host "    git pull; docker compose up -d --build   # yangilash"
