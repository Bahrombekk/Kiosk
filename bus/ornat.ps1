# ============================================================================
#  ornat.ps1 — Avtobus'ni Inno/NSSM'siz o'rnatadi (Windows Task Scheduler).
#
#  Bu skript release\Avtobus\ ичida keladi. Admin PowerShell'да ishga tushiring:
#      .\ornat.ps1  -CloudUrl cloud.poyezd.uz  -Name "Avtobus-01"
#  Ixtiyoriy:  -Enroll <token>   -License C:\yo'l\license.key   -InPlace
#
#  Nima qiladi:
#   1) release'ni  C:\Avtobus  ga ko'chiradi (data.db/content/license SAQLANADI)
#   2) cloud.txt (bulut super-admin manzili + nom) yozadi
#   3) firewall'да 80-portni ochadi
#   4) litsenziyani o'rnatadi (berilган bo'lsa)
#   5) "Avtobus" rejalashtirilган vazifasi — BOOT'да ishga tushadi (login yo'q),
#      qulasa AVTO-RESTART; "AvtobusWatchdog" — osilса qayta yoqadi
# ============================================================================
param(
  [string]$CloudUrl = "",
  [string]$Name = "",
  [string]$Enroll = "",
  [string]$License = "",
  [switch]$InPlace          # C:\Avtobus'ning o'zidan ishga tushirilса ko'chirmaydi
)
# DIQQAT: "Stop" EMAS. schtasks/taskkill/netsh kabi native buyruqlar mavjud
# bo'lmagan vazifa/qoidada stderr'ga yozadi; WinPS 5.1 "Stop"да buni HALOKATLI
# xato deb to'xtatadi (o'rnatish yarim qoladi). "Continue" — best-effort; muhim
# cmdlet'lar (Register-ScheduledTask) alohida try/catch bilan tekshiriladi.
$ErrorActionPreference = "Continue"
function Say($m){ Write-Host $m -ForegroundColor Cyan }
function Ok($m){  Write-Host $m -ForegroundColor Green }
function Warn($m){ Write-Host $m -ForegroundColor Yellow }
function Die($m){ Write-Host $m -ForegroundColor Red; exit 1 }

# Admin tekshiruvi
$isAdmin = ([Security.Principal.WindowsPrincipal] `
  [Security.Principal.WindowsIdentity]::GetCurrent()
  ).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) { Die "Admin PowerShell kerak (o'ng tugma -> Run as administrator)." }

$Src = $PSScriptRoot
$Dst = "C:\Avtobus"
$Svc = "Avtobus"

Say "════════════════════════════════════════════"
Say "   AVTOBUS — o'rnatish (Task Scheduler)"
Say "════════════════════════════════════════════"

# ── Ishlab turган nusxani to'xtatamiz (fayllar qulflanmasin) ──
schtasks /End /TN $Svc 2>$null | Out-Null
taskkill /IM Avtobus.exe /F 2>$null | Out-Null
taskkill /IM node.exe /F 2>$null | Out-Null
Start-Sleep -Seconds 1

# ── 1) Ko'chirish (data.db / content / cloud.txt / license.key SAQLANADI) ──
if (-not $InPlace -and ($Src.TrimEnd('\') -ne $Dst)) {
  Say "`nFayllar $Dst ga ko'chirilmoqda..."
  New-Item -ItemType Directory -Force -Path $Dst | Out-Null
  # /E hamma narsa; ma'lumot fayllarini XF/XD bilan chetlab o'tamiz (mavjudi qoladi)
  robocopy $Src $Dst /E /NFL /NDL /NJH /NJS /NP `
    /XF data.db data.db-wal data.db-shm cloud.txt license.key `
    /XD (Join-Path $Dst "content") (Join-Path $Dst "logs") | Out-Null
  if ($LASTEXITCODE -ge 8) { Die "robocopy xato ($LASTEXITCODE)" }
  Ok "✓ Ko'chirildi"
} else { $Dst = $Src; Ok "✓ Joyида o'rnatish ($Dst)" }

# Bo'sh papkalar
foreach ($d in @("content","content\media","content\covers","content\books","content\ads","content\branding","logs")) {
  New-Item -ItemType Directory -Force -Path (Join-Path $Dst $d) | Out-Null
}

