<template>
  <AdOverlay v-if="current" :key="showKey" :ad="current" @done="current = null" />
</template>

<script setup lang="ts">
import type { Ad } from "~/types/app";

/**
 * Qalqib chiquvchi reklama (kiosk services/ads.py soddalashtirilgan versiyasi):
 * har `ad_interval_min` daqiqada bitta popup|both reklama navbat bilan chiqadi,
 * `duration` soniya ko'rinib o'zi yopiladi. ad_algorithm="media" bo'lsa popup
 * chiqmaydi (reklama faqat kino oldidan — pre-roll, videos/[id].vue).
 *
 * Bu komponent default layout ichida — to'liq ekran pleyer/o'quvchi sahifalar
 * (layout: false) da umuman ulanmaydi, ya'ni playback vaqtida popup chiqmaydi.
 */
const FIRST_DELAY_MS = 20000;

const { popupAds, settingsStatus, algorithm, intervalMs } = useAds();

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
    if (algorithm.value === "media") return; // media: popup emas, pre-roll
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
