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
      context="pre"
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

// Nuxt-kontekstga bog'liq composable'lar (useFetch/useState/useStats/useAds)
// HAR QANDAY `await` dan OLDIN chaqiriladi. SPA (ssr:false) rejimda await'dan
// KEYIN chaqirilsa Nuxt konteksti yo'qoladi — reklama ma'lumoti yuklanmay,
// media (pre-roll) reklama umuman chiqmas edi.
const moviesReq = useFetch<Video[]>("/api/movies");
const { mediaAds, ready } = useAds();
const prerollIdx = useState("ad-preroll-idx", () => 0);
const { track } = useStats();
const { data: videos, error: fetchError, refresh } = moviesReq;

// Ikkala fetch tugashini kutamiz (movies + reklama/sozlamalar) — pre-roll
// qarori quyida render'dan OLDIN, BIR MARTA qabul qilinadi.
await moviesReq;
await ready;

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

// Pre-roll reklama holati (qaror quyida — reklama/sozlamalar allaqachon
// yuklangan: yuqorida composable'lar await'dan oldin chaqirilib kutildi).
const prerollAd = ref<Ad | null>(null);
const prerollDone = ref(false);

// Kontent ochilishi statistikaga (admin "Eng ko'p ochilgan kontent") — bir marta
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

// Pre-roll — 'media' joylashuvига belgilangan reklamalardан (endi global
// algoritmga bog'liq emas; har reklama o'zi tanlaydi).
if (!isAudio.value && video.value && mediaAds.value.length) {
  prerollAd.value =
    mediaAds.value[prerollIdx.value % mediaAds.value.length] ?? null;
  prerollIdx.value = prerollIdx.value + 1;
}
</script>

<style lang="scss">
.full-screen-page {
  padding: 0;
  overflow: hidden;
}
</style>
