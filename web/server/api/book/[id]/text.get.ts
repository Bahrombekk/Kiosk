interface BookText {
  chapters: { title: string; text: string }[];
}

/**
 * Kitob matni — Python `/api/book/{id}/text` (boblar bilan) ni olib, TextBookReader
 * komponenti kutgan TEKIS MATN ko'rinishida qaytaradi. Komponent textUrl'ni
 * `responseType: "text"` bilan o'qiydi, shuning uchun JSON emas — matn qaytaramiz.
 */
export default defineEventHandler(async (event) => {
  // Kitob matnini ham faqat ilova sahifasidan o'qish mumkin (to'g'ridan URL
  // bilan butun matnni ko'chirib olish bloklanadi).
  assertBrowserContext(event);
  const id = Number(getRouterParam(event, "id"));
  if (!Number.isInteger(id) || id <= 0) {
    throw createError({ statusCode: 400, statusMessage: "Noto'g'ri id" });
  }
  const data = await backendFetch<BookText>(`/api/book/${id}/text`);
  const text = (data.chapters || [])
    .map((ch) => (ch.title ? `${ch.title}\n\n` : "") + (ch.text || ""))
    .join("\n\n");
  setHeader(event, "content-type", "text/plain; charset=utf-8");
  return text;
});
