import { BOOK_TYPES, mapBook, type BackendContent } from "../utils/map";

/**
 * Kitoblar bo'limi — Python `/api/content` dan kitob/audiokitob turdagi
 * kontentni olib frontend Book[] shakliga o'giradi. Bir yozuv matn VA audio
 * bo'lishi mumkin (contentModes mapping'da aniqlanadi).
 */
export default defineEventHandler(async () => {
  const content = await backendFetch<BackendContent[]>("/api/content");
  return content.filter((c) => BOOK_TYPES.includes(c.type)).map(mapBook);
});
