<!-- HomepageAds.vue — Reklama banner sloti (§10).
     aspect 4:1 (desktop) / 4:3 (<760px); rasm center/contain + orqada blur-fon;
     REKLAMA badge, ‹ › tugmalar, nuqta indikator, 7s avtomatik almashish. -->
<template>
  <div
    v-if="bannerAds.length"
    class="relative overflow-hidden rounded-[24px] bg-(--dark-card)"
    style="box-shadow: 0 8px 30px rgba(28, 36, 51, 0.08)"
  >
    <div class="tm-frame">
      <!-- Orqa blur nusxa -->
      <div
        class="absolute inset-[-30px]"
        :style="{
          background: `url('${current.ad_image_link}') center/cover no-repeat`,
          filter: 'blur(26px) brightness(.8)',
          transform: 'scale(1.15)',
        }"
      />
      <!-- Old rasm (contain) -->
      <div
        class="absolute inset-0"
        :style="{
          background: `url('${current.ad_image_link}') center/contain no-repeat`,
        }"
        role="img"
        :aria-label="current.title"
      />
    </div>

    <!-- Badge -->
    <div
      class="absolute left-[14px] top-[14px] rounded-full bg-[rgba(201,154,60,.95)] px-[11px] py-[4px] text-[10px] font-extrabold tracking-[.1em] text-(--text-on-gold)"
    >
      {{ $t("adBadge") }}
    </div>

    <!-- ‹ › -->
    <template v-if="bannerAds.length > 1">
      <button
        class="tm-arrow left-[14px]"
        aria-label="prev"
        @click="prev"
      >
        ‹
      </button>
      <button
        class="tm-arrow right-[14px]"
        aria-label="next"
        @click="next"
      >
        ›
      </button>
    </template>

    <!-- Nuqtalar -->
    <div
      v-if="bannerAds.length > 1"
      class="absolute inset-x-0 bottom-[12px] flex justify-center gap-[7px]"
    >
      <button
        v-for="(a, i) in bannerAds"
        :key="a.id"
        class="h-[8px] rounded-full transition-[width] duration-[250ms]"
        :class="i === idx ? 'w-[22px] bg-(--accent-gold)' : 'w-[8px] bg-[rgba(255,255,255,.55)]'"
        @click="idx = i"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Ad } from "~/types/app";

const { bannerAds } = useAds();
const { track } = useStats();

const idx = ref(0);
const current = computed(() => bannerAds.value[idx.value] ?? bannerAds.value[0] ?? {});

let timer: ReturnType<typeof setInterval> | undefined;
function startTimer() {
  stopTimer();
  if (bannerAds.value.length > 1) {
    timer = setInterval(next, 7000); // §10: 7s rotatsiya
  }
}
function stopTimer() {
  if (timer) clearInterval(timer);
}
function next() {
  idx.value = (idx.value + 1) % bannerAds.value.length;
}
function prev() {
  idx.value = (idx.value - 1 + bannerAds.value.length) % bannerAds.value.length;
}

// Proof-of-play: har banner ko'rinishida ad_play (kiosk bilan parity)
function logBanner(ad?: Ad) {
  if (ad) {
    track("ad_play", {
      ad_id: ad.id,
      title: ad.title,
      media_type: ad.mediaType,
      placement: "banner",
    });
  }
}
watch(idx, () => logBanner(bannerAds.value[idx.value]));
watch(
  bannerAds,
  (list) => {
    idx.value = 0;
    if (list.length) {
      logBanner(list[0]);
      startTimer();
    }
  },
  { immediate: true },
);
onMounted(startTimer);
onBeforeUnmount(stopTimer);
</script>

<style scoped>
.tm-frame {
  position: relative;
  aspect-ratio: 4 / 1;
}
@media (max-width: 759.98px) {
  .tm-frame {
    aspect-ratio: 4 / 3;
  }
}
.tm-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.75);
  color: #1c2433;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  transition: background 0.15s;
}
.tm-arrow:hover {
  background: #fff;
}
</style>
