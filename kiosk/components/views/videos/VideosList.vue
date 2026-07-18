<template>
  <div class="flex h-[76vh] flex-col gap-[24px] overflow-y-scroll pb-[24px]">
    <div v-if="!genreSections.length" class="pt-[80px] text-center text-(--text-secondary)">
      {{ $t("noContent") }}
    </div>
    <div v-for="section in genreSections" :key="section.category">
      <div
        class="mb-[8px] flex w-full items-center justify-between rounded-full bg-(--surface-bg) px-[16px] py-[8px]"
      >
        <p class="font-semibold text-(--text-primary)">
          {{ section.category }}
        </p>
        <p class="text-[1rem] text-[#747674]">
          {{ section.count }}
        </p>
      </div>
      <div class="grid grid-cols-1 gap-[24px] sm:grid-cols-2 md:grid-cols-4">
        <VideoCard
          v-for="video in section.videos"
          :key="video.id"
          :video="video"
          @select="$emit('openVideoModal', video)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Video, VideoGenreSection } from "~/types/app";

defineProps<{
  genreSections: VideoGenreSection[];
}>();
defineEmits<{
  openVideoModal: [video: Video];
}>();
</script>
