<!-- TextBookReader.vue — o'qish rejimi (§21): tepada sarlavha paneli
     (ortga + nom + sahifa), markazda qog'oz karta (ivory reader foni). -->
<template>
  <div class="flex h-dvh flex-col overflow-hidden bg-(--reader-bg) text-(--text-primary)">
    <!-- Tepa panel -->
    <div
      class="flex items-center gap-[16px] bg-(--page-bg) px-[clamp(16px,3vw,32px)] py-[14px]"
      style="box-shadow: 0 2px 12px rgba(28, 36, 51, 0.06)"
    >
      <NuxtLink
        :to="{ name: 'books' }"
        class="rounded-[12px] bg-(--surface-bg) px-[18px] py-[10px] text-[13px] font-extrabold text-(--text-primary) no-underline shadow-(--shadow-card)"
      >
        ← {{ $t("back") }}
      </NuxtLink>
      <div class="truncate font-[Unbounded] text-[15px] font-semibold">
        {{ chapterTitle }}
      </div>
      <div class="ml-auto whitespace-nowrap text-[12px] font-extrabold text-(--text-secondary)">
        {{ currentPage }} / {{ book.pageCount || "—" }} {{ $t("pages") }}
      </div>
    </div>

    <!-- Qog'oz -->
    <main
      ref="scrollRef"
      class="flex flex-1 justify-center overflow-y-auto p-[clamp(16px,3vw,32px)]"
      @scroll="updateProgress"
    >
      <div
        class="w-[680px] max-w-full rounded-[16px] bg-(--paper-bg) p-[clamp(28px,5vw,48px)_clamp(24px,5vw,56px)]"
        style="box-shadow: 0 20px 60px rgba(28, 36, 51, 0.1)"
      >
        <h1 class="m-0 mb-[8px] font-[Unbounded] text-[22px] font-semibold text-(--text-primary)">
          {{ chapterTitle }}
        </h1>
        <div class="mb-[24px] h-[3px] w-[56px] bg-(--accent-gold)" />

        <p v-if="loading" class="text-center text-(--text-secondary)">{{ $t("loading") }}</p>
        <template v-else-if="loadError">
          <p class="text-center text-(--danger)">{{ $t("connectionError") }}</p>
          <div class="mt-[16px] text-center">
            <button
              type="button"
              class="rounded-[12px] bg-(--brand-base) px-[20px] py-[10px] text-[13px] font-extrabold text-white"
              @click="loadText"
            >
              {{ $t("retry") }}
            </button>
          </div>
        </template>
        <p v-else-if="!paragraphs.length" class="text-center text-(--text-secondary)">
          {{ $t("noContent") }}
        </p>
        <template v-else>
          <p
            v-for="(paragraph, index) in paragraphs"
            :key="index"
            class="m-0 mb-[18px] indent-[1.25rem] text-[17px] leading-[1.9] text-[#2c3242]"
          >
            {{ paragraph }}
          </p>
        </template>
      </div>
    </main>
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
  const total = props.book.pageCount || 1;
  currentPage.value = Math.min(
    total,
    Math.max(1, Math.round(progress * total) || 1),
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
