<#
  set-domain.ps1 — Kiosk qurilmasida veb domenini sozlaydi (oflayn, DNS'siz).

  Har bir kiosk qurilmaning hosts fayliga "<server-ip>  poyezd.uz" yozadi, shunda
  qurilma brauzeri http://poyezd.uz ni server IP'ga yo'naltiradi. Internetga
  chiqmaydi. Kiosk installeri buni AVTOMATIK chaqiradi (server IP o'rnatishda
  kiritilgan) — qo'lda hech narsa qilish shart emas.

  Ishlatish (admin PowerShell):
    .\set-domain.ps1 -ServerIp 192.168.136.69
    .\set-domain.ps1 -ServerIp 192.168.136.69 -Domain poyezd.uz

  Idempotent: qayta ishga tushirilsa dublikat yozmaydi (IP o'zgargan bo'lsa yangilaydi).
#>
param(
  [Parameter(Mandatory = $true)] [string] $ServerIp,
  [string] $Domain = "poyezd.uz"
)

$hosts = "$env:WINDIR\System32\drivers\etc\hosts"
$marker = "# Kiosk veb (avto)"

if (-not (Test-Path $hosts)) {
  Write-Error "hosts fayli topilmadi: $hosts"
  exit 1
}

# Shu domenga tegishli eski (avto) yozuvlarni olib tashlaymiz, so'ng yangisini qo'shamiz.
$lines = Get-Content $hosts -ErrorAction Stop | Where-Object {
  -not ($_ -match "\s$([regex]::Escape($Domain))(\s|$)" -and $_ -match [regex]::Escape($marker))
}
$lines += "$ServerIp`t$Domain`t$marker"

# hosts faylini Windows Defender kuzatadi — vaqtincha band bo'lishi mumkin.
# Bir necha marta qayta urinamiz (sharing violation o'tib ketadi).
$ok = $false
for ($i = 1; $i -le 5; $i++) {
  try {
    Set-Content -Path $hosts -Value $lines -Encoding ASCII -ErrorAction Stop
    $ok = $true
    break
  } catch {
    Start-Sleep -Milliseconds 500
    $err = $_.Exception.Message
  }
}
if ($ok) {
  Write-Host "OK: $Domain -> $ServerIp (hosts yangilandi)"
} else {
  Write-Error "hosts'ga yozib bo'lmadi (admin huquqi kerak): $err"
  exit 1
}
