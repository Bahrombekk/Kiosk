import { mapAd, type BackendAd } from "../utils/map";

/**
 * Reklamalar — Python `/api/ads` dan barcha faol reklamalarni (rasm VA video)
 * olib frontend Ad[] shakliga o'giradi (placement bilan). Frontend joylashuv
 * bo'yicha ajratadi: banner (HomepageAds, faqat rasm) va popup/pre-roll
 * (AdOverlay — mediaType bo'yicha rasm yoki video chiqaradi). Kiosk parity.
 */
export default defineEventHandler(async () => {
  const ads = await backendFetch<BackendAd[]>("/api/ads");
  return ads.map(mapAd);
});
