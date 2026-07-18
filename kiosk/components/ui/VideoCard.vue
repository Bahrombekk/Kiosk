<template>
  <div class="overflow-hidden rounded-[24px] bg-(--surface-bg)">
    <MediaPoster
      :src="video.image.original"
      :background-src="video.image.medium"
      :alt="video.name"
      frame-class="h-[171px] rounded-[24px]"
      image-class="z-2 h-[171px] w-full object-contain"
    >
      <button
        class="absolute top-1/2 left-1/2 z-3 flex h-[56px] w-[56px] -translate-x-1/2 -translate-y-1/2 cursor-pointer items-center justify-center rounded-full border border-white/50 bg-white/50 backdrop-blur-[5px]"
        type="button"
        @click="$emit('select', video)"
      >
        <PlaybackIcon class="mt-[3px] text-[24px] text-(--text-primary)" />
      </button>
    </MediaPoster>
    <div class="p-[16px]">
      <p class="m-0 text-[1.25rem]">{{ video.name }}</p>
      <p class="m-0 text-[0.875rem] text-(--text-secondary)">
        {{ formatVideoGenres(video.genres) }}
        {{ formatVideoRuntime(video.runtime) }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Video } from "~/types/app";
import PlaybackIcon from "~/assets/svg/play.svg";

defineProps<{
  video: Video;
}>();

defineEmits<{
  select: [video: Video];
}>();

const { formatVideoGenres, formatVideoRuntime } = useVideoFormatting();
</script>
