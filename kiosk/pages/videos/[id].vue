<template>
  <!-- Musiqa (audio) -> playlist'li audio pleyer -->
  <AudioPlayer
    v-if="isAudio"
    :playlist="audioPlaylist"
    :start-index="startIndex"
    :back-to="{ name: 'videos' }"
  />
  <!-- Kino/multfilm: media algoritmida kino oldidan reklama (pre-roll), so'ng pleyer -->
  <template v-else-if="video">
    <AdOverlay
      v-if="prerollAd && !prerollDone"
      :ad="prerollAd"
      @done="prerollDone = true"
    />
    <VideoPlayer v-else :video="video" />
  </template>
  <!-- Backend'ga ulanib bo'lmadi — "media yo'q" degan chalg'ituvchi xabar
       o'rniga aniq aloqa xatosi + qayta urinish -->
  <div
    v-else-if="fetchError"
    class="grid h-dvh place-items-center bg-black text-white"
  >
    <FetchErrorState @retry="refresh" />
  </div>
  <div v-else class="grid h-dvh place-items-center bg-black text-white">
    {{ $t("mediaUnavailable") }}
  </div>
</template>

<script setup lang="ts">
import VideoPlayer from "~/components/views/videos/details/VideoPlayer.vue";
import type { Ad, AudioTrack, Video } from "~/types/app";

definePageMeta({
  layout: false,
});
useHead({
  bodyAttrs: {
    class: "full-screen-page",
  },
});

const route = useRoute();
const {
  data: videos,
  error: fetchError,
  refresh,
} = await useFetch<Video[]>("/api/movies");
const video = computed(() =>
  videos.value?.find((item) => item.id === Number(route.params.id)),
);

// Musiqa audio faylmi? (kiosk: type==music + audio kengaytma -> audio pleyer)
const isAudio = computed(() =>
  (video.value?.mediaType || "").startsWith("audio/"),
);

// Playlist = joriy ko'rinishdagi barcha audio-musiqalar (avto-navbat uchun)
const audioPlaylist = computed<AudioTrack[]>(() =>
  (videos.value ?? [])
    .filter((v) => (v.mediaType || "").startsWith("audio/"))
    .map((v) => ({
      id: v.id,
      title: v.name,
      subtitle: v.genres.join(", "),
      cover: v.image.original,
      src: v.mediaUrl || "",
    })),
);
const startIndex = computed(() =>
  Math.max(
    0,
    audioPlaylist.value.findIndex((t) => t.id === Number(route.params.id)),
  ),
);

// Pre-roll reklama (faqat ad_algorithm="media" va kino/multfilm uchun).
// Qaror render'dan OLDIN, BIR MARTA qabul qilinadi: avval `watch` ishlatilgan
// edi — reklama ma'lumoti kech kelsa, allaqachon boshlangan video o'chirilib
// reklamadan keyin 0:00 dan qayta boshlanardi (poyga).
const { popupAds, algorithm, ready } = useAds();
await ready;

const prerollIdx = useState("ad-preroll-idx", () => 0);
const prerollAd = ref<Ad | null>(null);
const prerollDone = ref(false);

// Kontent ochilishi statistikaga (admin "Eng ko'p ochilgan kontent") — bir marta
const { track } = useStats();
let opened = false;
watchEffect(() => {
  if (video.value && !opened) {
    opened = true;
    track("content_open", {
      content_id: video.value.id,
      title: video.value.name,
      type: video.value.type,
    });
  }
});

if (
  algorithm.value === "media" &&
  !isAudio.value &&
  video.value &&
  popupAds.value.length
) {
  prerollAd.value =
    popupAds.value[prerollIdx.value % popupAds.value.length] ?? null;
  prerollIdx.value = prerollIdx.value + 1;
}
</script>

<style lang="scss">
.full-screen-page {
  padding: 0;
  overflow: hidden;
}
</style>
