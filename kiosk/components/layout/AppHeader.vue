<template>
  <div class="flex items-center justify-between gap-[5px]">
    <div
      class="flex items-center justify-between gap-[8px] rounded-full bg-(--surface-bg) p-[8px] shadow-[0_8px_50px_rgba(0,0,0,0.04)] mdl:w-auto mdl:gap-0"
    >
      <NuxtLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="flex h-[40px] w-[40px] items-center justify-center gap-[8px] p-2! text-[2rem] text-black no-underline mdl:h-auto mdl:w-auto mdl:p-[16px]!"
        active-class="rounded-full bg-(--brand-base) font-semibold text-white"
        v-slot="{ isActive }"
      >
        <component :is="item.icon" class="dark:text-(--icon-active)" />
        <span v-show="isActive" class="hidden text-[1.375rem] mdl:block">
          {{ $t(item.labelKey) }}
        </span>
      </NuxtLink>
    </div>

    <div class="hidden items-center gap-[24px] mdl:flex">
      <ThemeToggle />
      <div
        class="flex items-center gap-[8px] rounded-[16px] bg-(--surface-bg) p-[8px]"
      >
        <button
          v-for="locale_btn in locales"
          :key="locale_btn.code"
          class="p-[12px]"
          :class="
            locale_btn.code === locale
              ? 'rounded-[8px] bg-(--brand-base) font-semibold text-white'
              : ''
          "
          @click="setLocale(locale_btn.code)"
        >
          {{ locale_btn.name }}
        </button>
      </div>
      <p class="m-0 font-['Manrope'] text-[2.25rem] font-semibold">
        {{ props.label && $t(`appHeaderTitles.${props.label}`) }}
        <!-- `now` ref har 30s yangilanadi — avval Date.now() bir marta
             hisoblanib, soat sahifa ochilgan vaqtda qotib qolardi -->
        <NuxtTime
          v-show="!props.label"
          :datetime="now"
          :hour12="false"
          hour="numeric"
          minute="numeric"
        />
      </p>
    </div>
    <UPopover v-model:open="isPopoverOpen" arrow class="mdl:hidden">
      <UButton
        class="flex h-[52px] w-[52px] cursor-pointer items-center justify-center rounded-full bg-(--surface-bg) text-[3rem] text-(--text-primary) hover:bg-(--tertiary-bg) active:bg-(--tertiary-bg)"
        icon="lucide:menu"
      />
      <template #content>
        <ThemeToggle />
        <div
          class="flex items-center gap-[8px] rounded-[16px] bg-(--surface-bg) p-[8px]"
        >
          <button
            v-for="locale_btn in locales"
            :key="locale_btn.code"
            class="p-[12px]"
            :class="
              locale_btn.code === locale
                ? 'rounded-[8px] bg-(--brand-base) font-semibold text-white'
                : ''
            "
            @click="setLocale(locale_btn.code)"
          >
            {{ locale_btn.name }}
          </button>
        </div>
      </template>
    </UPopover>
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

const props = defineProps({
  label: {
    type: String,
  },
});

const navItems: NavItem[] = [
  { to: "/", labelKey: "appHeaderNavbar.main", icon: MainPageIcon },
  { to: "/maps", labelKey: "appHeaderNavbar.maps", icon: MapsIcon },
  { to: "/videos", labelKey: "appHeaderNavbar.videos", icon: VideosIcon },
  { to: "/books", labelKey: "appHeaderNavbar.books", icon: BooksIcon },
  { to: "/websites", labelKey: "appHeaderNavbar.websites", icon: WebsitesIcon },
];

const isPopoverOpen = ref(false);

// Jonli soat (30 soniyalik aniqlik yetarli — faqat soat:daqiqa ko'rsatiladi)
const now = ref(Date.now());
let clockTimer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  clockTimer = setInterval(() => (now.value = Date.now()), 30000);
});
onBeforeUnmount(() => clockTimer && clearInterval(clockTimer));
</script>
