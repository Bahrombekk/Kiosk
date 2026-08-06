<!-- HomepageAds.vue — Reklama banner sloti (§10).
     aspect 4:1 (desktop) / 4:3 (<760px); rasm center/contain + orqada MILLIY
     NAQSHLI fon (tungi ko'k + oltin romb) — rasm slotni to'ldirmaganда yon
     bo'shliq xira blur o'rniga naqsh bilan to'ladi (avtobus dizayni bilan uyg'un);
     REKLAMA badge, ‹ › tugmalar, nuqta indikator, 7s avtomatik almashish. -->
<template>
  <div
    v-if="bannerAds.length"
    class="relative overflow-hidden rounded-[24px] bg-(--dark-card)"
    style="box-shadow: 0 8px 30px rgba(28, 36, 51, 0.08)"
  >
    <div class="tm-frame">
      <!-- Milliy naqshli fon (yon bo'shliqni to'ldiradi, blur o'rniga) -->
      <div class="tm-ad-pattern" />
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

// Proof-of-play: banner ko'rsatilgani yoziladi, LEKIN har reklama uchun ko'pi
// bilan intervalда bir marta (banner har 7s aylanadi — har aylanishni sanasak
// hisob juda shishib ketardi; kiosk bilan bir xil mantiq).
const bannerLogged = new Map<number, number>();
function logBanner(ad?: Ad) {
  if (!ad) return;
  // Faqat sahifa ko'rinib turganda sanaymiz — tab orqada (yashirin) bo'lsa
  // banner aylanaversa ham "ko'rildi" hisoblanmaydi.
  if (typeof document !== "undefined" && document.hidden) return;
  const intervalMs = Math.max(60000, (Number(ad.intervalMin) || 0) * 60000);
  const now = Date.now();
  if (now - (bannerLogged.get(ad.id) ?? 0) < intervalMs) return;
  bannerLogged.set(ad.id, now);
  track("ad_play", {
    ad_id: ad.id,
    title: ad.title,
    media_type: ad.mediaType,
    placement: "banner",
  });
}
watch(idx, () => logBanner(bannerAds.value[idx.value]));
watch(
  bannerAds,
  (list) => {
    idx.value = 0;
    if (list.length) {
      logBanner(list[0]);
      startTimer();
    } else {
      stopTimer(); // ro'yxat bo'shaса — eski 7s taymer NaN idx bilan ishlab qolmasin
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
/* Milliy naqshli fon — tungi ko'k gradient + oltin romb naqsh (SVG data-URI).
   Reklama rasmi contain bo'lgani uchun to'ldirmaган yon bo'shliqni to'ldiradi. */
.tm-ad-pattern {
  position: absolute;
  inset: 0;
  background-color: #0e2150;
  background-image:
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='46' height='46'%3E%3Cpath d='M23 3 43 23 23 43 3 23Z' fill='none' stroke='rgba(232,200,122,0.16)' stroke-width='1.4'/%3E%3Cpath d='M23 15 31 23 23 31 15 23Z' fill='rgba(232,200,122,0.09)'/%3E%3C/svg%3E"),
    radial-gradient(circle at 12% 30%, rgba(255,255,255,0.06), transparent 60%),
    linear-gradient(135deg, #0e2150 0%, #1a3a86 55%, #0a1636 100%);
  background-repeat: repeat, no-repeat, no-repeat;
  background-size: 46px 46px, cover, cover;
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
