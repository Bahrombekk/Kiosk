<#
  start-web-kiosk.ps1 — Kiosk qurilma yoqilganda brauzerni KIOSK rejimida ochadi.

  Ishlash tartibi:
    1. Server tayyor bo'lishini kutadi (http://domen javob bergunicha, cheksiz
       kutadi -- poyezd yo'lda bo'lsa server keyinroq ko'tarilishi mumkin).
    2. Chrome (bo'lmasa Edge) ni to'liq ekran KIOSK rejimida ochadi.
    3. Brauzer yopilib qolsa (crash yoki Alt+F4) -- qayta ochadi.

  Bu skript setup-web-kiosk.ps1 tomonidan avtostartga qo'yiladi (har login'da
  ishga tushadi). Qo'lda sinash:
    powershell -ExecutionPolicy Bypass -File start-web-kiosk.ps1
#>
param(
  [string] $Url = "http://poyezd.uz",
  [int]    $WaitTimeoutSec = 0     # 0 = cheksiz kutish
)

$ErrorActionPreference = "SilentlyContinue"

function Find-Browser {
  # Chrome afzal; bo'lmasa Edge (Windows'da doim bor).
  $chrome = @(
    (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe'),
    (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')
  ) | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($chrome) { return @{ Path = $chrome; Kind = 'chrome' } }
  $edge = @(
    (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
    (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe')
  ) | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($edge) { return @{ Path = $edge; Kind = 'edge' } }
  return $null
}

function Wait-Server {
  param([string]$Url, [int]$TimeoutSec)
  $start = Get-Date
  while ($true) {
    try {
      $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 4
      if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
    } catch { }
    if ($TimeoutSec -gt 0 -and ((Get-Date) - $start).TotalSeconds -gt $TimeoutSec) {
      return $false
    }
    Start-Sleep -Seconds 3
  }
}

function Start-Kiosk {
  param($Browser, [string]$Url)
  # Har qurilma uchun alohida profil papkasi (restore-session oynasi chiqmasin)
  $profileDir = Join-Path $env:LOCALAPPDATA 'KioskBrowserProfile'
  $udd = '--user-data-dir="{0}"' -f $profileDir
  if ($Browser.Kind -eq 'chrome') {
    $browserArgs = @(
      '--kiosk', $Url, $udd,
      '--no-first-run', '--no-default-browser-check',
      '--disable-session-crashed-bubble', '--disable-infobars',
      '--disable-pinch', '--overscroll-history-navigation=0',
      '--disable-features=TranslateUI',
      '--autoplay-policy=no-user-gesture-required',
      '--start-fullscreen'
    )
  } else {
    $browserArgs = @(
      '--kiosk', $Url, '--edge-kiosk-type=fullscreen', $udd,
      '--no-first-run', '--no-default-browser-check',
      '--disable-features=TranslateUI'
    )
  }
  return Start-Process -FilePath $Browser.Path -ArgumentList $browserArgs -PassThru
}

# --- Asosiy ---
$browser = Find-Browser
if (-not $browser) {
  # Chrome/Edge yo'q -- hech narsa qilmaymiz (foydalanuvchi shartli so'ragan).
  Write-Host 'Chrome/Edge topilmadi -- veb-kiosk ochilmaydi.'
  exit 0
}

Write-Host ('Brauzer: ' + $browser.Path)
Write-Host ('Server kutilmoqda: ' + $Url)
Wait-Server -Url $Url -TimeoutSec $WaitTimeoutSec | Out-Null

# Brauzer yopilib qolsa qayta ochadigan yengil watchdog (qora ekran bo'lmasin).
while ($true) {
  $proc = Start-Kiosk -Browser $browser -Url $Url
  if (-not $proc) { Start-Sleep 5; continue }
  $proc.WaitForExit()
  Start-Sleep -Seconds 2
}
