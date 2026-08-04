import { mapWebsite, type BackendSite } from "../utils/map";

/**
 * Saytlar bo'limi — Python `/api/sites` dan olib frontend Website[] shakliga
 * o'giradi.
 */
export default defineEventHandler(async () => {
  const sites = await backendFetch<BackendSite[]>("/api/sites");
  return sites.map(mapWebsite);
});
