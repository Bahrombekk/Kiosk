import {
  mapRoute,
  type BackendStatus,
  type BackendStop,
} from "../utils/map";

/**
 * Yo'nalish (xarita bo'limi) — Python bekatlar ro'yxati + joriy status'dan
 * frontend TrainRoute quradi (joriy bekat, o'tilgan bekatlar, koordinatalar).
 */
export default defineEventHandler(async (event) => {
  // Joriy bekat vaqt bilan o'zgaradi — keshlanmasin
  setHeader(event, "cache-control", "no-store");
  const [stops, status] = await Promise.all([
    backendFetch<BackendStop[]>("/api/route"),
    backendFetch<BackendStatus>("/api/status").catch(() => null),
  ]);
  return mapRoute(stops, status);
});
