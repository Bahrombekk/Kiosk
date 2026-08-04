# Dizayn havolalari

Bu papkada **dizayn manbalari** turadi — ishlaydigan kod emas, faqat namuna
(reference). Kodni o'zgartirganda vizual mos kelishini shu fayllardan tekshiring.

| Fayl | Nima |
|---|---|
| `kiosk-cloud-admin.dc.html` | [`cloud/`](../../cloud/) bulut admin panelining dizayn prototipi |
| `support.js` | prototip runtime'i (dizayn vositasi generatsiya qilgan — tahrirlanmaydi) |
| `cloud-admin-upload-modal.png` | "Kontent yuklash" modali skrinshoti |

## Prototipni ko'rish

`kiosk-cloud-admin.dc.html` ni brauzerda ochish yetarli (`support.js` yonida
turishi shart). Ichida demo ma'lumot bor — barcha ekranlar bosiladi.

Prototipda **"Texnik reja"** sahifasi ham bor: bulut relay, heartbeat, kontent
tarqatish (Range + sha256), desired-state manifest, statistika/loglar va
xavfsizlik bo'yicha 6 qadam. `cloud/` va `server/cloud_client.py` aynan shu reja
bo'yicha yozilgan — batafsil [`cloud/README.md`](../../cloud/README.md).

> Prototip `{{ }}` bog'lamalari bilan ishlaydigan **maket**: ma'lumot fayl
> ichiga qattiq yozilgan. Haqiqiy UI — `cloud/static/`.
