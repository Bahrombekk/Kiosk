/**
 * GET /api/hero — asosiy sahifa banneri (hero) rasmi.
 *
 * Rasm BULUTDAN almashtirilishi mumkin: markaziy panelда yuklangan fayl poyezd
 * serveriga tushadi va u `/api/branding/hero` da beradi.
 *
 * MUHIM: brending bo'lmasa bu endpoint **404 qaytarmaydi**, balki ilovadagi
 * standart rasmga yo'naltiradi — bosh sahifa hech qachon bannersiz qolmaydi.
 *
 * Diqqat: `proxyMedia` backendning 404'ini SHAFFOF o'tkazadi (xato TASHLAMAYDI,
 * javob statusini o'zi qo'yib, 404 JSON tanasini uzatadi). Shu sababli faqat
 * `try/catch` yetarli emas — javob statusini o'zimiz tekshiramiz.
 */
import type { H3Event } from "h3";

const FALLBACK = "/dashboard-hero.png";

/** proxyMedia qo'ygan media sarlavhalarini tozalab, standart rasmga yo'naltirish. */
function toFallback(event: H3Event) {
  // Media javobidan qolgan sarlavhalar redirectni buzmasin (masalan 404 JSON'ning
  // content-length: 26 — brauzer tanani noto'g'ri o'qib qolardi).
  for (const h of [
    "content-type",
    "content-length",
    "content-range",
    "accept-ranges",
    "etag",
    "last-modified",
  ]) {
    removeResponseHeader(event, h);
  }
  setResponseHeader(event, "cache-control", "no-store");
  return sendRedirect(event, FALLBACK, 302);
}

export default defineEventHandler(async (event) => {
  try {
    const body = await proxyMedia(event, "/api/branding/hero");
    if (getResponseStatus(event) >= 400) {
      // 404 = bulutdan banner qo'yilmagan (odatiy holat). Foydalanilmagan
      // oqimni yopamiz, aks holda backend soketi ochiq qolib ketadi.
      const stream = body as ReadableStream | null;
      if (stream && typeof stream.cancel === "function") {
        await stream.cancel().catch(() => {});
      }
      return toFallback(event);
    }
    // Backend `max-age=3600` beradi — banner bulutdan almashtirilганда brauzer
    // 1 soatgacha ESKISINI ko'rsatib turardi. 60 s ga qisqartiramiz: yangi
    // banner deyarli darhol ko'rinadi, lekin har navigatsiyada qayta yuklanmaydi
    // (backend `If-None-Match`ни qo'llamaydi, ya'ni 304 bo'lmaydi — `no-cache`
    // qo'ysak har safar to'liq rasm qaytadi).
    setResponseHeader(event, "cache-control", "public, max-age=60");
    return body;
  } catch (err: unknown) {
    const code = (err as { statusCode?: number })?.statusCode;
    // 403 = hotlink himoyasi (assertBrowserContext) — uni buzmaymiz.
    if (code === 403) throw err;
    if (code && code !== 404) console.warn("[hero] backend xatosi:", code);
    return toFallback(event);
  }
});
