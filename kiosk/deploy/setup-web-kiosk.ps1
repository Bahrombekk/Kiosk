<#
  setup-web-kiosk.ps1 -- Kiosk qurilmani BIR MARTA sozlaydi (veb variant).

  Nima qiladi:
    1. Server Wi-Fi (hotspot) siga avtomatik ulanish profilini qo'shadi --
       qurilma har yoqilganda o'zi ulanadi.
    2. hosts fayliga <server-ip>  poyezd.uz yozadi (set-domain.ps1 orqali).
    3. start-web-kiosk.ps1 ni AVTOSTARTga qo'yadi (har login'da Chrome kiosk
       rejimida poyezd.uz ochiladi).

  ADMIN PowerShell'da bir marta ishga tushiring:
    .\setup-web-kiosk.ps1 -ServerIp 192.168.137.1 -Ssid KioskServer -WifiPass kiosk12345

  Parametrlar server admin panelidagi qiymatlar bilan bir xil bo'lsin
  (Sozlamalar -> Wi-Fi tarqatish: SSID/parol; ServerIp odatda 192.168.137.1).
#>
param(
  [Parameter(Mandatory = $true)] [string] $ServerIp,
  [Parameter(Mandatory = $true)] [string] $Ssid,
  [Parameter(Mandatory = $true)] [string] $WifiPass,
  [string] $Domain = "poyezd.uz"
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Assert-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object Security.Principal.WindowsPrincipal($id)
  if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Bu skript ADMIN huquqida ishlashi kerak (PowerShell'ni Administrator bilan oching)."
    exit 1
  }
}
Assert-Admin

# --- 1) Wi-Fi avto-ulanish profili -----------------------------------------
Write-Host "1/3  Wi-Fi profili qo'shilmoqda..." -ForegroundColor Cyan
# SSID/parolni XML uchun xavfsiz belgilarga aylantiramiz (built-in escaper)
$ssidX = [System.Security.SecurityElement]::Escape($Ssid)
$passX = [System.Security.SecurityElement]::Escape($WifiPass)
$hexSsid = -join ($Ssid.ToCharArray() | ForEach-Object { "{0:X2}" -f [int][char]$_ })
$profileXml = @"
<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>$ssidX</name>
  <SSIDConfig>
    <SSID>
      <hex>$hexSsid</hex>
      <name>$ssidX</name>
    </SSID>
  </SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>auto</connectionMode>
  <MSM>
    <security>
      <authEncryption>
        <authentication>WPA2PSK</authentication>
        <encryption>AES</encryption>
        <useOneX>false</useOneX>
      </authEncryption>
      <sharedKey>
        <keyType>passPhrase</keyType>
        <protected>false</protected>
        <keyMaterial>$passX</keyMaterial>
      </sharedKey>
    </security>
  </MSM>
</WLANProfile>
"@
$tmp = Join-Path $env:TEMP "kiosk_wifi_profile.xml"
Set-Content -Path $tmp -Value $profileXml -Encoding UTF8
$addOut = netsh wlan add profile filename="$tmp" user=all 2>&1
Remove-Item $tmp -Force -ErrorAction SilentlyContinue
Write-Host ("     " + $addOut)
netsh wlan connect name="$Ssid" 2>&1 | Out-Null
Write-Host "     Wi-Fi profil qo'shildi (qurilma har yoqilganda avto-ulanadi)." -ForegroundColor Green

# --- 2) hosts: poyezd.uz -> server IP --------------------------------------
Write-Host "2/3  Domen sozlanmoqda..." -ForegroundColor Cyan
$setDomain = Join-Path $here "set-domain.ps1"
if (Test-Path $setDomain) {
  & $setDomain -ServerIp $ServerIp -Domain $Domain
} else {
  Write-Warning "set-domain.ps1 topilmadi -- hosts qo'lda sozlang."
}

# --- 3) Avtostart: start-web-kiosk.ps1 -------------------------------------
Write-Host "3/3  Avtostart o'rnatilmoqda..." -ForegroundColor Cyan
$launcher = Join-Path $here "start-web-kiosk.ps1"
if (-not (Test-Path $launcher)) {
  Write-Error "start-web-kiosk.ps1 topilmadi"
  exit 1
}
# Startup papkasiga .cmd -- login'da yashirin oynada launcherni ishga tushiradi.
$startup = [Environment]::GetFolderPath("Startup")
$cmdPath = Join-Path $startup "KioskWeb.cmd"
$cmdBody = @"
@echo off
powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "$launcher" -Url "http://$Domain"
"@
Set-Content -Path $cmdPath -Value $cmdBody -Encoding ASCII
Write-Host ("     Avtostart: " + $cmdPath) -ForegroundColor Green

Write-Host ""
Write-Host "TAYYOR." -ForegroundColor Green
Write-Host "Qurilmani qayta yoqing (yoki hoziroq sinash uchun):" -ForegroundColor Yellow
Write-Host ('  powershell -ExecutionPolicy Bypass -File "' + $launcher + '"')
Write-Host ""
Write-Host "Eslatma: bu VEB variant (Chrome/Edge kiosk). Chrome bolmasa Edge"
Write-Host "ishlatiladi. Ikkalasi ham yoq bolsa Chrome ornating."
