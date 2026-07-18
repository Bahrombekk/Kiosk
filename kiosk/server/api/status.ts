import type { BackendStatus } from "../utils/map";

/**
 * Poyezd holati — tezlik, harorat, joriy bekat, vagon, blok (litsenziya).
 * Asosiy sahifadagi statistika kartochkalari shu ma'lumotdan foydalanadi.
 */
export default defineEventHandler(async (event) => {
  // Jonli ma'lumot (tezlik/joriy bekat/blocked) — hech qachon keshlanmasin
  setHeader(event, "cache-control", "no-store");
  return await backendFetch<BackendStatus>("/api/status");
});
