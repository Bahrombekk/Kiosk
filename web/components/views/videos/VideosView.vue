<template>
  <div class="flex flex-col gap-[20px]" style="animation: omFade 0.35s ease">
    <FetchErrorState v-if="error" @retry="refresh" />
    <template v-else>
      <VideosModal
        v-model:is-modal-open="isModalOpen"
        :selected-video="selectedVideo"
      />

      <!-- Tur tab (pill) + qidiruv -->
      <VideosFilter
        :items="videoTabs"
        v-model:active-category="activeCategory"
        v-model:search-query="searchQuery"
      />

      <div v-if="!baseVideos.length" class="py-[60px] text-center text-[15px] text-(--text-secondary)">
        {{ $t("nothingFound") }}
      </div>

      <template v-else>
        <!-- §13 haftaning filmi -->
        <VideoFeatured :video="featured" @select="openVideoModal" />

        <!-- §14 janr chiplari -->
        <div class="flex flex-wrap items-center gap-[8px]">
          <span class="mr-[4px] h-[12px] w-[12px] flex-none rotate-45 bg-(--accent-gold)" />
          <button
            v-for="chip in genreChips"
            :key="chip.key"
            type="button"
            class="cursor-pointer rounded-full border-[1.5px] px-[18px] py-[9px] text-[13px] transition-colors"
            :class="
              chip.key === activeGenre
                ? 'border-(--brand-base) bg-(--brand-base) font-extrabold text-white'
                : 'border-(--stroke-2) bg-(--surface-bg) font-semibold text-(--text-muted-btn) hover:border-(--brand-base)'
            "
            @click="activeGenre = chip.key"
          >
            {{ chip.label }}
          </button>
        </div>

        <!-- §15 poster to'r (sahifalab ko'rsatiladi) -->
        <div
          class="grid gap-[16px]"
          style="grid-template-columns: repeat(auto-fill, minmax(min(165px, 100%), 1fr))"
        >
          <VideoPosterCard
            v-for="(video, i) in pagedVideos"
            :key="video.id"
            :video="video"
            :index="i"
            @select="openVideoModal"
          />
        </div>

        <!-- Sahifalash -->
        <Paginator :total="filteredVideos.length" :per-page="PAGE_SIZE" v-model:page="page" />
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { IconItem, Video } from "~/types/app";
import MoviesIcon from "~/assets/svg/film.svg";
import MagicWandIcon from "~/assets/svg/wand-magic-sparkles.svg";
import MusicIcon from "~/assets/svg/music.svg";

const { t } = useI18n();
const { filterByLang } = useContentLang();
const { data: videos, error, refresh } =
  await useFetch<Video[]>("/api/movies");

const activeCategory = ref("movies");
const searchQuery = ref("");
const activeGenre = ref("all");

// Sahifalash — bir sahifada 12 ta (2 qator). Ko'p kino bo'lsa sahifa raqamlari.
const PAGE_SIZE = 12;
const page = ref(1);

// Videolarda "Barchasi" yo'q — har tab bitta turga bog'langan (kiosk kabi).
const videoTabs = computed<IconItem[]>(() => [
  { key: "movies", label: t("categories.movies"), icon: MoviesIcon },
  { key: "cartoons", label: t("categories.cartoons"), icon: MagicWandIcon },
  { key: "music", label: t("categories.music"), icon: MusicIcon },
]);

const TAB_TYPE: Record<string, string> = {
  movies: "movie",
  cartoons: "cartoon",
  music: "music",
};

const langVideos = filterByLang(videos);

const normalizedSearchQuery = computed(() =>
  searchQuery.value.trim().toLowerCase(),
);

// Tab (tur) + qidiruv bo'yicha — janr chiplari va featured shundan hosil bo'ladi.
const baseVideos = computed(() => {
  const type = TAB_TYPE[activeCategory.value] ?? "movie";
  return langVideos.value.filter((v) => {
    if (v.type !== type) return false;
    if (!normalizedSearchQuery.value) return true;
    const hay = [v.name, ...v.genres].join(" ").toLowerCase();
    return hay.includes(normalizedSearchQuery.value);
  });
});

// Janr chiplari: "Barchasi" + mavjud janrlar (birinchi janr, alifbo tartibida).
const genreChips = computed(() => {
  const genres = Array.from(
    new Set(baseVideos.value.map((v) => v.genres[0]).filter(Boolean)),
  ).sort((a, b) => a.localeCompare(b));
  return [
    { key: "all", label: t("categories.all") },
    ...genres.map((g) => ({ key: g, label: g })),
  ];
});

// Tanlangan chip yo'qolsa (tab/qidiruv o'zgarsa) "all" ga qaytamiz.
watch(genreChips, (chips) => {
  if (!chips.some((c) => c.key === activeGenre.value)) activeGenre.value = "all";
});

const filteredVideos = computed(() =>
  activeGenre.value === "all"
    ? baseVideos.value
    : baseVideos.value.filter((v) => v.genres[0] === activeGenre.value),
);

// Joriy sahifa kesimi (faqat shu ko'rsatiladi)
const pagedVideos = computed(() =>
  filteredVideos.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE),
);

// Tab / janr / qidiruv o'zgarsa 1-sahifaga qaytamiz
watch([activeCategory, activeGenre, normalizedSearchQuery], () => {
  page.value = 1;
});

// Haftaning filmi: tavsiya etilgani, bo'lmasa birinchisi.
const featured = computed(
  () => filteredVideos.value.find((v) => v.isRecommended) || filteredVideos.value[0],
);

const isModalOpen = ref(false);
const selectedVideo = ref<Video>();

function openVideoModal(video: Video) {
  selectedVideo.value = video;
  isModalOpen.value = true;
}
</script>
