<!-- HomeRecommend.vue — "Tavsiya etamiz" bo'lim sarlavhasi (§11) + video
     poster kartalari to'ri (§12). Kartalar /videos/:id ga o'tadi. -->
<template>
  <div class="flex flex-col gap-[16px]">
    <!-- §11 sarlavha: oltin romb + Unbounded 19px + zigzag + "Barchasi →" -->
    <div class="flex items-center gap-[14px]">
      <div class="tm-diamond3">
        <div class="tm-diamond3-mid"><div class="tm-diamond3-core" /></div>
      </div>
      <div class="font-[Unbounded] text-[19px] font-semibold text-(--text-primary)">
        {{ $t("weRecommend") }}
      </div>
      <div class="tm-zigzag h-[8px] flex-1" />
      <NuxtLink
        to="/videos"
        class="border-0 bg-none text-[13px] font-extrabold text-(--brand-base) no-underline"
      >
        {{ $t("categories.all") }} →
      </NuxtLink>
    </div>

    <!-- §12 video kartalar -->
    <div
      class="grid gap-[16px]"
      style="grid-template-columns: repeat(auto-fill, minmax(min(235px, 100%), 1fr))"
    >
      <NuxtLink
        v-for="(v, i) in movies"
        :key="v.id"
        :to="`/videos/${v.id}`"
        class="tm-vcard block overflow-hidden rounded-[20px] bg-(--surface-bg) no-underline shadow-(--shadow-card)"
      >
        <div class="relative h-[124px]" :style="{ background: gradFor(i) }">
          <img
            v-if="v.image?.original"
            :src="v.image.original"
            :alt="v.name"
            loading="lazy"
            class="absolute inset-0 h-full w-full object-cover"
          />
          <!-- girih tekstura -->
          <div
            class="pointer-events-none absolute inset-0"
            style="
              background: repeating-conic-gradient(from 45deg, rgba(255, 255, 255, 0.09) 0 25%, transparent 0 50%);
              background-size: 34px 34px;
            "
          />
          <!-- play tugma -->
          <div class="absolute inset-0 z-1 flex items-center justify-center">
            <div
              class="flex h-[46px] w-[46px] items-center justify-center rounded-full border border-[rgba(255,255,255,.6)] bg-[rgba(255,255,255,.55)] text-[15px] text-(--text-primary) backdrop-blur-[5px]"
            >
              ▶
            </div>
          </div>
          <div
            v-if="v.isRecommended"
            class="absolute left-[10px] top-[10px] rounded-full bg-(--accent-gold) px-[9px] py-[3px] text-[10px] font-extrabold tracking-[.06em] text-(--text-on-gold)"
          >
            {{ $t("recommendedBadge") }}
          </div>
        </div>
        <div class="px-[16px] py-[12px]">
          <div class="truncate text-[14px] font-extrabold text-(--text-primary)">
            {{ v.name }}
          </div>
          <div class="text-[12px] text-(--text-secondary)">{{ metaFor(v) }}</div>
        </div>
      </NuxtLink>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Video } from "~/types/app";

defineProps<{ movies: Video[] }>();

const { formatVideoGenres, formatVideoRuntime } = useVideoFormatting();

function metaFor(v: Video): string {
  return [formatVideoGenres(v.genres), formatVideoRuntime(v.runtime)]
    .filter(Boolean)
    .join(" · ");
}

// Poster rasmi yo'q bo'lsa — milliy ranglar gradienti (prototip placeholder)
const GRADS = [
  "linear-gradient(150deg,#16265e,#1445a7)",
  "linear-gradient(150deg,#14939b,#0e6f75)",
  "linear-gradient(150deg,#a34a2a,#c99a3c)",
  "linear-gradient(150deg,#1c2433,#16265e)",
];
const gradFor = (i: number) => GRADS[i % GRADS.length];
</script>

<style scoped>
/* §11 uch qavatli oltin romb */
.tm-diamond3 {
  width: 18px;
  height: 18px;
  flex: none;
  transform: rotate(45deg);
  background: var(--accent-gold);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 0 3px rgba(201, 154, 60, 0.25);
}
.tm-diamond3-mid {
  width: 8px;
  height: 8px;
  background: var(--page-bg);
  display: flex;
  align-items: center;
  justify-content: center;
}
.tm-diamond3-core {
  width: 4px;
  height: 4px;
  background: var(--accent-teal);
}
.tm-zigzag {
  background:
    linear-gradient(135deg, #ddd0b2 5px, transparent 0) 0 0 / 16px 8px repeat-x,
    linear-gradient(-135deg, #ddd0b2 5px, transparent 0) 8px 0 / 16px 8px repeat-x;
}
.tm-vcard {
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.tm-vcard:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-card-hover);
}
</style>
