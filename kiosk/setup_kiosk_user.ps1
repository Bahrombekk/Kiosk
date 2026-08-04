# setup_kiosk_user.ps1 — kiosk uchun cheklangan Windows foydalanuvchisi
# va shell almashtirishni sozlaydi. ADMIN PowerShell'da ishga tushiring:
#   powershell -ExecutionPolicy Bypass -File setup_kiosk_user.ps1
#
# Nima qiladi:
#   1) "kiosk" nomli STANDART (admin bo'lmagan) foydalanuvchi yaratadi
#   2) Uning shell'ini Explorer o'rniga KioskWatchdog.exe ga almashtiradi
#      (foydalanuvchi kirganda ish stoli o'rniga to'g'ridan-to'g'ri kiosk)
# Avto-kirishni qo'lda yoqing: netplwiz (DEPLOYMENT-LOCKDOWN.md 2.2-bo'lim)

$ErrorActionPreference = "Stop"

$UserName = "kiosk"
$ShellPath = "C:\Kiosk\KioskWatchdog.exe"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
        ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Bu skript ADMIN PowerShell'da ishga tushirilishi kerak."
}

if (-not (Test-Path $ShellPath)) {
    Write-Error "$ShellPath topilmadi. Avval KioskSetup.exe ni o'rnating."
}

# 1) Foydalanuvchi
$exists = Get-LocalUser -Name $UserName -ErrorAction SilentlyContinue
if ($exists) {
    Write-Host "'$UserName' foydalanuvchisi allaqachon bor — o'tkazib yuborildi."
} else {
    $pw = Read-Host "Yangi '$UserName' foydalanuvchisi uchun parol" -AsSecureString
    New-LocalUser -Name $UserName -Password $pw -FullName "Kiosk" `
        -Description "Kiosk rejimi uchun cheklangan hisob" -PasswordNeverExpires
    Add-LocalGroupMember -Group "Users" -Member $UserName
    Write-Host "'$UserName' yaratildi (standart huquqlar)."
}

# 2) Shell almashtirish — foydalanuvchi HKCU'siga yozish uchun uning SID'i
#    bilan HKEY_USERS orqali ishlaymiz (foydalanuvchi hali kirmagan bo'lsa
#    profil yo'q — bu holda birinchi kirishdan keyin qayta ishga tushiring).
$sid = (Get-LocalUser -Name $UserName).SID.Value
$hive = "Registry::HKEY_USERS\$sid"
if (Test-Path $hive) {
    $winlogon = "$hive\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
    if (-not (Test-Path $winlogon)) { New-Item -Path $winlogon -Force | Out-Null }
    Set-ItemProperty -Path $winlogon -Name "Shell" -Value $ShellPath
    Write-Host "Shell almashtirildi: $ShellPath"
} else {
    Write-Warning ("'$UserName' profili hali yaratilmagan. Avval shu hisob bilan " +
        "bir marta tizimga kiring, so'ng skriptni qayta ishga tushiring.")
}

Write-Host ""
Write-Host "Keyingi qadam: netplwiz orqali '$UserName' uchun avto-kirishni yoqing."
Write-Host "Batafsil: DEPLOYMENT-LOCKDOWN.md"
