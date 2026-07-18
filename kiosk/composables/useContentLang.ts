/**
 * Kontent til filtri — user kiosk bilan bir xil qoida (user/core/i18n.py):
 *   ko'rinsin = (lang bo'sh/null) YOKI (lang === tanlangan til)
 *
 * Ya'ni tilsiz (barcha tillar) kontent doim ko'rinadi; tilli kontent faqat
 * joriy interfeys tili bilan mos bo'lsa. `lang_group` ishlatilmaydi — dedup
 * shu til filtri orqali amalga oshadi (kiosk ham shunday).
 */
export function useContentLang() {
  const { locale } = useI18n();

  const matchesLang = (item: { lang?: string | null }) => {
    const lang = (item.lang || "").trim();
    return !lang || lang === locale.value;
  };

  /** Berilgan ro'yxatni joriy tilga ko'ra filtrlaydi (reaktiv). */
  function filterByLang<T extends { lang?: string | null }>(
    items: MaybeRefOrGetter<T[] | undefined | null>,
  ) {
    return computed(() => (toValue(items) ?? []).filter(matchesLang));
  }

  return { locale, matchesLang, filterByLang };
}
