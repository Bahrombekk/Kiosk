<template>
  <div
    class="relative flex h-dvh overflow-hidden bg-(--primary-bg) bg-[url('/splash_screen_background.png')] dark:bg-[url('/splash_screen_background_dark.png')] bg-cover text-(--text-primary)"
  >
    <UButton
      :to="{ name: 'books' }"
      icon="i-lucide-arrow-left"
      variant="soft"
      size="xl"
      class="absolute top-[20px] left-[24px] z-10 rounded-[12px]"
      :ui="{
        base: 'bg-(--brand-base)/25 backdrop-blur-lg text-(--brand-base) active:bg-(--brand-base) active:text-white hover:bg-(--brand-base) hover:text-white',
      }"
    >
      {{ $t("back") }}
    </UButton>

    <main
      ref="scrollRef"
      class="mx-auto h-full w-full max-w-[720px] overflow-y-auto px-[24px] py-[70px] text-[1.125rem] leading-[1.75] text-(--text-secondary)"
      @scroll="updateProgress"
    >
      <h1
        class="m-0 mb-[40px] text-center text-[1.5rem] font-semibold text-(--text-primary)"
      >
        {{ chapterTitle }}
      </h1>
      <p v-if="loading" class="text-center">{{ $t("loading") }}</p>
      <template v-else-if="loadError">
        <p class="text-center text-red-500">{{ $t("connectionError") }}</p>
        <div class="mt-[16px] text-center">
          <UButton icon="i-lucide-refresh-cw" @click="loadText">
            {{ $t("retry") }}
          </UButton>
        </div>
      </template>
      <p v-else-if="!paragraphs.length" class="text-center">
        {{ $t("noContent") }}
      </p>
      <template v-else>
        <p
          v-for="(paragraph, index) in paragraphs"
          :key="index"
          class="m-0 mb-[4px] indent-[1.25rem]"
        >
          {{ paragraph }}
        </p>
      </template>
    </main>

    <div
      class="absolute bottom-[24px] left-[24px] rounded-[8px] bg-(--brand-base) px-[12px] py-[4px] text-[1rem] font-semibold text-white"
    >
      {{ currentPage }} / {{ book.pageCount }}
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Book } from "~/types/app";

const props = defineProps<{
  book: Book;
}>();

const scrollRef = ref<HTMLElement | null>(null);
const currentPage = ref(1);
const remoteText = ref("");

const chapterTitle = computed(
  () => props.book.chapterTitle || props.book.title,
);
const stripHtml = (value: string) =>
  value
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
const rawText = computed(
  () =>
    remoteText.value ||
    props.book.textContent ||
    stripHtml(props.book.description),
);
const paragraphs = computed(() =>
  rawText.value
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean),
);

const updateProgress = () => {
  const element = scrollRef.value;
  if (!element) return;

  const scrollable = element.scrollHeight - element.clientHeight;
  const progress = scrollable > 0 ? element.scrollTop / scrollable : 0;
  currentPage.value = Math.min(
    props.book.pageCount,
    Math.max(1, Math.round(progress * props.book.pageCount) || 1),
  );
};

const loading = ref(false);
const loadError = ref(false);

// Matnni yuklash — xato/oflaynda unhandled rejection o'rniga aniq xato
// holati + qayta urinish (avval jimgina description'ga tushib ketardi).
async function loadText() {
  if (!props.book.textUrl) return;
  loading.value = true;
  loadError.value = false;
  try {
    remoteText.value = await $fetch<string>(props.book.textUrl, {
      responseType: "text",
      timeout: 20000,
    });
  } catch {
    loadError.value = true;
  } finally {
    loading.value = false;
  }
  await nextTick();
  updateProgress();
}

onMounted(async () => {
  await loadText();
  await nextTick();
  updateProgress();
});
</script>
