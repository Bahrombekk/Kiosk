<template>
  <div>
    <!-- ============ DESKTOP HEADER (≥760px) ============ -->
    <header class="hidden items-center justify-between gap-[16px] mdl:flex">
      <!-- Logo -->
      <NuxtLink to="/" class="flex items-center gap-[12px] no-underline">
        <div
          class="grid h-[54px] w-[54px] place-items-center [clip-path:polygon(50%_0,100%_50%,50%_100%,0_50%)] bg-[linear-gradient(135deg,#c99a3c,#e8c87a)]"
        >
          <div
            class="grid h-[44px] w-[44px] place-items-center [clip-path:polygon(50%_0,100%_50%,50%_100%,0_50%)] bg-[linear-gradient(135deg,#16265e,#1445a7)]"
          >
            <span class="font-[Unbounded] text-[16px] font-bold text-(--page-bg)"
              >P</span
            >
          </div>
        </div>
        <div>
          <div class="font-[Unbounded] text-[15px] font-semibold leading-none">
            <span class="text-(--text-primary)">POYEZD</span
            ><span class="text-(--accent-gold)">.UZ</span>
          </div>
          <div
            class="mt-[3px] text-[10px] font-extrabold tracking-[.22em] text-(--text-secondary)"
          >
            YO'LDA HAMROHINGIZ
          </div>
        </div>
      </NuxtLink>

      <!-- Markaz: nav pill -->
      <nav
        class="flex items-center gap-[2px] rounded-full bg-(--surface-bg) p-[6px] shadow-(--shadow-card)"
      >
        <span class="tm-diamond mx-[6px]" />
        <NuxtLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="rounded-full px-[clamp(13px,1.6vw,22px)] py-[10px] text-[14px] font-semibold text-(--text-muted-btn) no-underline transition-colors hover:text-(--brand-base)"
          active-class="!bg-(--brand-base) !font-extrabold !text-white"
        >
          {{ $t(item.labelKey) }}
        </NuxtLink>
        <span class="tm-diamond mx-[6px]" />
      </nav>

      <!-- O'ng: til + soat -->
      <div class="flex items-center gap-[16px]">
        <div
          class="flex items-center gap-[3px] rounded-[12px] bg-(--surface-bg) p-[4px] shadow-(--shadow-card)"
        >
          <button
            v-for="l in locales"
            :key="l.code"
            class="rounded-[9px] px-[11px] py-[7px] text-[12px] font-extrabold transition-colors"
            :class="
              l.code === locale
                ? 'bg-(--brand-base) text-white'
                : 'text-(--text-muted-btn) hover:text-(--brand-base)'
            "
            @click="setLocale(l.code)"
          >
            {{ l.name }}
          </button>
        </div>
        <div class="flex items-center gap-[10px]">
          <div class="text-right">
            <div class="font-[Unbounded] text-[20px] font-semibold text-(--text-primary)">
              {{ timeStr }}
            </div>
            <div class="text-[10.5px] font-bold text-(--text-secondary)">
              {{ dateStr }}
            </div>
          </div>
          <span
            class="h-[14px] w-[14px] rounded-full bg-(--accent-gold-light) shadow-[0_0_0_3px_rgba(232,200,122,.28)]"
          />
        </div>
      </div>
    </header>

    <!-- ============ MOBIL HEADER (<760px): logo + til ============ -->
    <header class="flex items-center justify-between gap-[10px] mdl:hidden">
      <NuxtLink to="/" class="flex items-center gap-[10px] no-underline">
        <div
          class="grid h-[46px] w-[46px] place-items-center [clip-path:polygon(50%_0,100%_50%,50%_100%,0_50%)] bg-[linear-gradient(135deg,#c99a3c,#e8c87a)]"
        >
          <div
            class="grid h-[38px] w-[38px] place-items-center [clip-path:polygon(50%_0,100%_50%,50%_100%,0_50%)] bg-[linear-gradient(135deg,#16265e,#1445a7)]"
          >
            <span class="font-[Unbounded] text-[14px] font-bold text-(--page-bg)">P</span>
          </div>
        </div>
        <div class="font-[Unbounded] text-[15px] font-semibold">
          <span class="text-(--text-primary)">POYEZD</span
          ><span class="text-(--accent-gold)">.UZ</span>
        </div>
      </NuxtLink>
      <div class="flex items-center gap-[8px]">
        <div class="text-right">
          <div class="font-[Unbounded] text-[15px] font-semibold text-(--text-primary)">
            {{ timeStr }}
          </div>
        </div>
        <div
          class="flex items-center gap-[2px] rounded-[10px] bg-(--surface-bg) p-[3px] shadow-(--shadow-card)"
        >
          <button
            v-for="l in locales"
            :key="l.code"
            class="rounded-[7px] px-[8px] py-[5px] text-[11px] font-extrabold"
            :class="
              l.code === locale
                ? 'bg-(--brand-base) text-white'
                : 'text-(--text-muted-btn)'
            "
            @click="setLocale(l.code)"
          >
            {{ l.name }}
          </button>
        </div>
      </div>
    </header>

    <!-- ============ MOBIL PASTKI TAB-BAR (<760px) ============ -->
    <nav
      class="fixed inset-x-0 bottom-0 z-40 flex justify-around rounded-t-[18px] border-t-[1.5px] border-(--stroke-1) bg-[rgba(255,253,248,.97)] px-[4px] pt-[8px] pb-[10px] shadow-[0_-8px_30px_rgba(28,36,51,.08)] backdrop-blur-[12px] mdl:hidden"
    >
      <NuxtLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="flex min-h-[44px] flex-col items-center gap-[3px] no-underline"
        v-slot="{ isActive }"
      >
        <span
          class="h-[5px] w-[5px] rotate-45"
          :class="isActive ? 'bg-(--accent-gold)' : 'bg-transparent'"
        />
        <component
          :is="item.icon"
          class="h-[24px] w-[24px]"
          :class="isActive ? 'text-(--brand-base)' : 'text-(--text-secondary) opacity-45'"
        />
        <span
          class="text-[11px]"
          :class="
            isActive
              ? 'font-extrabold text-(--brand-base)'
              : 'font-semibold text-(--text-secondary)'
          "
        >
          {{ $t(item.labelKey) }}
        </span>
      </NuxtLink>
    </nav>
  </div>
