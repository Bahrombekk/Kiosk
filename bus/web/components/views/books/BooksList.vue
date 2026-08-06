<!-- BooksList.vue — kitob kartalari (§16): gorizontal karta (muqova 70x100 +
     ma'lumot: nom/muallif/janr·sahifa + O'QISH/AUDIO belgilari). -->
<template>
  <p
    v-if="!books?.length"
    class="py-[48px] text-center text-[1.25rem] text-(--text-secondary)"
  >
    {{ $t("nothingFound") }}
  </p>
  <div
    v-else
    class="grid gap-[16px]"
    style="grid-template-columns: repeat(auto-fill, minmax(min(235px, 100%), 1fr))"
  >
    <div
      v-for="(book, i) in books"
      :key="book.id"
      class="tm-book flex cursor-pointer gap-[14px] rounded-[20px] bg-(--surface-bg) p-[16px] shadow-(--shadow-card)"
      @click="$emit('openBookModal', book)"
    >
      <!-- Muqova -->
      <div
        class="relative flex h-[100px] w-[70px] flex-none items-end overflow-hidden rounded-[8px] p-[7px]"
        :style="{ background: gradFor(i) }"
      >
        <img
          v-if="book.image?.original"
          :src="book.image.original"
          :alt="book.title"
          loading="lazy"
          class="absolute inset-0 h-full w-full object-cover"
        />
        <span
          v-else
          class="relative font-[Unbounded] text-[9px] font-semibold leading-[1.3] text-[rgba(255,255,255,.92)]"
        >
          {{ book.title }}
        </span>
      </div>
      <!-- Ma'lumot -->
      <div class="flex min-w-0 flex-col gap-[4px]">
        <div class="truncate text-[14px] font-extrabold text-(--text-primary)">
          {{ book.title }}
        </div>
        <div class="truncate text-[12px] text-(--text-secondary)">{{ book.author }}</div>
        <div
          v-if="book.genre || book.pageCount"
          class="truncate text-[11px] text-(--text-secondary)"
        >
          <template v-if="book.genre">{{ book.genre }}</template>
          <template v-if="book.genre && book.pageCount"> · </template>
          <template v-if="book.pageCount">{{ book.pageCount }} {{ $t("pages") }}</template>
        </div>
        <div class="mt-auto flex flex-wrap gap-[6px] pt-[4px]">
          <span
            v-if="book.contentModes.readable"
            class="rounded-full bg-(--brand-surface) px-[9px] py-[3px] text-[10px] font-extrabold uppercase text-(--brand-base)"
          >
            {{ $t("buttonActions.read") }}
          </span>
          <span
            v-if="book.contentModes.audible"
            class="rounded-full bg-(--accent-gold-surface) px-[9px] py-[3px] text-[10px] font-extrabold text-(--accent-gold-text)"
          >
            {{ $t("audioBadge") }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Book } from "~/types/app";

defineProps<{
  books: Book[] | undefined;
}>();

defineEmits<{
  openBookModal: [book: Book];
}>();

const GRADS = [
  "linear-gradient(160deg,#16265e,#0d1739)",
  "linear-gradient(160deg,#14939b,#0e6f75)",
  "linear-gradient(160deg,#a34a2a,#7a2f18)",
  "linear-gradient(160deg,#1c2433,#16265e)",
];
const gradFor = (i: number) => GRADS[i % GRADS.length];
</script>

<style scoped>
.tm-book {
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.tm-book:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-card-hover);
}
</style>
