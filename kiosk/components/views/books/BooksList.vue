<template>
  <!-- Bo'sh holat — jim bo'sh grid o'rniga aniq xabar -->
  <p
    v-if="!books?.length"
    class="py-[48px] text-center text-[1.25rem] text-(--text-secondary)"
  >
    {{ $t("nothingFound") }}
  </p>
  <PageGrid v-else columns="books">
    <div
      v-for="book in books"
      :key="book.id"
      class="cursor-pointer overflow-hidden rounded-[12px] bg-(--surface-bg)"
      @click="$emit('openBookModal', book)"
    >
      <MediaPoster
        :src="book.image.original"
        :background-src="book.image.medium"
        :alt="book.title"
        frame-class="rounded-[12px] p-[15px]"
        image-class="z-2 h-[170px] w-[125px] rounded-[4px] border border-white/60 object-cover"
      >
        <div
          class="absolute top-[8px] right-[8px] z-3 flex items-center gap-[8px] rounded-full bg-(--surface-bg) px-[8px] py-[4px]"
        >
          <BookOpenIcon
            v-if="book.contentModes.readable"
            class="h-[20px] w-[20px] pt-[2px] text-(--brand-base)"
          />
          <HeadphonesIconAlt
            v-if="book.contentModes.audible"
            class="text-(--warning-base)"
          />
        </div>
      </MediaPoster>
      <div class="p-[12px]">
        <p class="m-0 text-[1.25rem]">{{ book.title }}</p>
        <div class="flex items-center justify-between">
          <p class="m-0 text-[0.875rem] text-(--text-secondary)">
            {{ book.author }}
          </p>
          <p class="m-0 text-[0.875rem] text-(--text-secondary)">
            {{ book.pageCount }} {{ $t("pages_short") }}
          </p>
        </div>
      </div>
    </div>
  </PageGrid>
</template>

<script setup lang="ts">
import BookOpenIcon from "~/assets/svg/book-open.svg";
import HeadphonesIconAlt from "~/assets/svg/headphones-alt-1.svg";
import type { Book } from "~/types/app";

defineProps<{
  books: Book[] | undefined;
}>();

defineEmits<{
  openBookModal: [book: Book];
}>();
</script>
