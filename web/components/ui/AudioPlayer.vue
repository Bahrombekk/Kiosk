<template>
  <div
    class="relative flex h-dvh flex-col overflow-hidden text-white"
    style="background: linear-gradient(150deg, #16265e, #0e1b45)"
  >
    <!-- Girih tekstura -->
    <div
      class="pointer-events-none absolute inset-0"
      style="
        background: repeating-conic-gradient(from 45deg, rgba(255, 255, 255, 0.04) 0 25%, transparent 0 50%);
        background-size: 56px 56px;
      "
    />
    <UButton
      :to="backTo"
      icon="i-lucide-arrow-left"
      variant="soft"
      size="xl"
      class="absolute top-[20px] left-[24px] z-10 rounded-[12px]"
      :ui="{
        base: 'bg-white/15 backdrop-blur-lg text-white active:bg-white/25 hover:bg-white/25',
      }"
    >
      {{ $t("back") }}
    </UButton>

    <div
      class="relative z-1 mx-auto flex h-full w-full max-w-[680px] flex-col items-center justify-center gap-[24px] px-[24px] py-[32px]"
    >
      <MediaPoster
        :src="track.cover"
        :background-src="track.cover"
        :alt="track.title"
        frame-class="h-[250px] w-[190px] rounded-[18px] p-[18px]"
        image-class="z-2 h-full w-full rounded-[8px] border border-white/50 object-cover"
      />

      <div class="text-center">
        <h1 class="m-0 text-[2rem] font-semibold md:text-[2.625rem]">
          {{ track.title }}
        </h1>
        <p
          v-if="track.subtitle"
          class="m-0 mt-[4px] text-[1.25rem] font-semibold text-white/60"
        >
          {{ track.subtitle }}
        </p>
        <p v-if="audioError" class="m-0 mt-[8px] text-[1rem] text-red-300">
          {{ $t("mediaUnavailable") }}
        </p>
      </div>

      <!-- Progress -->
      <div class="w-full max-w-[560px]">
        <div class="relative h-[18px]">
          <div
            class="absolute top-1/2 left-0 h-[6px] -translate-y-1/2 rounded-full bg-(--accent-gold)"
            :style="{ width: `${progressPercent}%` }"
          />
          <input
            class="absolute inset-0 h-full w-full cursor-pointer appearance-none bg-transparent [&::-moz-range-thumb]:h-[18px] [&::-moz-range-thumb]:w-[18px] [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-(--accent-gold) [&::-webkit-slider-runnable-track]:h-[6px] [&::-webkit-slider-runnable-track]:rounded-full [&::-webkit-slider-runnable-track]:bg-white/20 [&::-webkit-slider-thumb]:mt-[-6px] [&::-webkit-slider-thumb]:h-[18px] [&::-webkit-slider-thumb]:w-[18px] [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-(--accent-gold)"
            type="range"
            min="0"
            :max="duration || 0"
            step="0.1"
            :value="currentTime"
            aria-label="Progress"
            @pointerdown="scrubbing = true"
            @pointerup="scrubbing = false"
            @input="onScrubInput"
            @change="seekTo"
          />
        </div>
        <div
          class="mt-[6px] flex justify-between text-[0.875rem] text-white/55"
        >
          <span>{{ formatTime(currentTime) }}</span>
          <span>{{ formatTime(duration) }}</span>
        </div>
      </div>

      <!-- Controls -->
      <div class="flex items-center gap-[24px]">
        <UButton
          v-if="hasPlaylist"
          icon="i-lucide-skip-back"
          color="neutral"
          variant="ghost"
          size="xl"
          class="rounded-full text-white"
          aria-label="Previous"
          @click="prev"
        />
        <UButton
          icon="i-lucide-rotate-ccw"
          color="neutral"
          label="10s"
          variant="ghost"
          size="xl"
          class="rounded-full text-white"
          aria-label="Back 10 seconds"
          @click="seekBy(-10)"
        />
        <UButton
          :icon="isPlaying ? 'i-fa7-solid-pause' : 'i-fa7-solid-play'"
          size="xl"
          class="h-[64px] w-[64px] justify-center rounded-full"
          aria-label="Play"
          :ui="{
            base: 'bg-(--accent-gold) text-(--text-on-gold) active:bg-(--accent-gold)/70 hover:bg-(--accent-gold-light) hover:text-(--text-on-gold) shadow-[0px_8px_35px_rgba(201,154,60,0.35)]',
          }"
          @click="togglePlayback"
        />
        <UButton
          trailing-icon="i-lucide-rotate-cw"
          color="neutral"
          label="10s"
          variant="ghost"
          size="xl"
          class="rounded-full text-white"
          aria-label="Forward 10 seconds"
          @click="seekBy(10)"
        />
        <UButton
          v-if="hasPlaylist"
          icon="i-lucide-skip-forward"
          color="neutral"
          variant="ghost"
          size="xl"
          class="rounded-full text-white"
          aria-label="Next"
          @click="next"
        />
        <UButton
          color="neutral"
          variant="outline"
          class="h-[40px] min-w-[40px] justify-center rounded-full border-white/25 text-white hover:bg-white/10"
          @click="cycleSpeed"
        >
          {{ playbackRate }}x
        </UButton>
      </div>
    </div>

    <audio
      v-if="track.src"
      ref="audioRef"
      :src="track.src"
      autoplay
      preload="metadata"
      @loadedmetadata="onLoadedMeta"
      @timeupdate="onTimeUpdate"
      @ended="onEnded"
      @error="onError"
      @play="isPlaying = true"
      @pause="isPlaying = false"
    />
  </div>
