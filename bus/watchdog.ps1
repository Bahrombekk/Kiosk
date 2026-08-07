# ============================================================================
#  watchdog.ps1 — Avtobus OSILIB qolsa (hang) qayta yoqadi.
#
#  Ikki o'rnatish rejimini ham qo'llaydi:
#    - NSSM xizmat  ("Avtobus" nomli Windows Service bo'lsa) -> nssm restart
#    - Task Scheduler ("Avtobus" nomli vazifa)               -> kill + qayta start
#
#  Boot/crash'ni xizmat/vazifaning O'ZI qoplaydi; bu skript esa jarayon tirik-u
#  JAVOB BERMAY qolган holatni: har 2 daqiqada /api/health, 3 marta ketma-ket
#  javob bermasa qayta yoqadi (bir martalik sekinlik yolg'on trigger bermasin).
# ============================================================================
$ErrorActionPreference = "SilentlyContinue"
$name      = "Avtobus"
$health    = "http://127.0.0.1:8765/api/health"
$stateFile = Join-Path $PSScriptRoot "logs\watchdog.state"
$logFile   = Join-Path $PSScriptRoot "logs\watchdog.log"
function LogLine($m){ Add-Content $logFile "$(Get-Date -Format s)  $m" }

# Boshqaruv rejimini aniqlaymiz
$svc  = Get-Service $name -ErrorAction SilentlyContinue
$task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue

if ($svc) {
  if ($svc.Status -ne 'Running') { exit 0 }   # ataylab to'xtatilgan — tegmaymiz
} elseif (-not $task) {
  exit 0                                       # umuman o'rnatilmagan
}

# Sog'liq tekshiruvi
$ok = $false
try {
  $r = Invoke-WebRequest -Uri $health -TimeoutSec 15 -UseBasicParsing
  if ($r.StatusCode -eq 200) { $ok = $true }
} catch { $ok = $false }
if ($ok) { Set-Content $stateFile "0"; exit 0 }

# Ketma-ket xatolar
$fails = 0
if (Test-Path $stateFile) { $fails = [int]((Get-Content $stateFile) -as [int]) }
$fails++
Set-Content $stateFile "$fails"
LogLine "health javob bermadi (ketma-ket $fails)"
if ($fails -lt 3) { exit 0 }

LogLine "3 marta ketma-ket — qayta yoqilmoqda"
$nssm = Join-Path $PSScriptRoot "nssm.exe"
if ($svc -and (Test-Path $nssm)) {
  & $nssm restart $name | Out-Null
} else {
  # Task Scheduler: osilган jarayonni majburan yopib, vazifani qayta boshlaymiz
  taskkill /IM Avtobus.exe /F 2>$null | Out-Null
  taskkill /IM node.exe /F     2>$null | Out-Null
  Start-Sleep -Seconds 2
  Start-ScheduledTask -TaskName $name
}
Set-Content $stateFile "0"
