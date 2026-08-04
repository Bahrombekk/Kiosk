// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: false },
  app: {
    head: {
      title: "Poyezd kiosk",
      meta: [{ name: "description", content: "Poyezd ko'ngilochar kioski" }],
    },
  },
  vue: {
    compilerOptions: {
      isCustomElement: (tag) => tag.startsWith("media-"),
    },
  },

  // Python (FastAPI) backend manzili va API kaliti — FAQAT server tomonda
  // (Nitro proksi) ishlatiladi, brauzerga chiqmaydi. Muhit o'zgaruvchilari
  // bilan bekor qilinadi: NUXT_KIOSK_SERVER, NUXT_KIOSK_API_KEY.
  runtimeConfig: {
    kioskServer: "https://127.0.0.1:8765",
    kioskApiKey: "",
  },

  components: [
    {
      path: "~/components",
      pathPrefix: false,
    },
  ],
  ssr: false,
  spaLoadingTemplate: "./spa-loading-template.html",
  css: [
    "~/assets/css/main.css",
    "~/assets/index.scss",
    "maplibre-gl/dist/maplibre-gl.css",
  ],
  modules: [
    "@nuxt/eslint",
    "@nuxt/icon",
    "@nuxt/image",
    "@nuxt/ui",
    "nuxt-svgo",
    "@nuxtjs/color-mode",
    "@nuxtjs/i18n",
  ],
  colorMode: {
    classSuffix: "",
  },
  i18n: {
    strategy: "no_prefix",
    // Standart til — UZ (PyQt kiosk klient bilan bir xil; O'zbekiston poyezdi)
    defaultLocale: "uz",
    locales: [
      { code: "en", name: "EN", file: "en.json" },
      { code: "ru", name: "RU", file: "ru.json" },
      { code: "uz", name: "UZ", file: "uz.json" },
    ],
    langDir: "locales/",
    detectBrowserLanguage: {
      useCookie: true,
      cookieKey: "i18n_redirected",
      redirectOn: "root",
    },
  },
});
