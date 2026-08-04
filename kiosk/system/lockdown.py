"""
lockdown.py — OS darajasidagi klaviatura qulfi (Windows low-level hook).

Kiosk rejimida yo'lovchi klaviatura ulasa ham tizimga chiqib keta olmasligi
kerak. Qt faqat o'z oynasidagi tugmalarni ko'radi — Win, Alt+Tab kabi tizim
kombinatsiyalarini esa Windows ilovadan oldin ushlaydi. Ularni bloklash uchun
SetWindowsHookEx(WH_KEYBOARD_LL) o'rnatamiz.

Bloklanadi: Win (chap/o'ng), Alt+Tab, Alt+Esc, Ctrl+Esc.
Bloklab BO'LMAYDI (Windows himoyalangan ketma-ketligi — SAS):
Ctrl+Alt+Del, Win+L. Ular installer o'rnatadigan registry siyosatlari bilan
zararsizlantiriladi (DisableTaskMgr, DisableLockWorkstation — installer.iss).

Faqat frozen (PyInstaller) nusxada yoki KIOSK_LOCKDOWN=1 bo'lsa yoqiladi —
ishlab chiqishda kompyuteringiz qulflanib qolmaydi.

MUHIM: hook callback'iga modul darajasida referens saqlanadi — Python GC
callback'ni yig'ishtirib yuborsa, Windows ichidan chaqirilganda crash bo'ladi.
"""
import ctypes
import ctypes.wintypes as wintypes
import logging
import os
import sys

log = logging.getLogger(__name__)

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104

VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_F4 = 0x73
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_APPS = 0x5D       # kontekst-menyu (o'ng tugma) klavishi
VK_CONTROL = 0x11
VK_SHIFT = 0x10
LLKHF_ALTDOWN = 0x20

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

_hook_handle = None
_hook_proc_ref = None   # GC dan saqlash uchun


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD),
                ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


_HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                               wintypes.WPARAM, wintypes.LPARAM)

# MUHIM (64-bit): funksiya imzolarini ANIQ belgilaymiz. Aks holda ctypes
# qaytar qiymatni c_int (32-bit) deb hisoblaydi va GetModuleHandleW/
# SetWindowsHookExW qaytargan 64-bitli HANDLE kesiladi -> yaroqsiz modul
# handle -> SetWindowsHookExW XATO 126 (ERROR_MOD_NOT_FOUND), hook o'rnatilmaydi.
_kernel32.GetModuleHandleW.restype = ctypes.c_void_p
_kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
_user32.SetWindowsHookExW.restype = ctypes.c_void_p
_user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, _HOOKPROC, ctypes.c_void_p, wintypes.DWORD]
_user32.CallNextHookEx.restype = ctypes.c_ssize_t
_user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
_user32.UnhookWindowsHookEx.restype = wintypes.BOOL
_user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]


def _should_block(vk, flags):
    # Win tugmasi (Start, Win+R/D/E/Tab/L...) — keydown'ni yutamiz, demak Win
    # bilan boshlanadigan HAR QANDAY kombinatsiya tuzilmaydi.
    if vk in (VK_LWIN, VK_RWIN):
        return True
    if vk == VK_APPS:
        return True                      # kontekst-menyu (o'ng tugma) klavishi
    alt = bool(flags & LLKHF_ALTDOWN)
    if alt and vk in (VK_TAB, VK_ESCAPE, VK_F4):
        return True                      # Alt+Tab, Alt+Esc, Alt+F4 (oynani yopish)
    ctrl = bool(_user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
    if ctrl and vk == VK_ESCAPE:
        # Ctrl+Esc (Start) VA Ctrl+Shift+Esc (Vazifa menejeri) — ikkalasi ham
        # shu shartga tushadi (Ctrl bosilgan + Esc), shuning uchun Dispetcher
        # zadach to'g'ridan-to'g'ri ochilmaydi.
        return True
    return False


def _hook_proc(n_code, w_param, l_param):
    if n_code >= 0 and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
        kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        if _should_block(kb.vkCode, kb.flags):
            return 1   # voqea yutildi — tizimga yetmaydi
    return _user32.CallNextHookEx(_hook_handle, n_code, w_param, l_param)


def enabled():
    """Qulf yoqilishi kerakmi? Frozen build yoki KIOSK_LOCKDOWN=1."""
    if os.environ.get("KIOSK_LOCKDOWN") == "0":
        return False   # texnik xizmat: vaqtincha o'chirish imkoni
    return getattr(sys, "frozen", False) or os.environ.get("KIOSK_LOCKDOWN") == "1"


def install():
    """Hook'ni o'rnatadi (Qt event loop boshlanishidan oldin, asosiy oqimda).

    Qt'ning Windows xabarlar sikli hook xabarlarini o'zi aylantiradi —
    alohida oqim kerak emas."""
    global _hook_handle, _hook_proc_ref
    if _hook_handle is not None or not enabled():
        return False
    _hook_proc_ref = _HOOKPROC(_hook_proc)
    _hook_handle = _user32.SetWindowsHookExW(
        WH_KEYBOARD_LL, _hook_proc_ref,
        _kernel32.GetModuleHandleW(None), 0)
    if not _hook_handle:
        log.error("Klaviatura qulfini o'rnatib bo'lmadi (xato %d)",
                  _kernel32.GetLastError())
        return False
    log.info("Klaviatura qulfi yoqildi (Win/Alt+Tab/Alt+F4/Ctrl+Esc/"
             "Ctrl+Shift+Esc/kontekst-menyu bloklanadi)")
    return True


def uninstall():
    """Hook'ni olib tashlaydi (toza chiqishda)."""
    global _hook_handle, _hook_proc_ref
    if _hook_handle is not None:
        ok = _user32.UnhookWindowsHookEx(_hook_handle)
        _hook_handle = None
        # Callback referensini FAQAT unhook muvaffaqiyatli bo'lsa bo'shatamiz —
        # aks holda hali faol hook bo'shatilgan callback'ni chaqirib crash beradi.
        if ok:
            _hook_proc_ref = None
        log.info("Klaviatura qulfi o'chirildi")