</template>

<script setup lang="ts">
import type { NavItem } from "~/types/app";
import MainPageIcon from "~/assets/svg/house-floor.svg";
import MapsIcon from "~/assets/svg/map-location-pin.svg";
import VideosIcon from "~/assets/svg/clapperboard-play.svg";
import BooksIcon from "~/assets/svg/book.svg";
import WebsitesIcon from "~/assets/svg/globe-alt.svg";

const { locales, setLocale, locale } = useI18n();

const navItems: NavItem[] = [
  { to: "/", labelKey: "appHeaderNavbar.main", icon: MainPageIcon },
  { to: "/maps", labelKey: "appHeaderNavbar.maps", icon: MapsIcon },
  { to: "/videos", labelKey: "appHeaderNavbar.videos", icon: VideosIcon },
  { to: "/books", labelKey: "appHeaderNavbar.books", icon: BooksIcon },
  { to: "/websites", labelKey: "appHeaderNavbar.websites", icon: WebsitesIcon },
];

// Jonli soat + sana (30s yangilanadi). Sana oy/hafta nomlari MASSIVDAN —
// toLocaleDateString("uz-UZ") Chrome'da "M07" beradi (README talabi).
const MONTHS = [
  "yanvar", "fevral", "mart", "aprel", "may", "iyun",
  "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
];
const WEEKDAYS = [
  "Yakshanba", "Dushanba", "Seshanba", "Chorshanba",
  "Payshanba", "Juma", "Shanba",
];
const now = ref(Date.now());
let clockTimer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  clockTimer = setInterval(() => (now.value = Date.now()), 30000);
});
onBeforeUnmount(() => clockTimer && clearInterval(clockTimer));

const timeStr = computed(() => {
  const d = new Date(now.value);
  return `${String(d.getHours()).padStart(2, "0")}:${String(
    d.getMinutes(),
  ).padStart(2, "0")}`;
});
const dateStr = computed(() => {
  const d = new Date(now.value);
  return `${d.getDate()}-${MONTHS[d.getMonth()]}, ${WEEKDAYS[d.getDay()]}`;
});
</script>

<style scoped>
/* Nav pill chetidagi oltin romblar */
.tm-diamond {
  width: 7px;
  height: 7px;
  transform: rotate(45deg);
  background: var(--accent-gold);
  flex: none;
}
</style>
