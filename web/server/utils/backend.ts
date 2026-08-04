import type { H3Event } from "h3";

/**
 * Python (FastAPI) backend bilan ishlash uchun yagona nuqta.
 *
 * - `backendFetch` — JSON so'rovlar (katalog, status, route...). API kalitni
 *   `X-API-Key` header'da qo'shadi (server tomonda; brauzerga chiqmaydi).
 *   Timeout + 1 retry bor; tarmoq xatosi ichki manzilni OSHKOR QILMAYDIGAN
 *   toza 502 ga o'giriladi (avval brauzerga `ECONNREFUSED https://127.0.0.1...`
 *   trace'i chiqib ketardi).
 * - `proxyMedia` — binar fayllar (muqova, video striming, reklama) ni brauzerga
 *   oqim qilib uzatadi. Range (video seek), shartli kesh headerlari va status
 *   kodlari (206/304/416) shaffof o'tadi. Kalit endi bu yerda ham `X-API-Key`
 *   header'da — bu Nitro->backend so'rovi (brauzer emas), header bemalol
 *   ishlaydi va kalit uvicorn access-loglariga tushmaydi.
 */

function base() {
  const cfg = useRuntimeConfig();
  return {
    url: String(cfg.kioskServer || "").replace(/\/+$/, ""),
    key: String(cfg.kioskApiKey || ""),
  };
}

/** Python REST endpoint'iga autentifikatsiyalangan JSON so'rov. */
export async function backendFetch<T = unknown>(
  path: string,
  opts: Parameters<typeof $fetch<T>>[1] = {},
): Promise<T> {
  const { url, key } = base();
  const headers: Record<string, string> = {
    ...((opts?.headers as Record<string, string>) || {}),
  };
  if (key) headers["X-API-Key"] = key;
  try {
    return await $fetch<T>(path, {
      baseURL: url,
      timeout: 8000,
      retry: 1,
      ...opts,
      headers,
    });
  } catch (err: unknown) {
    // Backend'ning o'z 4xx javobini saqlaymiz (404 va h.k.), tarmoq/5xx
    // xatolarni esa toza 502 qilamiz — xabarda ichki topologiya yo'q.
    const status = (err as { response?: { status?: number } })?.response?.status;
    throw createError({
      statusCode: status && status >= 400 && status < 500 ? status : 502,
      statusMessage: "Kiosk serveri bilan aloqa yo'q",
    });
  }
}

/**
 * Python'dagi binar endpoint'ni (`/api/...`) brauzerga proksi qiladi.
 * Range va shartli headerlarni uzatadi, javob status/sarlavhalarini saqlaydi,
 * brauzer ulanishni uzsa (seek/yopish) upstream fetch ham bekor qilinadi.
 */
/**
 * Kontent o'g'irlanishiga qarshi yengil qalqon: media/matn faqat ILOVA
 * SAHIFASI ichidan (video/img/fetch) ochilsin. Yo'lovchi brauzer manzil
 * satriga `poyezd.uz/api/stream/5` deb yozib to'g'ridan yuklab olishi yoki
 * boshqa saytdan hotlink qilishi bloklanadi.
 *
 * - Sec-Fetch-Dest === "document" -> foydalanuvchi URL'ni O'ZI ochgan
 *   (media element emas) -> rad. Bu zamonaviy brauzerlar avtomatik qo'yadigan
 *   header, JS/foydalanuvchi uni soxtalashtira olmaydi.
 * - Referer boshqa hostdan bo'lsa (hotlink) -> rad.
 *
 * Halol chegara: bu OMMAVIY/oddiy yuklab olishni to'xtatadi, lekin maxsus
 * dastur (curl va sh.k.) uchun to'liq himoya emas -- raqamli kontentni 100%
 * himoya qilib bo'lmaydi (ko'rilgan/eshitilgan narsa yozib olinishi mumkin).
 */
export function assertBrowserContext(event: H3Event) {
  const dest = getRequestHeader(event, "sec-fetch-dest");
  if (dest === "document") {
    throw createError({ statusCode: 403, statusMessage: "Ruxsat yo'q" });
  }
  const referer = getRequestHeader(event, "referer");
  const host = getRequestHeader(event, "host") || "";
  if (referer && host) {
    let rHost = "";
    try {
      rHost = new URL(referer).host;
    } catch {
      rHost = "";
    }
    if (rHost && rHost !== host) {
      throw createError({ statusCode: 403, statusMessage: "Ruxsat yo'q" });
    }
  }
}

export async function proxyMedia(event: H3Event, backendPath: string) {
  assertBrowserContext(event);
  const { url, key } = base();
  const target = `${url}${backendPath}`;

  const headers: Record<string, string> = {};
  if (key) headers["X-API-Key"] = key;
  // Range (seek) + shartli kesh headerlari — busiz brauzerning If-None-Match
  // so'rovi ham har safar to'liq 200 body qaytarardi (kesh ishlamasdi).
  for (const h of ["range", "if-none-match", "if-modified-since", "if-range"]) {
    const v = getRequestHeader(event, h);
    if (v) headers[h] = v;
  }

  // Brauzer streamni uzsa (videoni yopish, boshqa joyga seek) — upstream
  // fetch'ni ham to'xtatamiz, aks holda backend faylni o'lik pipega quyaverardi.
  const ac = new AbortController();
  event.node.req.on("close", () => ac.abort());

  let upstream: Response;
  try {
    upstream = await fetch(target, { headers, signal: ac.signal });
  } catch {
    throw createError({
      statusCode: 502,
      statusMessage: "Kiosk serveri bilan aloqa yo'q (media)",
    });
  }

  setResponseStatus(event, upstream.status);
  for (const h of [
    "content-type",
    "content-length",
    "content-range",
    "accept-ranges",
    "cache-control",
    "etag",
    "last-modified",
  ]) {
    const v = upstream.headers.get(h);
    if (v) setResponseHeader(event, h, v);
  }
  // 304 (kesh yaroqli) va bo'sh javoblarda body yo'q — null qaytaramiz.
  if (upstream.status === 304 || !upstream.body) return null;
  // Nitro web ReadableStream'ni to'g'ridan-to'g'ri oqim qilib uzatadi.
  return upstream.body;
}
