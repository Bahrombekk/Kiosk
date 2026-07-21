<!-- VideoFeatured.vue — "Haftaning filmi" hero (§13). Navy gradient + oltin
     hoshiya/halo + girih; chapda matn + tugmalar, o'ngda 150x212 poster. -->
<template>
  <div
    v-if="video"
    class="relative flex min-h-[220px] items-center gap-[28px] overflow-hidden rounded-[24px] border-2 border-(--accent-gold) p-[clamp(22px,3vw,36px)] text-white"
    style="
      background: linear-gradient(120deg, #0e1b45, #16265e 55%, #1445a7);
      box-shadow: 0 0 0 5px rgba(201, 154, 60, 0.12), 0 18px 44px rgba(14, 27, 69, 0.22);
    "
  >
    <!-- girih tekstura -->
    <div
      class="pointer-events-none absolute inset-0"
      style="
        background: repeating-conic-gradient(from 45deg, rgba(255, 255, 255, 0.05) 0 25%, transparent 0 50%);
        background-size: 56px 56px;
      "
    />
    <!-- Matn -->
    <div class="relative z-1 flex min-w-0 flex-1 flex-col gap-[10px]">
      <div class="text-[11px] font-extrabold tracking-[.16em] text-(--accent-gold-light)">
        {{ $t("videoFeatured") }}
      </div>
      <div class="font-[Unbounded] text-[clamp(22px,2.6vw,32px)] font-semibold leading-[1.2]">
        {{ video.name }}
      </div>
      <div class="text-[13px] font-bold text-[rgba(255,255,255,.7)]">{{ meta }}</div>
      <div
        v-if="video.summary"
        class="line-clamp-3 max-w-[560px] text-[14px] leading-[1.6] text-[rgba(255,255,255,.82)]"
      >
        {{ video.summary }}
      </div>
      <div class="mt-[6px] flex flex-wrap gap-[10px]">
        <button
          type="button"
          class="rounded-[12px] border-0 bg-(--accent-gold) px-[24px] py-[12px] text-[13px] font-extrabold text-(--text-on-gold) transition-colors hover:bg-(--accent-gold-light)"
          @click="$emit('select', video)"
        >
          ▶ {{ $t("buttonActions.watch") }}
        </button>
      </div>
    </div>
    <!-- Poster 150x212 -->
    <div
      class="relative z-1 hidden h-[212px] w-[150px] flex-none overflow-hidden rounded-[14px] sm:block"
      :style="{ background: 'linear-gradient(150deg,#16265e,#1445a7)', boxShadow: '0 14px 34px rgba(0,0,0,.35)' }"
    >
      <img
        v-if="video.image?.original"
        :src="video.image.original"
        :alt="video.name"
        class="absolute inset-0 h-full w-full object-cover"
      />
      <div
        class="pointer-events-none absolute inset-0"
        style="
          background: repeating-conic-gradient(from 45deg, rgba(255, 255, 255, 0.08) 0 25%, transparent 0 50%);
          background-size: 30px 30px;
        "
      />
      <div class="pointer-events-none absolute inset-[6px] rounded-[9px] border border-dashed border-[rgba(232,200,122,.4)]" />
      <div
        class="absolute inset-x-0 bottom-0 px-[10px] pt-[22px] pb-[10px]"
        style="background: linear-gradient(to top, rgba(10, 16, 34, 0.85), transparent)"
      >
        <div class="font-[Unbounded] text-[12px] font-semibold leading-[1.3] text-white">
          {{ video.name }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Video } from "~/types/app";

const props = defineProps<{ video: Video | undefined }>();
defineEmits<{ select: [video: Video] }>();

const { formatVideoGenres, formatVideoRuntime } = useVideoFormatting();
const meta = computed(() =>
  props.video
    ? [formatVideoGenres(props.video.genres), formatVideoRuntime(props.video.runtime)]
        .filter(Boolean)
        .join(" · ")
    : "",
);
</script>
