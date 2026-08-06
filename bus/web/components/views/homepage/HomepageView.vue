<!-- HomepageView.vue — Bosh sahifa (§7-12): hero + 3 stat + kun kitobi
     (yuqori 2 ustunli to'r), reklama banner (§10), tavsiya bo'limi (§11-12). -->
<template>
  <div class="flex flex-col gap-[22px]" style="animation: omFade 0.35s ease">
    <!-- Yuqori to'r: chapda hero, o'ngda stat kartalar + kun kitobi -->
    <div
      class="grid items-stretch gap-[18px]"
      style="grid-template-columns: repeat(auto-fit, minmax(min(420px, 100%), 1fr))"
    >
      <HomeHero :route="route" :status="status" />
      <div class="flex flex-col gap-[14px]">
        <HomepageStats />
        <FetchErrorState v-if="booksError && moviesError" @retry="retryAll" />
        <HomeBookOfDay v-else :book="recBooks[0]" />
      </div>
    </div>

    <!-- §10 reklama banner -->
    <HomepageAds />

    <!-- §11-12 tavsiya bo'limi -->
    <FetchErrorState v-if="moviesError" @retry="refreshMovies" />
    <div v-else-if="!recMovies.length" class="py-[40px] text-center text-(--text-secondary)">
      {{ $t("nothingFound") }}
    </div>
    <HomeRecommend v-else :movies="recMovies" />
  </div>
</template>

<script setup lang="ts">
import type { Book, TrainRoute, TrainStatus, Video } from "~/types/app";

const { filterByLang } = useContentLang();

const {
  data: movies,
  error: moviesError,
  refresh: refreshMovies,
} = await useFetch<Video[]>("/api/movies");
const {
  data: books,
  error: booksError,
  refresh: refreshBooks,
} = await useFetch<Book[]>("/api/books");

// Hero uchun marshrut + status (joriy bekat, tezlik). Xatosi hero'ni buzmaydi.
const { data: route } = await useFetch<TrainRoute>("/api/route", {
  default: () => null,
});
const { data: status } = await useFetch<TrainStatus>("/api/status", {
  default: () => null,
});

function retryAll() {
  refreshMovies();
  refreshBooks();
}

// Tavsiya etilganlar birinchi; 2 tadan kam bo'lsa qolganlar bilan to'ldiriladi
// (user kiosk home.py:544-556 bilan bir xil).
function recommendedFirst<T extends { isRecommended: boolean }>(items: T[]): T[] {
  const recs = items.filter((i) => i.isRecommended);
  return recs.length >= 2 ? recs : [...recs, ...items.filter((i) => !i.isRecommended)];
}

const langMovies = filterByLang(movies);
const langBooks = filterByLang(books);

// Tavsiyaga FAQAT kino tushadi (musiqa/multfilm emas), tavsiya birinchi.
const recMovies = computed(() =>
  recommendedFirst(langMovies.value.filter((m) => m.type === "movie")),
);
const recBooks = computed(() => recommendedFirst(langBooks.value));
</script>
