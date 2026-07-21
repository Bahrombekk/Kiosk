<!-- VideoPosterCard.vue — poster karta (§15): 236px poster + girih + shtrix
     hoshiya + play + TAVSIYA + pastda nom/meta (gradient ustida). -->
<template>
  <div
    class="tm-poster cursor-pointer"
    @click="$emit('select', video)"
  >
    <div
      class="relative h-[236px] overflow-hidden rounded-[16px] shadow-(--shadow-poster)"
      :style="{ background: grad }"
    >
      <img
        v-if="video.image?.original"
        :src="video.image.original"
        :alt="video.name"
        loading="lazy"
        class="absolute inset-0 h-full w-full object-cover"
      />
      <div
        class="pointer-events-none absolute inset-0"
        style="
          background: repeating-conic-gradient(from 45deg, rgba(255, 255, 255, 0.08) 0 25%, transparent 0 50%);
          background-size: 30px 30px;
        "
      />
      <div class="pointer-events-none absolute inset-[6px] rounded-[11px] border border-dashed border-[rgba(232,200,122,.35)]" />
      <div class="absolute inset-0 flex items-center justify-center">
        <div
          class="flex h-[44px] w-[44px] items-center justify-center rounded-full border border-[rgba(255,255,255,.6)] bg-[rgba(255,255,255,.55)] text-[14px] text-(--text-primary) backdrop-blur-[5px]"
        >
          ▶
        </div>
      </div>
      <div
        v-if="video.isRecommended"
        class="absolute left-[10px] top-[10px] rounded-full bg-(--accent-gold) px-[8px] py-[3px] text-[9px] font-extrabold tracking-[.06em] text-(--text-on-gold)"
      >
        {{ $t("recommendedBadge") }}
      </div>
      <div
        class="absolute inset-x-0 bottom-0 px-[12px] pt-[26px] pb-[10px]"
        style="background: linear-gradient(to top, rgba(10, 16, 34, 0.85), transparent)"
      >
        <div class="truncate text-[13px] font-extrabold text-white">{{ video.name }}</div>
        <div class="truncate text-[11px] text-[rgba(255,255,255,.75)]">{{ meta }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Video } from "~/types/app";

const props = defineProps<{ video: Video; index?: number }>();
defineEmits<{ select: [video: Video] }>();

const { formatVideoGenres, formatVideoRuntime } = useVideoFormatting();
const meta = computed(() =>
  [formatVideoGenres(props.video.genres), formatVideoRuntime(props.video.runtime)]
    .filter(Boolean)
    .join(" · "),
);

const GRADS = [
  "linear-gradient(150deg,#16265e,#1445a7)",
  "linear-gradient(150deg,#14939b,#0e6f75)",
  "linear-gradient(150deg,#a34a2a,#c99a3c)",
  "linear-gradient(150deg,#1c2433,#16265e)",
];
const grad = computed(() => GRADS[(props.index ?? 0) % GRADS.length]);
</script>

<style scoped>
.tm-poster {
  transition: transform 0.15s ease;
}
.tm-poster:hover {
  transform: translateY(-4px);
}
</style>
