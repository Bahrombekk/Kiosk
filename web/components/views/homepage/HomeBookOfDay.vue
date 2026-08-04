<!-- HomeBookOfDay.vue — "Kun kitobi" kartasi (§9). -->
<template>
  <div
    v-if="book"
    class="flex flex-1 items-center gap-[16px] rounded-[20px] bg-(--surface-bg) p-[18px] shadow-(--shadow-card)"
  >
    <!-- Muqova 82x116: navy gradient + oltin border + L-hoshiyalar + nom -->
    <div class="tm-cover">
      <span class="tm-corner tm-corner--tl" />
      <span class="tm-corner tm-corner--br" />
      <img
        v-if="book.image?.original"
        :src="book.image.original"
        :alt="book.title"
        class="absolute inset-0 h-full w-full rounded-[8px] object-cover"
        @error="imgOk = false"
        v-show="imgOk"
      />
      <span
        v-show="!imgOk"
        class="px-[8px] text-center font-[Unbounded] text-[10px] font-semibold leading-[1.4] text-[rgba(255,255,255,.92)]"
      >
        {{ book.title }}
      </span>
    </div>
    <div class="flex flex-col gap-[6px]">
      <div class="text-[10px] font-extrabold tracking-[.14em] text-(--accent-gold)">
        {{ $t("bookOfDay") }}
      </div>
      <div class="text-[17px] font-extrabold text-(--text-primary)">{{ book.title }}</div>
      <div class="text-[12px] text-(--text-secondary)">
        {{ book.author }}<template v-if="book.pageCount"> · {{ book.pageCount }} {{ $t("pages") }}</template>
      </div>
      <div class="mt-[4px] flex gap-[8px]">
        <NuxtLink
          v-if="book.contentModes.readable"
          :to="{ name: 'books-id', params: { id: book.id }, query: { readable: 1 } }"
          class="rounded-[12px] bg-(--brand-base) px-[18px] py-[10px] text-[12px] font-extrabold text-white no-underline transition-colors hover:bg-(--brand-hover)"
        >
          {{ $t("buttonActions.read") }}
        </NuxtLink>
        <NuxtLink
          v-if="book.contentModes.audible"
          :to="{ name: 'books-id', params: { id: book.id }, query: { audible: 1 } }"
          class="rounded-[12px] bg-(--accent-gold-surface) px-[18px] py-[10px] text-[12px] font-extrabold text-(--accent-gold-text) no-underline transition-colors hover:bg-[#f0e0ba]"
        >
          {{ $t("buttonActions.listen") }}
        </NuxtLink>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Book } from "~/types/app";

defineProps<{ book: Book | undefined }>();
const imgOk = ref(true);
</script>

<style scoped>
.tm-cover {
  position: relative;
  width: 82px;
  height: 116px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: linear-gradient(160deg, #16265e, #0d1739);
  border: 1.5px solid rgba(201, 154, 60, 0.55);
  box-shadow: inset 0 0 0 3px rgba(201, 154, 60, 0.18);
  overflow: hidden;
}
.tm-corner {
  position: absolute;
  width: 13px;
  height: 13px;
  z-index: 1;
}
.tm-corner--tl {
  top: 5px;
  left: 5px;
  border-top: 2px solid rgba(232, 200, 122, 0.8);
  border-left: 2px solid rgba(232, 200, 122, 0.8);
  border-top-left-radius: 4px;
}
.tm-corner--br {
  bottom: 5px;
  right: 5px;
  border-bottom: 2px solid rgba(232, 200, 122, 0.8);
  border-right: 2px solid rgba(232, 200, 122, 0.8);
  border-bottom-right-radius: 4px;
}
</style>
