# receiver.ps1 — Kontent qabul qiluvchi (NISHON kompyuterda ishlaydi).
#
# Nima qiladi:
#   - Kiosk Server o'rnatilgan papkani (data.db + content/) topadi.
#   - LAN IP + bir martalik token chiqaradi (ularni yuboruvchiga berasiz).
#   - Oddiy TCP protokol orqali: serverni to'xtatadi, data.db'ni beradi/qabul
#     qiladi, content/ fayllarini qabul qiladi, serverni qayta ishga tushiradi.
#
# Admin shart EMAS (raw TcpListener, HttpListener emas).
#
# Ishga tushirish (PowerShell'da):
#   powershell -ExecutionPolicy Bypass -File receiver.ps1
# yoki papka boshqa joyda bo'lsa:
#   powershell -ExecutionPolicy Bypass -File receiver.ps1 -BaseDir "D:\KioskServer"

param(
    [string]$BaseDir = "",
    [int]$Port = 8799,
    # Faqat shu IP'lardan qabul qilish (bo'sh = birinchi to'g'ri token kelgan
    # IP'ga avtomatik "pin" qilinadi, boshqalar rad etiladi)
    [string[]]$AllowFrom = @(),
    # Shuncha daqiqa faoliyatsiz tursa o'zini o'chiradi (0 = cheksiz)
    [int]$IdleTimeoutMin = 30
)

$ErrorActionPreference = "Stop"
$ExeName = "KioskServer.exe"
$ProcName = "KioskServer"

# XAVFSIZLIK: bu vosita faqat ISHONCHLI, izolyatsiya qilingan tarmoqda (masalan
# ikkala kompyuter bitta switch/hotspot'da) ishlatilsin. Transport shifrlanmagan
# TCP — ochiq/umumiy Wi-Fi'da ishlatmang: data.db ichida API kalit va parol
# xeshlari bor. Qo'shimcha himoya qatlamlari: token (bir martalik), IP pinning,
# `put` faqat content/ va data.db bilan cheklangan (exe almashtirib bo'lmaydi).

# --- Baza papkasini aniqlash -------------------------------------------------
function Find-BaseDir {
    param([string]$Given)
    if ($Given -and (Test-Path $Given)) { return (Resolve-Path $Given).Path }
    # 1) Ishlab turgan KioskServer jarayonidan yo'lni olamiz (eng ishonchli)
    try {
        $p = Get-Process -Name $ProcName -ErrorAction SilentlyContinue |
             Select-Object -First 1
        if ($p -and $p.Path) { return (Split-Path -Parent $p.Path) }
    } catch {}
    # 2) Skript joylashgan papka (agar installatsiya ichiga qo'yilgan bo'lsa)
    $here = Split-Path -Parent $MyInvocation.MyCommand.Path
    if (Test-Path (Join-Path $here $ExeName)) { return $here }
    # 3) Standart o'rnatish yo'li
    if (Test-Path "C:\KioskServer") { return "C:\KioskServer" }
    throw "Kiosk Server papkasi topilmadi. -BaseDir bilan ko'rsating."
}

$BaseDir = Find-BaseDir -Given $BaseDir
$DbPath = Join-Path $BaseDir "data.db"
$ContentDir = Join-Path $BaseDir "content"
$ExePath = Join-Path $BaseDir $ExeName

# --- Token va tarmoq manzillari ----------------------------------------------
$Token = ([guid]::NewGuid().ToString("N")).Substring(0, 16)

# Token taqqoslash — to'g'ridan-to'g'ri string solishtirish (-eq) timing
# ma'lumotini oqizishi mumkin; ikkala qiymatning SHA-256 xeshini solishtiramiz
# (xesh ustidagi timing farqi tokenni tiklashga yordam bermaydi).
$Sha256 = [System.Security.Cryptography.SHA256]::Create()
$TokenHash = $Sha256.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Token))
function Test-Token {
    param([string]$Given)
    if (-not $Given) { return $false }
    $h = $Sha256.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Given))
    if ($h.Length -ne $TokenHash.Length) { return $false }
    $diff = 0
    for ($i = 0; $i -lt $h.Length; $i++) { $diff = $diff -bor ($h[$i] -bxor $TokenHash[$i]) }
    return ($diff -eq 0)
}

