/**
 * Oflayn xarita aktivlari (PMTiles + shriftlar) proksisi — Python
 * `/api/map/<path>` ni brauzerga uzatadi. MapLibre GL shu orqali oflayn
 * vektor xaritani yuklaydi (internet kerak emas). Range (PMTiles tile'lari)
 * shaffof o'tadi. proxyMedia'ning brauzer-konteksti tekshiruvi bu yerda
 * ham qo'llanadi (Referer/Sec-Fetch), lekin xarita fetch'lari ilova
 * sahifasidan bo'lgani uchun normal o'tadi.
 */
export default defineEventHandler((event) => {
  const parts = getRouterParam(event, "path") || "";
  return proxyMedia(event, `/api/map/${parts}`);
});
