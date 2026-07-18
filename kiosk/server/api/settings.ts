/**
 * Sozlamalar — Python `/api/settings` javobidan faqat vebga kerakli,
 * maxfiy bo'lmagan kalitlarni o'tkazadi (OQ RO'YXAT).
 *
 * Muhim: backend endpoint API kalit bilan yopiq, bu marshrut esa LAN'dagi
 * istalgan brauzerga ochiq. Butun javobni filtrsiz uzatish sirlarni
 * (masalan, kioskning chiqish PIN xeshini) tarmoqqa ochib qo'yadi —
 * shu sabab bu yerda alohida, tor oq ro'yxat qo'llanadi.
 */
const PUBLIC_KEYS = ["ad_interval_min", "ad_algorithm", "default_theme"];

export default defineEventHandler(async () => {
  const all = await backendFetch<Record<string, string>>("/api/settings");
  const out: Record<string, string> = {};
  for (const k of PUBLIC_KEYS) {
    if (all && k in all) out[k] = all[k];
  }
  return out;
});
