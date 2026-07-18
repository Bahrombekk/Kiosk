<template>
  <div
    class="fixed inset-0 z-[200] flex items-center justify-center bg-black/85 p-[24px]"
  >
    <div class="relative max-h-[90vh] max-w-[90vw]">
      <!-- mediaType bo'yicha tarmoqlanish: video reklama <video> bilan
           o'ynaydi (@ended -> done); avval doim <img> chiqarilib, video
           reklamalar singan-rasm bo'lib qolar edi -->
      <video
        v-if="isVideo"
        :src="ad.ad_image_link"
        autoplay
        muted
        playsinline
        class="max-h-[90vh] max-w-[90vw] rounded-[16px] object-contain"
        @ended="emit('done')"
        @error="emit('done')"
      />
      <img
        v-else
        :src="ad.ad_image_link"
        :alt="'ad-' + ad.id"
        class="max-h-[90vh] max-w-[90vw] rounded-[16px] object-contain"
        @error="emit('done')"
      />
      <div
        class="absolute top-[12px] right-[12px] rounded-full bg-black/60 px-[14px] py-[6px] text-[0.95rem] font-semibold text-white backdrop-blur-sm"
      >
        {{ remaining }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Ad } from "~/types/app";

const props = defineProps<{ ad: Ad }>();
const emit = defineEmits<{ done: [] }>();

const isVideo = computed(() => props.ad.mediaType === "video");

const total = () =>
  props.ad.duration && props.ad.duration > 0 ? props.ad.duration : 10;
const remaining = ref(total());
let tick: ReturnType<typeof setInterval> | undefined;
let doneTimer: ReturnType<typeof setTimeout> | undefined;

onMounted(() => {
  remaining.value = total();
  tick = setInterval(() => {
    remaining.value = Math.max(0, remaining.value - 1);
  }, 1000);
  // Rasm: duration tugagach yopiladi. Video: asosan @ended yopadi, taymer
  // zaxira (osilib qolgan/yuklanmagan video abadiy qolib ketmasin) — video
  // davomiyligidan uzunroq bo'lishi uchun +15s.
  const ms = (total() + (isVideo.value ? 15 : 0)) * 1000;
  doneTimer = setTimeout(() => emit("done"), ms);
});

onBeforeUnmount(() => {
  if (tick) clearInterval(tick);
  if (doneTimer) clearTimeout(doneTimer);
});
</script>
