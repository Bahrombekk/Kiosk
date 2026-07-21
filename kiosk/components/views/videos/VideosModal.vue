<!-- VideosModal.vue — video ma'lumot modali (§19): poster + play/close,
     nom/meta/tavsif + "Tomosha qilish" (pleyer sahifasiga o'tadi). -->
<template>
  <UModal
    v-model:open="isModalOpenModel"
    scrollable
    :ui="{ content: 'max-w-[560px] rounded-[24px]' }"
  >
    <template #content>
      <div
        v-if="selectedVideo"
        class="overflow-hidden rounded-[24px] bg-(--page-bg)"
      >
        <!-- Poster -->
        <MediaPoster
          :src="selectedVideo.image.original"
          :background-src="selectedVideo.image.medium"
          :alt="selectedVideo.name"
          frame-class="h-[220px]"
          image-class="z-2 h-[220px] w-full object-contain"
        >
          <NuxtLink
            :to="{ name: 'videos-id', params: { id: selectedVideo.id } }"
            class="absolute left-1/2 top-1/2 z-3 flex h-[64px] w-[64px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-0 bg-[rgba(255,255,255,.9)] text-[20px] text-(--text-primary) no-underline transition-colors hover:bg-white"
          >
            ▶
          </NuxtLink>
          <button
            type="button"
            class="absolute right-[12px] top-[12px] z-3 flex h-[34px] w-[34px] items-center justify-center rounded-full border-0 bg-[rgba(0,0,0,.35)] text-[15px] text-white"
            @click="isModalOpenModel = false"
          >
            ✕
          </button>
        </MediaPoster>
        <!-- Matn -->
        <div class="flex flex-col gap-[10px] p-[22px_26px]">
          <div class="font-[Unbounded] text-[20px] font-semibold text-(--text-primary)">
            {{ selectedVideo.name }}
          </div>
          <div class="text-[13px] font-bold text-(--text-secondary)">{{ meta }}</div>
          <p
            v-if="selectedVideo.summary"
            class="m-0 max-h-[156px] overflow-y-auto text-[14px] leading-[1.6] text-[#4d5464]"
          >
            {{ selectedVideo.summary }}
          </p>
          <NuxtLink
            :to="{ name: 'videos-id', params: { id: selectedVideo.id } }"
            class="mt-[6px] self-start rounded-[12px] bg-(--brand-base) px-[24px] py-[12px] text-[13px] font-extrabold text-white no-underline transition-colors hover:bg-(--brand-hover)"
          >
            ▶ {{ $t("buttonActions.watch") }}
          </NuxtLink>
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { Video } from "~/types/app";

const isModalOpenModel = defineModel("isModalOpen", { type: Boolean });

const props = defineProps<{
  selectedVideo: Video | undefined;
}>();

const { formatVideoGenres, formatVideoRuntime } = useVideoFormatting();
const meta = computed(() =>
  props.selectedVideo
    ? [
        formatVideoGenres(props.selectedVideo.genres),
        formatVideoRuntime(props.selectedVideo.runtime),
      ]
        .filter(Boolean)
        .join(" · ")
    : "",
);
</script>
