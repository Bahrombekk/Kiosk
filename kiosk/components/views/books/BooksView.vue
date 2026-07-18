<template>
  <div class="mx-auto max-w-[1920px]">
    <FetchErrorState v-if="error" @retry="refresh" />
    <template v-else>
      <BooksModal
        :selectedBook="selectedBook"
        v-model:isModalOpen="isModalOpen"
      />
      <BooksFilter v-model:activeCategory="activeCategory" :items="bookTabs" />
      <BooksList :books="filteredBooks" @openBookModal="openBookModal" />
    </template>
  </div>
</template>

<script setup lang="ts">
import type { Book, IconItem } from "~/types/app";
import AllbooksIcon from "~/assets/svg/grid-search.svg";
import GenreIcon from "~/assets/svg/book.svg";

const { t } = useI18n();
const { filterByLang } = useContentLang();
const { data: books, error, refresh } = await useFetch<Book[]>("/api/books");

const activeCategory = ref("all");

// Til bo'yicha filtr (kiosk: lang bo'sh yoki joriy tilga teng)
const langBooks = filterByLang(books);

// Tablar DINAMIK — joriy tildagi kitoblardagi mavjud janrlardan quriladi
// (user kiosk books.py:_on_loaded bilan bir xil). Birinchisi "Barchasi".
const genres = computed(() => {
  const set = new Set<string>();
  for (const b of langBooks.value) {
    const g = (b.genre || "").trim();
    if (g) set.add(g);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
});

const bookTabs = computed<IconItem[]>(() => [
  { key: "all", label: t("categories.all"), icon: AllbooksIcon },
  ...genres.value.map((g) => ({ key: g, label: g, icon: GenreIcon })),
]);

// Til almashsa tanlangan janr yo'qolsa — "Barchasi"ga qaytamiz
watch(genres, (list) => {
  if (activeCategory.value !== "all" && !list.includes(activeCategory.value)) {
    activeCategory.value = "all";
  }
});

// Aniq janr tengligi bo'yicha filtr (kiosk books.py:219)
const filteredBooks = computed(() =>
  langBooks.value.filter(
    (b) => activeCategory.value === "all" || b.genre === activeCategory.value,
  ),
);

const isModalOpen = ref(false);
const selectedBook = ref<Book>();

function openBookModal(book: Book) {
  selectedBook.value = book;
  isModalOpen.value = true;
}
</script>
