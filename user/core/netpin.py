"""
netpin.py — Sertifikat "pinning" bilan HTTP (requests ustida).

TLS yoqilgan (https) va trust.json'da fingerprint bo'lsa, har bir ulanish
serverning AYNAN o'sha sertifikatiga pin qilinadi: boshqa sertifikatga
(o'rtadagi MITM hujumchiga) ulanmaydi. Hostname tekshiruvi o'chiriladi —
ishonch fingerprint orqali, IP o'zgarsa ham buzilmaydi.

http (eski rejim) bo'lsa — oddiy requests (pin yo'q).

DIQQAT: har chaqiruvда YANGI Session — bir nechta QThread parallel ishlatsa
ham xavfsiz (requests.Session thread-safe emas; api.py shu sababli Session'dan
qochadi)."""
import ssl
import logging

import requests
from requests.adapters import HTTPAdapter

from core import config
from core import trust

log = logging.getLogger(__name__)

try:
    from urllib3.poolmanager import PoolManager
except Exception:                       # noqa: BLE001
    PoolManager = None

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
    """Pinned requests.Session (https bo'lsa). Foydalangach yoping
    (`with netpin.session() as s: ...`)."""
    s = requests.Session()
    fp = _pin_fp()
    if fp and PoolManager is not None:
        s.mount("https://", _PinAdapter(fp))
        # MUHIM: verify=False — aks holda requests har ulanishga CERT_REQUIRED
        # (CA zanjiri tekshiruvi) ni majburlab, adapterning CERT_NONE+fingerprint
        # kontekstini bekor qiladi va self-signed sertifikat rad etiladi.
        # Xavfsizlik YO'QOLMAYDI: ishonch assert_fingerprint orqali — boshqa
        # sertifikatga (MITM) ulanmaydi (soxta fingerprint -> SSLError).
        s.verify = False
    return s


def get(url, **kw):
    """Pinned GET. stream=True KERAK bo'lsa session()'ni o'zingiz boshqaring
    (javob o'qilgunicha session ochiq tursin)."""
    with session() as s:
        return s.get(url, **kw)


def post(url, **kw):
    """Pinned POST."""
    with session() as s:
        return s.post(url, **kw)
