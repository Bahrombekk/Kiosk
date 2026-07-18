import type { Ad } from "~/types/app";

/**
 * Reklama ma'lumoti va kiosk-parity logikasi (server/settings + /api/ads).
 *
 * - `bannerAds` — asosiy sahifadagi banner (placement banner|both, vaqt oynasi,
 *   faqat rasm — banner karuseli video o'ynatmaydi).
 * - `popupAds`  — qalqib chiquvchi/pre-roll uchun (placement popup|both; rasm
 *   ham video ham bo'lishi mumkin — AdOverlay ikkalasini ko'rsatadi).
 * - `algorithm` — ad_algorithm (media|weighted|queue|random). "media" bo'lsa
 *   popup chiqmaydi, reklama faqat kino oldidan (pre-roll) ko'rsatiladi.
 * - `intervalMs`— ad_interval_min (popup slotlari oralig'i).
 * - `ready`     — ikkala fetch tugashini kutish uchun promise (pre-roll
 *   qarori renderdan OLDIN qabul qilinishi uchun — poyga bo'lmasin).
 *
 * useFetch'larga ANIQ umumiy key berilgan — AdPopup/HomepageAds/videos-[id]
 * bir xil ma'lumotni bo'lishadi, har chaqiruv joyi alohida so'rov yubormaydi.
 *
 * Vaqt oynasi (start_time/end_time, yarim tundan o'tadigan oraliq ham) kiosk
 * bilan bir xil tekshiriladi.
 */
export function useAds() {
  const adsReq = useFetch<Ad[]>("/api/ads", {
    key: "ads",
    default: () => [],
  });
  const settingsReq = useFetch<Record<string, string>>("/api/settings", {
    key: "settings",
    default: () => ({}),
  });
  const { data: ads } = adsReq;
  const { data: settings, status: settingsStatus } = settingsReq;

  // Ikkala so'rov yakunlangunicha kutish imkoni (xato bo'lsa ham resolve —
  // default qiymatlar bilan davom etiladi).
  const ready = Promise.allSettled([adsReq, settingsReq]).then(() => undefined);

  const now = ref(new Date());
  let timer: ReturnType<typeof setInterval> | undefined;
  onMounted(() => {
    timer = setInterval(() => (now.value = new Date()), 30000);
  });
  onBeforeUnmount(() => timer && clearInterval(timer));

  const algorithm = computed(() => settings.value?.ad_algorithm || "weighted");
  const intervalMin = computed(() => {
    const n = parseInt(settings.value?.ad_interval_min || "5", 10);
    return Number.isFinite(n) && n > 0 ? n : 5;
  });
  const intervalMs = computed(() => intervalMin.value * 60 * 1000);

  function toMin(s: string | null): number | null {
    if (!s) return null;
    const m = /^(\d{1,2})[:.](\d{2})/.exec(s.trim());
    return m ? Number(m[1]) * 60 + Number(m[2]) : null;
  }
  function inWindow(ad: Ad): boolean {
    const start = toMin(ad.startTime);
    const end = toMin(ad.endTime);
    if (start == null && end == null) return true;
    const nowMin = now.value.getHours() * 60 + now.value.getMinutes();
    if (start != null && end != null) {
      return start <= end
        ? nowMin >= start && nowMin <= end
        : nowMin >= start || nowMin <= end; // yarim tundan o'tadi
    }
    if (start != null) return nowMin >= start;
    return nowMin <= (end as number);
  }

  const bannerAds = computed(() =>
    (ads.value ?? []).filter(
      (a) =>
        (a.placement === "banner" || a.placement === "both") &&
        a.mediaType !== "video" &&
        inWindow(a),
    ),
  );
  const popupAds = computed(() =>
    (ads.value ?? []).filter(
      (a) => (a.placement === "popup" || a.placement === "both") && inWindow(a),
    ),
  );

  return {
    ads,
    settings,
    settingsStatus,
    algorithm,
    intervalMin,
    intervalMs,
    bannerAds,
    popupAds,
    ready,
  };
}
