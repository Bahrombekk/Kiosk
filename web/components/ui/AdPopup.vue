<template>
  <AdOverlay v-if="current" :key="showKey" :ad="current" context="popup" @done="current = null" />
</template>

<script setup lang="ts">
import type { Ad } from "~/types/app";

/**
 * Qalqib chiquvchi reklama (kiosk services/ads.py soddalashtirilgan versiyasi):
 * har `ad_interval_min` daqiqada 'popup' joylashuvли reklama navbat bilan
 * chiqadi, `duration` soniya ko'rinib o'zi yopiladi. 'media' joylashuvли
 * reklama esa kino oldidan (pre-roll, videos/[id].vue) alohida ko'rsatiladi.
 *
 * Bu komponent default layout ichida — to'liq ekran pleyer/o'quvchi sahifalar
 * (layout: false) da umuman ulanmaydi, ya'ni playback vaqtida popup chiqmaydi.
 */
const FIRST_DELAY_MS = 20000;

const { popupAds, settingsStatus, intervalMs } = useAds();

const current = ref<Ad | null>(null);
const showKey = ref(0);
let idx = 0;
let started = false;
let firstTimer: ReturnType<typeof setTimeout> | undefined;
let slotTimer: ReturnType<typeof setInterval> | undefined;

function showNext() {
  const list = popupAds.value;
  if (!list.length) return;
  current.value = list[idx % list.length] ?? null;
  idx++;
  showKey.value++;
}

// Sozlamalar fetch'i YAKUNLANGACH boshlaymiz — muvaffaqiyat ham, xato ham
// (xatoda default interval/algoritm bilan). Avval faqat bo'sh bo'lmagan
// settings kutilardi: fetch xato bersa popup umuman boshlanmay qolardi.
watch(
  settingsStatus,
  (st) => {
    if (started || st === "pending" || st === "idle") return;
    started = true;
    // Popup faqat 'popup' joylashuvли reklama bo'lsa chiqadi (popupAds bo'sh
    // bo'lsa showNext hech narsa qilmaydi). 'media' endi alohida — pre-roll.
    firstTimer = setTimeout(() => {
      showNext();
      slotTimer = setInterval(showNext, intervalMs.value);
    }, FIRST_DELAY_MS);
  },
  { immediate: true },
);

// Admin intervalni o'zgartirsa (SPA kunlab ishlaydi) taymerni qayta quramiz
watch(intervalMs, (ms) => {
  if (!slotTimer) return;
  clearInterval(slotTimer);
  slotTimer = setInterval(showNext, ms);
});

onBeforeUnmount(() => {
  if (firstTimer) clearTimeout(firstTimer);
  if (slotTimer) clearInterval(slotTimer);
});
</script>
