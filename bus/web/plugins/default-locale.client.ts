/**
 * Birinchi kirishda til DOIM o'zbekcha bo'lsin.
 *
 * Muammo: nuxt.config.ts da `defaultLocale: "uz"` turibdi, lekin yonidagi
 * `detectBrowserLanguage` uni bekor qiladi — til `navigator.language` dan
 * olinadi. Ya'ni ruscha telefonli yo'lovchi RU da, inglizchada EN da ochadi.
 *
 * Nega `detectBrowserLanguage` ni butunlay o'chirmadik: @nuxtjs/i18n da
 * tanlangan tilni eslab qolish (`i18n_redirected` cookie) AYNAN shu bo'limga
 * bog'langan. O'chirsak — yo'lovchi RU ga o'tib, keyingi sahifaga bosganda
 * yana UZ ga qaytib ketardi.
 *
 * Yechim: modulning o'z eslab qolishini saqlaymiz, faqat ENG BIRINCHI
 * tashrifni UZ ga majburlaymiz. Buning uchun alohida belgi-cookie ishlatamiz —
 * `i18n_redirected` ni tekshirish ishonchsiz, chunki detectBrowserLanguage
 * plaginlardan OLDIN ishlab, uni allaqachon to'ldirib qo'ygan bo'ladi.
 */
export default defineNuxtPlugin(async () => {
  const seen = useCookie<string | null>("lang_initialized", {
    maxAge: 60 * 60 * 24 * 365,
    sameSite: "lax",
    path: "/",
  });

  if (seen.value) return; // avval kirgan — tanlovi hurmat qilinadi
  seen.value = "1";

  const { setLocale, locale } = useNuxtApp().$i18n;
  if (locale.value !== "uz") await setLocale("uz");
});