# ── 2) cloud.txt (bulut super-admin manzili + nom) ──
$cloudTxt = Join-Path $Dst "cloud.txt"
if ($CloudUrl -or $Name -or $Enroll -or -not (Test-Path $cloudTxt)) {
  $lines = @("# Avtobus bulut sozlamasi (ornat.ps1 yozdi)")
  if ($CloudUrl) { $lines += "url=$CloudUrl" }
  if ($Enroll)   { $lines += "enroll=$Enroll" }
  if ($Name)     { $lines += "name=$Name" }
  $lines | Out-File -FilePath $cloudTxt -Encoding utf8 -Force
  Ok "✓ cloud.txt yozildi"
}

# ── 3) Firewall (80-port — yo'lovchilar) ──
netsh advfirewall firewall delete rule name="Avtobus-Web80" 2>$null | Out-Null
netsh advfirewall firewall add rule name="Avtobus-Web80" dir=in action=allow protocol=TCP localport=80 enable=yes profile=any | Out-Null
Ok "✓ Firewall: 80-port ochildi"

# ── 4) Litsenziya (berilган bo'lsa) ──
if ($License) {
  if (-not (Test-Path $License)) { Warn "  ⚠ Litsenziya fayli topilmadi: $License" }
  else { & (Join-Path $Dst "Avtobus.exe") --license $License; Ok "✓ Litsenziya o'rnatildi" }
}

# ── 5) Rejalashtirilган vazifa: BOOT autostart + crash restart ──
Say "`nVazifa ro'yxatga olinmoqda (boot autostart + restart)..."
$exe = Join-Path $Dst "Avtobus.exe"
$action    = New-ScheduledTaskAction -Execute $exe -WorkingDirectory $Dst
$trigger   = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
try {
  Register-ScheduledTask -TaskName $Svc -Action $action -Trigger $trigger `
      -Principal $principal -Settings $settings -Force -ErrorAction Stop | Out-Null
  Ok "✓ '$Svc' vazifasi (boot'da, login shart emas, qulasa restart)"
} catch {
  Die "Vazifani ro'yxatga olib bo'lmadi: $($_.Exception.Message)"
}

# Watchdog (hang bo'lsa qayta yoqadi) — har 2 daqiqa
schtasks /Create /TN "AvtobusWatchdog" /RU SYSTEM /RL HIGHEST /SC MINUTE /MO 2 /F `
  /TR "powershell -NoProfile -ExecutionPolicy Bypass -File `"$Dst\watchdog.ps1`"" | Out-Null
Ok "✓ 'AvtobusWatchdog' (hang bo'lsa qayta yoqadi)"

# Hoziroq ishga tushiramiz
Start-ScheduledTask -TaskName $Svc
Start-Sleep -Seconds 3

# ── Manzil ── (gateway'ga marshrutlangan HAQIQIY LAN IP — Radmin/Tailscale/WSL
# virtual adapterlari emas. UDP "ulanish" paket yubormaydi, faqat manba IP.)
$ip = $null
try {
  $sock = New-Object System.Net.Sockets.Socket([Net.Sockets.AddressFamily]::InterNetwork, [Net.Sockets.SocketType]::Dgram, [Net.Sockets.ProtocolType]::Udp)
  $sock.Connect("8.8.8.8", 80); $ip = $sock.LocalEndPoint.Address.ToString(); $sock.Dispose()
} catch {}
if (-not $ip -or $ip -like '127.*') {
  $ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
         Where-Object { $_.IPAddress -like '192.168.*' -or $_.IPAddress -like '10.*' } |
         Select-Object -First 1 -ExpandProperty IPAddress)
}
if (-not $ip) { $ip = "<qurilma-IP>" }
Ok "`n════════════════════════════════════════════"
Ok " ✓ TAYYOR — Avtobus o'rnatildi va ishga tushdi"
Ok "════════════════════════════════════════════"
Write-Host "  Yo'lovchilar:   http://$ip/"
Write-Host "  Holat / HW ID:  $Dst\holat.bat  (yoki Avtobus.exe --license-status)"
Write-Host "  Loglar:         $Dst\logs\"
Write-Host "  Boshqarish:     schtasks /Run /TN Avtobus   |   /End /TN Avtobus"
