<template>
  <div class="mx-auto max-w-[1920px]">
    <FetchErrorState v-if="error" @retry="refresh" />
    <template v-else>
      <VideosModal
        v-model:is-modal-open="isModalOpen"
        :selected-video="selectedVideo"
      />
      <VideosFilter
        :items="videoTabs"
        v-model:active-category="activeCategory"
        v-model:search-query="searchQuery"
      />
      <VideosList
        :genre-sections="genreSections"
        @openVideoModal="openVideoModal"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import type { IconItem, Video, VideoGenreSection } from "~/types/app";
import MoviesIcon from "~/assets/svg/film.svg";
import MagicWandIcon from "~/assets/svg/wand-magic-sparkles.svg";
import MusicIcon from "~/assets/svg/music.svg";

const { t } = useI18n();
const { filterByLang } = useContentLang();
const { data: videos, error, refresh } =
  await useFetch<Video[]>("/api/movies");

const activeCategory = ref("movies");
const searchQuery = ref("");

// Videolarda "Barchasi" yo'q — har tab bitta turga bog'langan (kiosk kabi).
const videoTabs = computed<IconItem[]>(() => [
  { key: "movies", label: t("categories.movies"), icon: MoviesIcon },
  { key: "cartoons", label: t("categories.cartoons"), icon: MagicWandIcon },
  { key: "music", label: t("categories.music"), icon: MusicIcon },
]);

// Tab kaliti -> backend `type`
const TAB_TYPE: Record<string, string> = {
  movies: "movie",
  cartoons: "cartoon",
  music: "music",
};

// Til bo'yicha filtr (kiosk: lang bo'sh yoki joriy tilга teng)
const langVideos = filterByLang(videos);

const normalizedSearchQuery = computed(() =>
  searchQuery.value.trim().toLowerCase(),
);

// Joriy tab (tur) + qidiruv (nom/janr bo'yicha)
const filteredVideos = computed(() => {
  const type = TAB_TYPE[activeCategory.value] ?? "movie";
  return langVideos.value.filter((v) => {
    if (v.type !== type) return false;
    if (!normalizedSearchQuery.value) return true;
    const hay = [v.name, ...v.genres].join(" ").toLowerCase();
    return hay.includes(normalizedSearchQuery.value);
  });
});

// Birinchi janr bo'yicha guruh; janrlar alifbo tartibida; janrsizlar "Boshqa"
// sarlavhasi bilan oxirida (user kiosk videos.py:_group_by_genre bilan bir xil).
const genreSections = computed<VideoGenreSection[]>(() => {
  const otherLabel = t("categories.other");
  const groups = new Map<string, Video[]>();
  for (const v of filteredVideos.value) {
    const key = v.genres[0] || otherLabel;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(v);
  }
  const sections = Array.from(groups, ([category, vids]) => ({
    category,
    count: vids.length,
    videos: vids,
  }));
  sections.sort((a, b) => {
    if (a.category === otherLabel) return 1;
    if (b.category === otherLabel) return -1;
    return a.category.localeCompare(b.category);
  });
  return sections;
});

const isModalOpen = ref(false);
const selectedVideo = ref<Video>();

function openVideoModal(video: Video) {
  selectedVideo.value = video;
  isModalOpen.value = true;
}
</script>
