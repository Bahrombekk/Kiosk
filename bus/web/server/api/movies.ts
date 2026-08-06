import { VIDEO_TYPES, mapVideo, type BackendContent } from "../utils/map";

/**
 * Videolar bo'limi — Python `/api/content` dan video turdagi kontentni
 * (kino, multfilm, musiqa) olib frontend Video[] shakliga o'giradi.
 */
export default defineEventHandler(async () => {
  const content = await backendFetch<BackendContent[]>("/api/content");
  return content.filter((c) => VIDEO_TYPES.includes(c.type)).map(mapVideo);
});
