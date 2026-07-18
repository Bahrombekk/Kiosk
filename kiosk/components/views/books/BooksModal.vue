<template>
  <UModal
    v-model:open="model"
    scrollable
    :ui="{
      content: 'max-w-[632px] h-auto! md:h-[393px]',
    }"
  >
    <template #content>
      <div
        v-if="selectedBook"
        class="relative grid h-auto overflow-hidden rounded-[24px] bg-(--surface-bg) md:h-[393px] md:grid-cols-[250px_auto]"
      >
        <ModalCloseButton @click="model = false" />
        <MediaPoster
          :src="selectedBook.image.original"
          :background-src="selectedBook.image.medium"
          :alt="selectedBook.title"
          frame-class="h-[273px] w-full rounded-none p-[15px] md:h-full md:w-[250px]"
          image-class="h-[273px] w-auto rounded-[8px] border border-white/60 object-contain"
        >
          <div
            class="absolute bottom-[12px] z-3 rounded-full bg-white/25 px-[12px] py-[6px] text-white backdrop-blur-[105px]"
          >
            {{ selectedBook.pageCount }} {{ $t("pages") }}
          </div>
        </MediaPoster>
        <div class="flex flex-col gap-[24px] p-[24px]">
          <div>
            <p class="m-0 text-[1.75rem]">{{ selectedBook.title }}</p>
            <p class="m-0 text-[1rem] font-semibold text-(--text-secondary)">
              {{ selectedBook.author }}
            </p>
          </div>
          <hr class="h-px border-0 bg-(--neutral-stroke)" />
          <!-- v-html EMAS — backend matni oddiy matn sifatida chiqadi
               (stored-XSS oldini olish; server ham teglarni tozalaydi) -->
          <p
            class="m-0 max-h-[144px] overflow-y-auto text-[1rem] text-(--text-secondary)"
          >
            {{ selectedBook.description }}
          </p>
          <div class="mt-auto flex flex-col items-center gap-[8px] md:flex-row">
            <PrimaryActionButton
              :to="{
                name: 'books-id',
                params: { id: selectedBook.id },
                query: { audible: 1 },
              }"
              v-if="selectedBook.contentModes.audible"
              variant="warning"
            >
              <template #icon>
                <HeadphonesIcon class="h-[24px] w-[24px]" />
              </template>
              {{ $t("buttonActions.listen") }}
            </PrimaryActionButton>
            <PrimaryActionButton
              :to="{
                name: 'books-id',
                params: { id: selectedBook.id },
                query: { readable: 1 },
              }"
              v-if="selectedBook.contentModes.readable"
              variant="brand"
            >
              <template #icon>
                <BookOpenIcon class="h-[24px] w-[24px] pt-[5px]" />
              </template>
              {{ $t("buttonActions.read") }}
            </PrimaryActionButton>
          </div>
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import HeadphonesIcon from "~/assets/svg/headphones-alt.svg";
import BookOpenIcon from "~/assets/svg/book-open.svg";
import type { Book } from "~/types/app";
const model = defineModel("isModalOpen", { type: Boolean });
defineProps<{
  selectedBook: Book | undefined;
}>();
</script>
