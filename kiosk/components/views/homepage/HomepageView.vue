<template>
  <div
    class="mx-auto grid max-w-[1024px] grid-cols-1 gap-[24px] md:grid-cols-2"
  >
    <div class="flex flex-col gap-[24px] self-start">
      <HomepageStats />
      <HomepageAds />
    </div>
    <div class="flex flex-col gap-[24px] h-auto self-start">
      <FetchErrorState v-if="moviesError && booksError" @retry="retryAll" />
      <HomepageRecommendations v-else :movies="recMovies" :books="recBooks" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Book, Video } from "~/types/app";

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

function retryAll() {
  refreshMovies();
  refreshBooks();
}

// Tavsiya etilganlar birinchi; agar 2 tadan kam bo'lsa — qolganlar bilan
// to'ldiriladi (user kiosk home.py:544-556 bilan bir xil).
function recommendedFirst<T extends { isRecommended: boolean }>(items: T[]): T[] {
  const recs = items.filter((i) => i.isRecommended);
  return recs.length >= 2 ? recs : [...recs, ...items.filter((i) => !i.isRecommended)];
}

const langMovies = filterByLang(movies);
const langBooks = filterByLang(books);

// Home karuseliga FAQAT kino tushadi (musiqa/multfilm emas), tavsiya birinchi.
const recMovies = computed(() =>
  recommendedFirst(langMovies.value.filter((m) => m.type === "movie")),
);
const recBooks = computed(() => recommendedFirst(langBooks.value));
</script>
