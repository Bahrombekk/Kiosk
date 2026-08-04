"""
netpin.py — Sertifikat "pinning" bilan HTTP (requests ustida).

TLS yoqilgan (https) va trust.json'da fingerprint bo'lsa, har bir ulanish
serverning AYNAN o'sha sertifikatiga pin qilinadi: boshqa sertifikatga
(o'rtadagi MITM hujumchiga) ulanmaydi. Hostname tekshiruvi o'chiriladi —
ishonch fingerprint orqali, IP o'zgarsa ham buzilmaydi.

http (eski rejim) bo'lsa — oddiy requests (pin yo'q).

DIQQAT (thread xavfsizligi): requests.Session thread-safe emas, shuning uchun
har CHAQIRUVCHI THREAD o'zining bitta UZOQ YASHOVCHI Session'iga ega
(`thread_session()`, threading.local). Avvalgi "har chaqiruvda yangi Session"
yondashuvi parallel QThread'larda Session/PoolManager obyektlarining tinimsiz
yaratilib-GC qilinishiga olib kelar va native crash (access violation,
crash.log) manbai edi — endi sessiyalar qayta ishlatiladi."""
import ssl
import logging
import threading

import requests
from requests.adapters import HTTPAdapter

from core import config
from core import trust

log = logging.getLogger(__name__)

try:
    from urllib3.poolmanager import PoolManager
except Exception:                       # noqa: BLE001
    PoolManager = None
    log.error("urllib3.PoolManager import bo'lmadi — TLS pinning ishlamaydi")

# verify=False bilan ishlaganda (fingerprint pinning) urllib3 har so'rovda
# InsecureRequestWarning chiqaradi — bu yerda u ATAYLAB (ishonch fingerprint
# orqali), shuning uchun ogohlantirishni jim qilamiz (log to'lib ketmasin).
try:
    from urllib3.exceptions import InsecureRequestWarning
    import urllib3
    urllib3.disable_warnings(InsecureRequestWarning)
except Exception:                       # noqa: BLE001
    pass


class _PinAdapter(HTTPAdapter):
    """Serverning SHA-256 fingerprint'iga pin qiladigan requests adapteri."""

    def __init__(self, fingerprint, **kw):
        self._fp = fingerprint
        super().__init__(**kw)

    def init_poolmanager(self, connections, maxsize, block=False, **kw):
        ctx = ssl.create_default_context()
        # Ishonch fingerprint orqali — CA zanjiri/hostname emas (self-signed,
        # IP bilan ulanamiz). urllib3 assert_fingerprint'ni baribir tekshiradi.
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize, block=block,
            ssl_context=ctx, assert_fingerprint=self._fp,
            assert_hostname=False, **kw)


def _pin_fp():
    return trust.cert_fingerprint() if config.is_tls() else None


def session():
    """YANGI pinned requests.Session (https bo'lsa). Hayot tsiklini chaqiruvchi
    boshqaradi (`with netpin.session() as s: ...`). Ko'p martalik oddiy
    so'rovlar uchun `thread_session()` / `get()` / `post()` afzal — ular
    sessiyani qayta ishlatadi."""
    s = requests.Session()
    fp = _pin_fp()
    if config.is_tls():
        # TLS yoqilgan — pinsiz ulanish QILMAYMIZ (fail-closed). Pin materiali
        # (fingerprint yoki urllib3) yo'q bo'lsa MITM'ga ochiq qolmaslik uchun
        # rad etamiz. ws_client ham xuddi shunday fail-closed ishlaydi.
        if not fp or PoolManager is None:
            # requests.exceptions.SSLError — RequestException merosxo'ri, shuning
            # uchun api.py dagi mavjud xato ushlovchilar buni tutadi (kesh fallback).
            raise requests.exceptions.SSLError(
                "TLS pinning materiali yo'q (fingerprint/urllib3) — ulanish rad etildi")
        s.mount("https://", _PinAdapter(fp))
        # MUHIM: verify=False — aks holda requests har ulanishga CERT_REQUIRED
        # (CA zanjiri tekshiruvi) ni majburlab, adapterning CERT_NONE+fingerprint
        # kontekstini bekor qiladi va self-signed sertifikat rad etiladi.
        # Xavfsizlik YO'QOLMAYDI: ishonch assert_fingerprint orqali — boshqa
        # sertifikatga (MITM) ulanmaydi (soxta fingerprint -> SSLError).
        s.verify = False
    return s


# Har thread uchun bitta sessiya (threading.local). Thread tugasa sessiya u
# bilan birga yig'iladi; fingerprint (trust.json rotatsiyasi) o'zgarsa qayta
# quriladi.
_local = threading.local()


def thread_session():
    """Joriy thread uchun KESHLANGAN uzoq yashovchi pinned Session.

    YOPMANG (`with` bilan o'ramang) — sessiya thread hayoti davomida qayta
    ishlatiladi. stream=True javoblarda faqat javobni yoping
    (`with s.get(url, stream=True) as r: ...`) — sessiya ochiq qolaveradi."""
    fp = _pin_fp()
    s = getattr(_local, "session", None)
    if s is not None and getattr(_local, "fp", None) == fp:
        return s
    if s is not None:
        try:
            s.close()   # sert rotatsiyasi — eski pin bilan ulanishlar yopiladi
        except Exception:                    # noqa: BLE001
            pass
    s = session()
    _local.session = s
    _local.fp = fp
    return s


def get(url, **kw):
    """Pinned GET (per-thread sessiya orqali). stream=True bo'lsa javobni
    o'zingiz yoping — sessiya ochiq qoladi."""
    return thread_session().get(url, **kw)


def post(url, **kw):
    """Pinned POST (per-thread sessiya orqali)."""
    return thread_session().post(url, **kw)
