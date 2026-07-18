/**
 * Veb statistikasini ishga tushiradi (faqat brauzer tomonida) va sahifa
 * o'tishlarini (screen_view) avtomatik qayd etadi. Boshqa eventlar
 * (content_open, lang_change, ad_play, site_qr) tegishli komponentlarda
 * useStats().track(...) orqali yuboriladi.
 */
// Nuxt route nomini kiosk statistikasidagi "screen" bilan moslash
// (admin SCREEN_LABELS: home/map/videos/books/sites).
const ROUTE_SCREEN: Record<string, string> = {
  index: "home",
  maps: "map",
  "videos-index": "videos",
  "videos-id": "videos",
  "books-index": "books",
  "books-id": "books",
  websites: "sites",
};

export default defineNuxtPlugin((nuxtApp) => {
  const { track, initStats } = useStats();
  initStats();

  const router = useRouter();
  router.afterEach((to) => {
    const name = String(to.name || "");
    const screen = ROUTE_SCREEN[name];
    if (screen) track("screen_view", { screen });
  });

  // i18n til almashishi -> lang_change
  const i18n = nuxtApp.$i18n as { locale?: { value: string } } | undefined;
  if (i18n?.locale) {
    watch(
      () => i18n.locale!.value,
      (lang) => track("lang_change", { lang }),
    );
  }
});
