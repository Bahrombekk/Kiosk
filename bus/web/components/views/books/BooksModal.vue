<!-- BooksModal.vue — kitob ma'lumot modali: muqova + nom/muallif/tavsif +
     O'qish/Tinglash tugmalari (reader/audio sahifasiga o'tadi). -->
<template>
  <UModal
    v-model:open="model"
    scrollable
    :ui="{ content: 'max-w-[540px] rounded-[24px]' }"
  >
    <template #content>
      <div
        v-if="selectedBook"
        class="flex gap-[20px] rounded-[24px] bg-(--page-bg) p-[26px]"
      >
        <!-- Muqova -->
        <div
          class="relative flex h-[172px] w-[120px] flex-none items-end overflow-hidden rounded-[10px] p-[10px]"
          style="background: linear-gradient(160deg, #16265e, #0d1739)"
        >
          <img
            v-if="selectedBook.image?.original"
            :src="selectedBook.image.original"
            :alt="selectedBook.title"
            class="absolute inset-0 h-full w-full object-cover"
          />
          <span
            v-else
            class="relative font-[Unbounded] text-[11px] font-semibold leading-[1.35] text-[rgba(255,255,255,.92)]"
          >
            {{ selectedBook.title }}
          </span>
        </div>
        <!-- Ma'lumot -->
        <div class="flex min-w-0 flex-1 flex-col gap-[8px]">
          <div class="font-[Unbounded] text-[19px] font-semibold text-(--text-primary)">
            {{ selectedBook.title }}
          </div>
          <div class="text-[13px] font-bold text-(--text-secondary)">{{ meta }}</div>
          <p
            v-if="selectedBook.description"
            class="m-0 max-h-[120px] overflow-y-auto text-[13.5px] leading-[1.6] text-[#4d5464]"
          >
            {{ selectedBook.description }}
          </p>
          <div class="mt-auto flex items-center gap-[8px] pt-[10px]">
            <NuxtLink
              v-if="selectedBook.contentModes.readable"
              :to="{ name: 'books-id', params: { id: selectedBook.id }, query: { readable: 1 } }"
              class="rounded-[12px] bg-(--brand-base) px-[20px] py-[11px] text-[12px] font-extrabold text-white no-underline transition-colors hover:bg-(--brand-hover)"
            >
              {{ $t("buttonActions.read") }}
            </NuxtLink>
            <NuxtLink
              v-if="selectedBook.contentModes.audible"
              :to="{ name: 'books-id', params: { id: selectedBook.id }, query: { audible: 1 } }"
              class="rounded-[12px] bg-(--accent-gold-surface) px-[20px] py-[11px] text-[12px] font-extrabold text-(--accent-gold-text) no-underline transition-colors hover:bg-[#f0e0ba]"
            >
              {{ $t("buttonActions.listen") }}
            </NuxtLink>
            <button
              type="button"
              class="ml-auto border-0 bg-transparent text-[12px] font-extrabold text-(--text-secondary)"
              @click="model = false"
            >
              {{ $t("back") }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { Book } from "~/types/app";

const model = defineModel("isModalOpen", { type: Boolean });
const props = defineProps<{
  selectedBook: Book | undefined;
}>();

const { t } = useI18n();
const meta = computed(() => {
  const b = props.selectedBook;
  if (!b) return "";
  return [b.author, b.genre, b.pageCount ? `${b.pageCount} ${t("pages")}` : ""]
    .filter(Boolean)
    .join(" · ");
});
</script>