# Noto'g'ri token urinishlari (IP bo'yicha) — 5 tadan keyin o'sha IP bloklanadi
$script:BadTries = @{}
$script:PinnedPeer = $null   # birinchi to'g'ri token kelgan IP

function Get-LanIPs {
    try {
        return (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object {
                $_.IPAddress -ne "127.0.0.1" -and
                $_.IPAddress -notlike "169.254.*"
            } | Select-Object -ExpandProperty IPAddress)
    } catch {
        return @([System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
            Where-Object { $_.AddressFamily -eq "InterNetwork" } |
            ForEach-Object { $_.IPAddressToString })
    }
}

# --- Yordamchi: protokol I/O -------------------------------------------------
function Read-Line {
    param($Stream)
    $bytes = New-Object System.Collections.Generic.List[byte]
    while ($true) {
        $b = $Stream.ReadByte()
        if ($b -lt 0) { break }
        if ($b -eq 10) { break }          # \n
        if ($b -ne 13) { $bytes.Add([byte]$b) }  # \r ni tashlab yuboramiz
    }
    return [System.Text.Encoding]::UTF8.GetString($bytes.ToArray())
}

function Write-Line {
    param($Stream, [string]$Text)
    $data = [System.Text.Encoding]::UTF8.GetBytes($Text + "`n")
    $Stream.Write($data, 0, $data.Length)
    $Stream.Flush()
}

function Send-Json {
    param($Stream, $Obj)
    Write-Line $Stream ($Obj | ConvertTo-Json -Compress -Depth 6)
}

function Read-Exact-ToFile {
    param($Stream, [string]$Path, [long]$Size)
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $tmp = "$Path.part"
    $fs = [System.IO.File]::Create($tmp)
    try {
        $buf = New-Object byte[] (1MB)
        $remaining = $Size
        while ($remaining -gt 0) {
            $toRead = [Math]::Min([long]$buf.Length, $remaining)
            $read = $Stream.Read($buf, 0, [int]$toRead)
            if ($read -le 0) { throw "ulanish uzildi (qabulda)" }
            $fs.Write($buf, 0, $read)
            $remaining -= $read
        }
    } finally {
        $fs.Close()
    }
    if (Test-Path $Path) { Remove-Item $Path -Force }
    Move-Item $tmp $Path -Force
}

# --- Buyruqlar ---------------------------------------------------------------
function Stop-KioskServer {
    $proc = Get-Process -Name $ProcName -ErrorAction SilentlyContinue
    if ($proc) {
        cmd /c "taskkill /IM $ExeName /F /T" | Out-Null
    }
    # data.db yozish uchun bo'shashini kutamiz (lock tugashi)
    for ($i = 0; $i -lt 30; $i++) {
        if (-not (Test-Path $DbPath)) { return $true }
        try {
            $f = [System.IO.File]::Open($DbPath, "Open", "ReadWrite", "None")
            $f.Close()
            return $true
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    return $false
}

function Start-KioskServer {
    if (Test-Path $ExePath) {
        Start-Process -FilePath $ExePath -WorkingDirectory $BaseDir | Out-Null
        return $true
    }
    return $false
}

function Get-ContentManifest {
    $map = @{}
    if (Test-Path $ContentDir) {
        Get-ChildItem -Path $ContentDir -Recurse -File | ForEach-Object {
            $rel = $_.FullName.Substring($BaseDir.Length).TrimStart('\','/')
            $rel = $rel -replace '\\', '/'
            $map[$rel] = $_.Length
        }
    }
    return $map
}

function Resolve-SafePath {
    param([string]$Rel)
    if ($Rel -match '\.\.') { throw "yaroqsiz yo'l: $Rel" }
    $rel = $Rel -replace '/', '\'
    $full = [System.IO.Path]::GetFullPath((Join-Path $BaseDir $rel))
    $baseFull = [System.IO.Path]::GetFullPath($BaseDir)
    if (-not $full.StartsWith($baseFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "yo'l papka tashqarisida: $Rel"
    }
    return $full
}

function Handle-Client {
    param($Client, [string]$PeerIp)
    $stream = $Client.GetStream()
    try {
        # IP darajasidagi nazorat: aniq allowlist (-AllowFrom) yoki birinchi
        # to'g'ri token kelgan IP'ga avtomatik pinning — begona qurilma token
        # bilsa ham boshqa IP'dan ulanolmaydi.
        if ($AllowFrom.Count -gt 0 -and ($AllowFrom -notcontains $PeerIp)) {
            Send-Json $stream @{ ok = $false; error = "IP ruxsat etilmagan" }
            return $false
        }
        if ($script:PinnedPeer -and $PeerIp -ne $script:PinnedPeer) {
            Send-Json $stream @{ ok = $false; error = "boshqa qurilma ulangan" }
            return $false
        }
        if ($script:BadTries[$PeerIp] -ge 5) {
            Send-Json $stream @{ ok = $false; error = "juda ko'p xato urinish" }
            return $false
        }
        $line = Read-Line $stream
        if (-not $line) { return $false }
        $req = $line | ConvertFrom-Json
        if (-not (Test-Token $req.token)) {
            $script:BadTries[$PeerIp] = [int]$script:BadTries[$PeerIp] + 1
            Send-Json $stream @{ ok = $false; error = "token xato" }
            return $false
        }
        if (-not $script:PinnedPeer) { $script:PinnedPeer = $PeerIp }
        switch ($req.cmd) {
            "hello" {
                $n = 0
                if (Test-Path $ContentDir) {
                    $n = (Get-ChildItem $ContentDir -Recurse -File |
                          Measure-Object).Count
                }
                Send-Json $stream @{
                    ok = $true; base = $BaseDir;
                    has_db = (Test-Path $DbPath); content_files = $n
                }
            }
            "stop" {
                $ok = Stop-KioskServer
                Send-Json $stream @{ ok = $ok }
            }
            "start" {
                $ok = Start-KioskServer
                Send-Json $stream @{ ok = $ok }
            }
            "manifest" {
                $map = Get-ContentManifest
                $json = ($map | ConvertTo-Json -Compress -Depth 4)
                if (-not $json) { $json = "{}" }
                $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
                Send-Json $stream @{ ok = $true; size = $bytes.Length }
                $stream.Write($bytes, 0, $bytes.Length)
                $stream.Flush()
            }
            "get_db" {
                if (-not (Test-Path $DbPath)) {
                    Send-Json $stream @{ ok = $true; size = 0 }
                } else {
                    $fi = Get-Item $DbPath
                    Send-Json $stream @{ ok = $true; size = $fi.Length }
                    $fs = [System.IO.File]::OpenRead($DbPath)
                    try { $fs.CopyTo($stream); $stream.Flush() }
                    finally { $fs.Close() }
                }
            }
            "put" {
                $target = Resolve-SafePath $req.path
                # MUHIM CHEKLOV: faqat content/ ichiga yoki data.db'ga yozish
                # mumkin. BaseDir ildiziga (KioskServer.exe va boshqa dastur
                # fayllariga) yozish taqiqlanadi — aks holda token bilgan
                # hujumchi exe'ni almashtirib RCE olishi mumkin edi.
                $contentFull = [System.IO.Path]::GetFullPath($ContentDir).TrimEnd('\') + '\'
                $dbFull = [System.IO.Path]::GetFullPath($DbPath)
                $isContent = $target.StartsWith($contentFull, [StringComparison]::OrdinalIgnoreCase)
                $isDb = [string]::Equals($target, $dbFull, [StringComparison]::OrdinalIgnoreCase)
                if (-not ($isContent -or $isDb)) {
                    throw "ruxsat yo'q: faqat content/ yoki data.db (berilgan: $($req.path))"
                }
                Read-Exact-ToFile $stream $target ([long]$req.size)
                Send-Json $stream @{ ok = $true }
            }
            "hash" {
                # Bitta faylning SHA-256 xeshi — sender --verify rejimi uchun
                # (bir xil o'lchamli, lekin farqli kontentni aniqlash).
                $target = Resolve-SafePath $req.path
                if (Test-Path $target) {
                    $hh = (Get-FileHash -Algorithm SHA256 -Path $target).Hash.ToLower()
                    Send-Json $stream @{ ok = $true; sha256 = $hh }
                } else {
                    Send-Json $stream @{ ok = $true; sha256 = $null }
                }
            }
            default {
                Send-Json $stream @{ ok = $false; error = "noma'lum buyruq" }
            }
        }
        return $true
    } catch {
        try { Send-Json $stream @{ ok = $false; error = "$($_.Exception.Message)" } } catch {}
        return $false
    } finally {
        $stream.Close()
        $Client.Close()
    }
}

# --- Ishga tushirish ---------------------------------------------------------
Write-Host ""
Write-Host "===================== KIOSK KONTENT QABULCHISI =====================" -ForegroundColor Cyan
Write-Host " Papka   : $BaseDir"
Write-Host " Baza    : $(if (Test-Path $DbPath) {'bor'} else {'yo''q (yangi yaratiladi)'})"
Write-Host " Port    : $Port"
Write-Host ""
Write-Host " Quyidagilarni yuboruvchiga (Claude'ga) BERING:" -ForegroundColor Yellow
foreach ($ip in Get-LanIPs) {
    Write-Host ("   --host {0} --port {1} --token {2}" -f $ip, $Port, $Token) -ForegroundColor Green
}
Write-Host ""
Write-Host " Kutilmoqda... (to'xtatish uchun Ctrl+C)" -ForegroundColor Gray
Write-Host "===================================================================="
Write-Host ""

$listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, $Port)
$listener.Start()
$deadline = $null
if ($IdleTimeoutMin -gt 0) { $deadline = (Get-Date).AddMinutes($IdleTimeoutMin) }
try {
    while ($true) {
        # Bloklovchi Accept o'rniga polling — faoliyatsizlik timeout'ini
        # tekshirib turamiz (unutilgan receiver ochiq xizmat bo'lib qolmasin).
        if (-not $listener.Pending()) {
            if ($deadline -and (Get-Date) -gt $deadline) {
                Write-Host " Faoliyatsizlik $IdleTimeoutMin daqiqadan oshdi - yopilmoqda." -ForegroundColor Yellow
                break
            }
            Start-Sleep -Milliseconds 200
            continue
        }
        $client = $listener.AcceptTcpClient()
        $client.ReceiveTimeout = 600000
        $client.SendTimeout = 600000
        $peerIp = $client.Client.RemoteEndPoint.Address.ToString()
        $ts = (Get-Date).ToString("HH:mm:ss")
        $ok = Handle-Client $client $peerIp
        if ($ok) {
            if ($IdleTimeoutMin -gt 0) { $deadline = (Get-Date).AddMinutes($IdleTimeoutMin) }
            Write-Host ("[{0}] {1} - so'rov bajarildi" -f $ts, $peerIp) -ForegroundColor DarkGray
        } else {
            Write-Host ("[{0}] {1} - RAD ETILDI" -f $ts, $peerIp) -ForegroundColor Red
        }
    }
} finally {
    $listener.Stop()
}
