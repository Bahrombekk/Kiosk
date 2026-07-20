"""
hotspot.py — Server kompyuterida Wi-Fi tarqatish (hotspot) ni dasturiy
boshqaradi. Kiosklar shu Wi-Fi'ga ulanib, `poyezd.uz`/8765 orqali serverga
kiradi — alohida router shart emas (internet ham shart emas: faqat lokal
tarmoq yetarli).

IKKI USUL (birinchisi ishlamasa ikkinchisiga o'tadi):

  1) Windows Mobile Hotspot (WinRT NetworkOperatorTetheringManager) — zamonaviy
     Windows 10/11 usuli. SSID/parolni sozlaydi va yoqadi. Odatda internet
     ulanish profili (Ethernet/mobil) bo'lishini talab qiladi.
  2) `netsh wlan hostednetwork` — eski SoftAP. Internetsiz ham ishlaydi, LEKIN
     ko'p zamonaviy Wi-Fi drayverlar qo'llamaydi ("Hosted network: No").

Ikkalasi ham ADMIN huquqini talab qiladi. Muvaffaqiyatsiz bo'lsa server
baribir ishlaydi (mavjud Ethernet/Wi-Fi orqali) — faqat log'ga yoziladi.

DIQQAT: bu tizim tarmog'ini o'zgartiradi — REAL server mashinasida tekshiring.
"""
import logging
import subprocess

log = logging.getLogger("kiosk.hotspot")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _ps(script, timeout=30):
    """PowerShell skriptini ishga tushiradi -> (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-Command", script],
            capture_output=True, text=True, timeout=timeout,
            creationflags=_NO_WINDOW)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except Exception as e:                               # noqa: BLE001
        return 1, "", str(e)


# --- Usul 1: Windows Mobile Hotspot (WinRT) --------------------------------
# WinRT async metodlarini PowerShell'da kutish uchun kichik yordamchi (Await).
_WINRT_PRELUDE = r"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
  ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
      $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $resultType) {
  $task = $asTaskGeneric.MakeGenericMethod($resultType).Invoke($null, @($op))
  $task.Wait(-1) | Out-Null
  $task.Result
}
function AwaitAction($op) {
  $t = [System.WindowsRuntimeSystemExtensions]::AsTask($op)
  $t.Wait(-1) | Out-Null
}
[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime] | Out-Null
[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime] | Out-Null
$profile = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if ($null -eq $profile) { Write-Output 'NO_PROFILE'; exit 3 }
$mgr = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
"""


def _winrt_start(ssid, password):
    # Band: 2.4 GHz'ni MAJBURLAYMIZ — ko'p telefonlar (ayniqsa arzon/eski)
    # faqat 2.4 GHz ni ko'radi; Windows default '5 GHz / Auto' bo'lsa tarmoq
    # ularda umuman ko'rinmaydi. IsBandSupported/Band Windows 10 2004+ da bor —
    # eski Windows'da try/catch jim o'tadi (u holda default band ishlatiladi).
    script = _WINRT_PRELUDE + f"""
$cfg = $mgr.GetCurrentAccessPointConfiguration()
$cfg.Ssid = '{_esc(ssid)}'
$cfg.Passphrase = '{_esc(password)}'
try {{
  $band24 = [Windows.Networking.NetworkOperators.TetheringWiFiBand]::TwoPointFourGigahertz
  if ($cfg.IsBandSupported($band24)) {{ $cfg.Band = $band24 }}
}} catch {{ }}
# Band o'zgarishi FAOL hotspot'ga qo'llanishi uchun avval to'xtatamiz
if ($mgr.TetheringOperationalState -eq [Windows.Networking.NetworkOperators.TetheringOperationalState]::On) {{
  AwaitAction($mgr.StopTetheringAsync())
}}
AwaitAction($mgr.ConfigureAccessPointAsync($cfg))
$res = Await ($mgr.StartTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
if ($res.Status -eq [Windows.Networking.NetworkOperators.TetheringOperationStatus]::Success) {{
  Write-Output 'OK'; exit 0
}} else {{
  Write-Output ('FAIL:' + $res.Status + ':' + $res.AdditionalErrorMessage); exit 2
}}
"""
    rc, out, err = _ps(script, timeout=45)
    if rc == 0 and ("OK" in out or "ALREADY_ON" in out):
        return True, out
    return False, (out or err or f"rc={rc}")


def _winrt_stop():
    script = _WINRT_PRELUDE + """
AwaitAction($mgr.StopTetheringAsync())
Write-Output 'OK'; exit 0
"""
    rc, out, err = _ps(script, timeout=30)
    return rc == 0, (out or err)


def _winrt_active():
    script = _WINRT_PRELUDE + """
Write-Output $mgr.TetheringOperationalState
"""
    rc, out, _ = _ps(script, timeout=20)
    return rc == 0 and "On" in out


def _esc(s):
    """PowerShell single-quote uchun xavfsizlash (' -> '')."""
    return str(s).replace("'", "''")


# --- Usul 2: netsh hostednetwork (eski SoftAP) -----------------------------
def _netsh_start(ssid, password):
    rc, out, err = _ps(
        f"netsh wlan set hostednetwork mode=allow "
        f"ssid=\"{ssid}\" key=\"{password}\"", timeout=20)
    rc2, out2, err2 = _ps("netsh wlan start hostednetwork", timeout=20)
    ok = rc2 == 0 and "started" in (out2 or "").lower()
    if not ok and "not supported" in (out2 + err2).lower():
        return False, "adapter hostednetwork'ni qo'llamaydi"
    return ok, (out2 or err2)


def _netsh_stop():
    rc, out, err = _ps("netsh wlan stop hostednetwork", timeout=20)
    return rc == 0, (out or err)


# --- Umumiy interfeys -------------------------------------------------------
_method = None   # muvaffaqiyatli usul eslab qolinadi (stop uchun)


def start(ssid, password):
    """Hotspot'ni yoqadi (avval Mobile Hotspot, keyin netsh). (ok, xabar)."""
    global _method
    if not ssid or not password or len(password) < 8:
        return False, "SSID kerak va parol kamida 8 belgi bo'lsin"
    ok, msg = _winrt_start(ssid, password)
    if ok:
        _method = "winrt"
        log.info("Wi-Fi hotspot yoqildi (Mobile Hotspot): SSID=%s", ssid)
        return True, "Mobile Hotspot"
    log.info("Mobile Hotspot ishlamadi (%s) — netsh usuliga o'tamiz", msg)
    ok2, msg2 = _netsh_start(ssid, password)
    if ok2:
        _method = "netsh"
        log.info("Wi-Fi hotspot yoqildi (netsh): SSID=%s", ssid)
        return True, "netsh hostednetwork"
    log.warning("Wi-Fi hotspot yoqilmadi. Mobile Hotspot: %s | netsh: %s",
                msg, msg2)
    return False, f"Mobile Hotspot: {msg}; netsh: {msg2}"


def stop():
    """Hotspot'ni o'chiradi (qaysi usul yoqqan bo'lsa)."""
    if _method == "netsh":
        return _netsh_stop()
    if _method == "winrt":
        return _winrt_stop()
    # Noma'lum — ikkalasini ham to'xtatishga urinamiz
    _winrt_stop()
    _netsh_stop()
    return True, "to'xtatildi"


def is_active():
    """Hotspot hozir yoqilganmi (Mobile Hotspot holati bo'yicha)."""
    try:
        return _winrt_active()
    except Exception:                                    # noqa: BLE001
        return False
