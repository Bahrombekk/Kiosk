<template>
  <UModal v-model:open="isModalOpenModel" scrollable>
    <template #content>
      <div
        v-if="selectedVideo"
        class="overflow-hidden rounded-[24px] bg-(--surface-bg)"
      >
        <MediaPoster
          :src="selectedVideo.image.original"
          :background-src="selectedVideo.image.medium"
          :alt="selectedVideo.name"
          frame-class="h-[264px]"
          image-class="z-2 h-[264px] w-full object-contain"
        >
          <ModalCloseButton
            class="h-[44px] w-[44px] border border-white/50 bg-white/50 text-(--text-primary) backdrop-blur-[5px]"
            icon="lucide:x"
            @click="isModalOpenModel = false"
          />
        </MediaPoster>
        <div class="p-[16px]">
          <p class="m-0 text-[1.25rem]">{{ selectedVideo.name }}</p>
          <p class="m-0 text-[0.875rem] text-(--text-secondary)">
            {{ formatVideoGenres(selectedVideo.genres) }}
            {{ formatVideoRuntime(selectedVideo.runtime) }}
          </p>
          <!-- v-html EMAS — backend matni oddiy matn sifatida chiqadi
               (stored-XSS oldini olish; server ham teglarni tozalaydi) -->
          <p
            class="my-[16px] max-h-[156px] overflow-y-auto text-[1rem] text-(--text-secondary)"
          >
            {{ selectedVideo.summary }}
          </p>
          <PrimaryActionButton
            :to="{ name: 'videos-id', params: { id: selectedVideo.id } }"
          >
            <template #icon>
              <PlaybackIcon class="h-[24px] w-[24px]" />
            </template>
            {{ $t("buttonActions.watch") }}
          </PrimaryActionButton>
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { Video } from "~/types/app";
import PlaybackIcon from "~/assets/svg/play.svg";

const isModalOpenModel = defineModel("isModalOpen", { type: Boolean });

defineProps<{
  selectedVideo: Video | undefined;
}>();

const { formatVideoGenres, formatVideoRuntime } = useVideoFormatting();
</script>
