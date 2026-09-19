/**
 * VAQTINCHALIK: kontent importi uchun proksi (`/api/import/...`).
 *
 * Nega bor: avtobus qurilmasi kontentni faqat bulutdan oladi va tashqariga
 * hech qanday yozuv endpointi ochmaydi. Ommaviy serverga BIRINCHI marta
 * ma'lumot solish uchun boshqa yo'l qolmadi (bulut tailnet ichida).
 *
 * XAVFSIZLIK — ikki qulf:
 *   1. `NUXT_KIOSK_IMPORT_TOKEN` berilmasa bu marshrut 404 qaytaradi, ya'ni
 *      standart holda BUTUNLAY O'CHIQ.
 *   2. Berilgan bo'lsa ham har so'rovda `x-import-token` header tekshiriladi.
 * Backend tomonda uchinchi qulf bor: `KIOSK_IMPORT=1` bo'lmasa u ham 404.
 *
 * Import tugagach ikkala o'zgaruvchini ham olib tashlang va qayta deploy qiling.
 */
export default defineEventHandler(async (event) => {
  const cfg = useRuntimeConfig();
  const expected = String(cfg.kioskImportToken || "");

  // O'chiq holat — mavjud emasdek ko'rinadi (borligini ham oshkor qilmaymiz).
  if (!expected) throw createError({ statusCode: 404, statusMessage: "Not Found" });

  const supplied = getHeader(event, "x-import-token") || "";
  // Uzunlik farq qilsa ham bir xil javob — nima noto'g'ri ekanini aytmaymiz.
  if (supplied !== expected) {
    throw createError({ statusCode: 404, statusMessage: "Not Found" });
  }

  const backend = String(cfg.kioskServer || "").replace(/\/+$/, "");
  const key = String(cfg.kioskApiKey || "");

  // `event.path` = "/api/import/blob?kind=media&name=..." — query bilan birga
  // o'zgarishsiz uzatamiz.
  const target = backend + event.path;

  // proxyRequest tanani OQIM bilan uzatadi — gigabaytlik fayl xotiraga
  // yig'ilmaydi (oddiy readBody() buni qila olmasdi).
  return proxyRequest(event, target, {
    headers: { "X-API-Key": key },
    // Katta fayl uzoq yuklanadi; Nitro standart timeout'i yetmaydi.
    fetchOptions: { timeout: 0 as unknown as number },
  });
});