</template>

<script setup lang="ts">
import type { AudioTrack } from "~/types/app";
import type { RouteLocationRaw } from "vue-router";

const props = withDefaults(
  defineProps<{
    // Bitta trek (audiokitob) uchun:
    cover?: string;
    title?: string;
    subtitle?: string;
    src?: string;
    // Playlist (musiqa) uchun — berilsa shu ishlatiladi:
    playlist?: AudioTrack[];
    startIndex?: number;
    backTo?: RouteLocationRaw;
  }>(),
  { startIndex: 0, backTo: () => "/" },
);

const audioRef = ref<HTMLAudioElement | null>(null);
const isPlaying = ref(false);
const currentTime = ref(0);
const duration = ref(0);
const playbackRate = ref(1);
const speeds = [1, 1.25, 1.5, 2];
const scrubbing = ref(false); // barmoq slayderda — timeupdate uni bosib yozmasin
const audioError = ref(false);
let consecutiveErrors = 0; // butun playlist buzuq bo'lsa cheksiz aylanmaslik uchun

const hasPlaylist = computed(() => (props.playlist?.length ?? 0) > 0);
const currentIndex = ref(props.startIndex);

// startIndex mount'dan keyin o'zgarsa (boshqa trek tanlansa) sinxronlaymiz
watch(
  () => props.startIndex,
  (i) => {
    currentIndex.value = i;
  },
);

const track = computed<AudioTrack>(() => {
  if (hasPlaylist.value) {
    return (
      props.playlist![currentIndex.value] ??
      props.playlist![0]
    );
  }
  return {
    id: 0,
    title: props.title || "",
    subtitle: props.subtitle,
    cover: props.cover || "",
    src: props.src || "",
  };
});

const progressPercent = computed(() =>
  duration.value ? (currentTime.value / duration.value) * 100 : 0,
);

const formatTime = (value: number) => {
  if (!Number.isFinite(value)) return "0:00";
  const m = Math.floor(value / 60);
  const s = Math.floor(value % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
};

function onLoadedMeta() {
  duration.value = audioRef.value?.duration || 0;
  if (audioRef.value) audioRef.value.playbackRate = playbackRate.value;
}
function onTimeUpdate() {
  // Scrub paytida thumb barmoq ostidan sakramasin
  if (!scrubbing.value) currentTime.value = audioRef.value?.currentTime || 0;
}
function onScrubInput(event: Event) {
  currentTime.value = Number((event.target as HTMLInputElement).value);
}
function togglePlayback() {
  const a = audioRef.value;
  if (!a) return;
  if (a.paused) a.play();
  else a.pause();
}
function seekBy(seconds: number) {
  const a = audioRef.value;
  if (!a) return;
  a.currentTime = Math.min(
    Math.max(a.currentTime + seconds, 0),
    duration.value || a.currentTime,
  );
}
function seekTo(event: Event) {
  const a = audioRef.value;
  if (!a) return;
  a.currentTime = Number((event.target as HTMLInputElement).value);
}
function cycleSpeed() {
  const i = speeds.indexOf(playbackRate.value);
  playbackRate.value = speeds[(i + 1) % speeds.length] ?? 1;
  if (audioRef.value) audioRef.value.playbackRate = playbackRate.value;
}
function prev() {
  if (!hasPlaylist.value) return;
  const n = props.playlist!.length;
  currentIndex.value = (currentIndex.value - 1 + n) % n;
}
function next() {
  if (!hasPlaylist.value) return;
  const n = props.playlist!.length;
  currentIndex.value = (currentIndex.value + 1) % n;
}
function onEnded() {
  consecutiveErrors = 0;
  // Musiqa: avto-navbat (keyingi trek). Bitta trek: shunchaki to'xtaydi.
  if (hasPlaylist.value) next();
}
function onError() {
  // Buzuq/404 trek avto-navbatni jim o'ldirmasin: playlist'da keyingisiga
  // o'tamiz; hammasi buzuq bo'lsa (yoki yakka trek) xato xabari ko'rsatiladi.
  audioError.value = true;
  const n = props.playlist?.length ?? 0;
  consecutiveErrors++;
  if (hasPlaylist.value && n > 1 && consecutiveErrors < n) {
    next();
  }
}

// Trek manbasi o'zgarsa (playlist'da keyingiga o'tilsa) — qayta yuklab o'ynatamiz
watch(
  () => track.value.src,
  (src) => {
    audioError.value = !src; // bo'sh src — darhol "media mavjud emas"
    if (!src) return;
    audioError.value = false;
    nextTick(() => {
      const a = audioRef.value;
      if (!a) return;
      a.load();
      a.playbackRate = playbackRate.value;
      a.play().catch(() => {
        isPlaying.value = false; // autoplay bloklandi — play tugmasi ko'rinsin
      });
    });
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  audioRef.value?.pause();
});
</script>
