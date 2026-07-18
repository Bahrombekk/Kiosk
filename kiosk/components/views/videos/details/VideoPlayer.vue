<template>
  <!-- mediaUrl yo'q — xato holati; avval birga keladigan demo klip
       (/videos/video.mp4) jimgina o'ynab, foydalanuvchini chalg'itardi -->
  <div
    v-if="!video.mediaUrl"
    class="grid h-dvh place-items-center bg-black text-white"
  >
    {{ $t("mediaUnavailable") }}
  </div>
  <!-- media-player is the fullscreen target, so all overlay controls must live inside it -->
  <media-player
    v-else
    ref="playerRef"
    class="aspect-auto! relative h-dvh w-full touch-none overflow-hidden bg-black text-white"
    :src="mediaSrc"
    :title="video.name"
    :playsInline="true"
    preload="metadata"
    fullscreenOrientation="landscape"
    keyTarget="document"
    :keyShortcuts="keyShortcuts"
    @play="handlePlay"
    @pause="isPlaying = false"
    @ended="isPlaying = false"
    @time-update="handleTimeUpdate"
    @duration-change="handleDurationChange"
    @volume-change="handleVolumeChange"
    @fullscreen-change="handleFullscreenChange"
    @mousemove="handleActivity"
    @touchstart="handleActivity"
  >
    <media-provider />

    <!-- Poster shown until the user starts playback, mirrors native <video poster> behaviour -->
    <img
      v-if="!hasStarted"
      :src="video.image.original"
      :alt="video.name"
      class="pointer-events-none absolute inset-0 h-full w-full bg-black object-contain"
    />

    <!-- Double-tap zones for mobile seek (left = -10s, right = +10s); a safe
    middle band avoids conflicts with the centered play/skip buttons.
    O'zimizning dbl-tap logikamiz — seek HAM, flash feedback HAM birga ishlaydi
    (avval media-gesture seek qilar, flashSeek esa hech qachon chaqirilmasdi) -->
    <div class="absolute inset-0 flex">
      <div class="h-full basis-[40%]" @pointerup="onZoneTap('back')" />
      <div class="h-full basis-[20%]" />
      <div class="h-full basis-[40%]" @pointerup="onZoneTap('forward')" />
    </div>

    <!-- Visual feedback for the double-tap seek gesture -->
    <Transition name="fade">
      <div
        v-if="seekFlash"
        class="pointer-events-none absolute inset-y-0 flex w-2/5 items-center justify-center"
        :class="seekFlash === 'back' ? 'left-0' : 'right-0'"
      >
        <div
          class="flex flex-col items-center gap-1 rounded-full bg-black/55 px-6 py-4 text-white backdrop-blur-sm"
        >
          <Icon
            :name="
              seekFlash === 'back'
                ? 'i-lucide-rotate-ccw'
                : 'i-lucide-rotate-cw'
            "
            class="size-7"
          />
          <span class="text-xs font-medium">10s</span>
        </div>
      </div>
    </Transition>

    <!-- Back Button with conditional visibility class -->
    <UButton
      :to="{ name: 'videos' }"
      icon="i-lucide-arrow-left"
      variant="soft"
      size="xl"
      :ui="{
        base: 'bg-blue-600/15 backdrop-blur-lg text-(--brand-base) active:bg-(--brand-base) active:text-white hover:bg-(--brand-base) hover:text-white',
      }"
      class="absolute top-[20px] left-[24px] z-10 rounded-[12px] transition-opacity duration-300"
      :class="[
        areControlsVisible
          ? 'opacity-100 pointer-events-auto'
          : 'opacity-0 pointer-events-none',
      ]"
    >
      {{ $t("back") }}
    </UButton>

    <!-- Centered Playback Controls with conditional visibility class -->
    <div
      class="pointer-events-none absolute inset-0 flex items-center justify-center transition-opacity duration-300"
      :class="[areControlsVisible ? 'opacity-100' : 'opacity-0']"
    >
      <div
        class="flex items-center gap-[28px]"
        :class="[
          areControlsVisible ? 'pointer-events-auto' : 'pointer-events-none',
        ]"
      >
        <UButton
          icon="i-lucide-rotate-ccw"
          color="neutral"
          variant="soft"
          size="xl"
          class="h-[56px] w-[56px] justify-center rounded-full bg-black/55 text-white backdrop-blur-sm hover:bg-black/70"
          aria-label="Back 10 seconds"
          @click="seekBy(-10)"
        />
        <UButton
          :icon="isPlaying ? 'i-fa7-solid-pause' : 'i-fa7-solid-play'"
          size="xl"
          :ui="{
            base: 'bg-(--brand-base) active:bg-(--brand-base)/50 active:text-white hover:bg-(--brand-base)/50 hover:text-white',
          }"
          class="h-[72px] w-[72px] justify-center rounded-full shadow-xl"
          :aria-label="isPlaying ? 'Pause' : 'Play'"
          @click="togglePlayback"
        />
        <UButton
          icon="i-lucide-rotate-cw"
          color="neutral"
          variant="soft"
          size="xl"
          class="h-[56px] w-[56px] justify-center rounded-full bg-black/55 text-white backdrop-blur-sm hover:bg-black/70"
          aria-label="Forward 10 seconds"
          @click="seekBy(10)"
        />
      </div>
    </div>

    <!-- Bottom Progress/Volume Controls with conditional visibility class -->
    <div
      class="absolute right-0 bottom-0 left-0 z-10 bg-linear-to-t from-black/90 to-transparent px-[24px] pt-[56px] pb-[24px] transition-opacity duration-300"
      :class="[
        areControlsVisible
          ? 'opacity-100 pointer-events-auto'
          : 'opacity-0 pointer-events-none',
      ]"
    >
      <div class="flex items-center gap-[16px]">
        <span class="min-w-[44px] text-sm tabular-nums">
          {{ formatTime(currentTime) }}
        </span>
        <div class="relative h-[18px] flex-1">
          <div
            class="absolute top-1/2 left-0 h-[6px] -translate-y-1/2 rounded-full bg-(--brand-base)"
            :style="{ width: `${progressPercent}%` }"
          />
          <input
            class="absolute inset-0 h-full w-full cursor-pointer appearance-none bg-transparent [&::-moz-range-thumb]:h-[18px] [&::-moz-range-thumb]:w-[18px] [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-white [&::-webkit-slider-runnable-track]:h-[6px] [&::-webkit-slider-runnable-track]:rounded-full [&::-webkit-slider-runnable-track]:bg-white/25 [&::-webkit-slider-thumb]:mt-[-6px] [&::-webkit-slider-thumb]:h-[18px] [&::-webkit-slider-thumb]:w-[18px] [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white"
            type="range"
            min="0"
            :max="duration || 0"
            step="0.1"
            :value="currentTime"
            aria-label="Video progress"
            @pointerdown="scrubbing = true"
            @pointerup="scrubbing = false"
            @input="onScrubInput"
            @change="seekTo"
          />
        </div>
        <span class="min-w-[44px] text-sm tabular-nums">
          {{ formatTime(duration) }}
        </span>

        <UButton
          :icon="volumeIcon"
          color="neutral"
          variant="ghost"
          class="rounded-full text-white hover:bg-white/15"
          :aria-label="isMuted ? 'Unmute' : 'Mute'"
          @click="toggleMute"
        />
        <div class="relative hidden h-[18px] w-[120px] landscape:block">
          <div
            class="absolute top-1/2 left-0 h-[6px] -translate-y-1/2 rounded-full bg-white"
            :style="{ width: `${volumePercent}%` }"
          />
          <input
            class="absolute inset-0 h-full w-full cursor-pointer appearance-none bg-transparent [&::-moz-range-thumb]:h-[16px] [&::-moz-range-thumb]:w-[16px] [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:rounded-full [&::-xaxis-range-thumb]:border-0 [&::-moz-range-thumb]:bg-white [&::-webkit-slider-runnable-track]:h-[6px] [&::-webkit-slider-runnable-track]:rounded-full [&::-webkit-slider-runnable-track]:bg-white/25 [&::-webkit-slider-thumb]:mt-[-5px] [&::-webkit-slider-thumb]:h-[16px] [&::-webkit-slider-thumb]:w-[16px] [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white"
            type="range"
            min="0"
            max="1"
            step="0.01"
            :value="isMuted ? 0 : volume"
            aria-label="Volume"
            @input="setVolume"
          />
        </div>

        <UButton
          :icon="isFullscreen ? 'i-lucide-minimize' : 'i-lucide-maximize'"
          color="neutral"
          variant="ghost"
          class="rounded-full text-white hover:bg-white/15"
          :aria-label="isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'"
          @click="toggleFullscreen"
        />
      </div>
    </div>
  </media-player>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from "vue";
import type { Video } from "~/types/app";
import type { MediaKeyShortcuts } from "vidstack";
import type { MediaPlayerElement } from "vidstack/elements";
import "vidstack/player";
import "vidstack/player/ui";
import "vidstack/player/styles/base.css";

const props = defineProps<{
  video: Video;
}>();

const playerRef = ref<MediaPlayerElement | null>(null);
const isPlaying = ref(false);
const currentTime = ref(0);
const duration = ref(0);
const volume = ref(1);
const isMuted = ref(false);
const isFullscreen = ref(false);
const hasStarted = ref(false);
const seekFlash = ref<"back" | "forward" | null>(null);
let seekFlashTimeout: NodeJS.Timeout | null = null;

// Visibility state and timer refs
const areControlsVisible = ref(true);
let activityTimeout: NodeJS.Timeout | null = null;

const source = computed(() => props.video.mediaUrl || "");
const scrubbing = ref(false); // barmoq slayderda — timeupdate bosib yozmasin
const mediaSrc = computed(() =>
  props.video.mediaType
    ? { src: source.value, type: props.video.mediaType }
    : source.value,
);
const progressPercent = computed(() =>
  duration.value ? (currentTime.value / duration.value) * 100 : 0,
);
const volumePercent = computed(() => (isMuted.value ? 0 : volume.value * 100));
const volumeIcon = computed(() => {
  if (isMuted.value || volume.value === 0) return "i-lucide-volume-x";
  if (volume.value < 0.5) return "i-lucide-volume-1";
  return "i-lucide-volume-2";
});

// Resets timer on activity and ensures controls are visible
const handleActivity = () => {
  areControlsVisible.value = true;

  if (activityTimeout) {
    clearTimeout(activityTimeout);
  }

  // Only hide if the video is actually playing
  if (isPlaying.value) {
    activityTimeout = setTimeout(() => {
      areControlsVisible.value = false;
    }, 3000); // Hides after 3 seconds of inactivity
  }
};

// Keep controls up if the user pauses the video
watch(isPlaying, (playing) => {
  handleActivity();
  if (!playing && activityTimeout) {
    clearTimeout(activityTimeout);
  }
});

const formatTime = (value: number) => {
  if (!Number.isFinite(value)) return "0:00";

  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
};

const handlePlay = () => {
  isPlaying.value = true;
  hasStarted.value = true;
};

const handleTimeUpdate = (event: CustomEvent<{ currentTime: number }>) => {
  if (!scrubbing.value) currentTime.value = event.detail.currentTime;
};

const onScrubInput = (event: Event) => {
  handleActivity();
  currentTime.value = Number((event.target as HTMLInputElement).value);
};

const handleDurationChange = (event: CustomEvent<number>) => {
  duration.value = event.detail || 0;
};

const handleVolumeChange = (
  event: CustomEvent<{ volume: number; muted: boolean }>,
) => {
  volume.value = event.detail.volume;
  isMuted.value = event.detail.muted;
};

const handleFullscreenChange = (event: CustomEvent<boolean>) => {
  isFullscreen.value = event.detail;
};

// Double-tap seek: flash feedback + haqiqiy seek birgalikda.
const flashSeek = (side: "back" | "forward") => {
  handleActivity();

  if (seekFlashTimeout) clearTimeout(seekFlashTimeout);
  seekFlash.value = side;
  seekFlashTimeout = setTimeout(() => {
    seekFlash.value = null;
  }, 500);
};

// Zonalarga ikki marta tez teginish (300ms ichida) — ±10s seek + flash.
const lastTap: Record<string, number> = { back: 0, forward: 0 };
const onZoneTap = (side: "back" | "forward") => {
  handleActivity();
  const now = Date.now();
  if (now - lastTap[side] < 300) {
    lastTap[side] = 0;
    seekBy(side === "back" ? -10 : 10);
    flashSeek(side);
  } else {
    lastTap[side] = now;
  }
};

onUnmounted(() => {
  // Taymerlar unmount'dan keyin ishlab qolmasin (leak edi)
  if (seekFlashTimeout) clearTimeout(seekFlashTimeout);
  if (activityTimeout) clearTimeout(activityTimeout);
});

const togglePlayback = async () => {
  if (!playerRef.value) return;

  // Let tap/click events handle visibility lifecycle seamlessly
  handleActivity();

  if (playerRef.value.paused) {
    await playerRef.value.play();
  } else {
    await playerRef.value.pause();
  }
};

const seekBy = (seconds: number) => {
  if (!playerRef.value) return;
  handleActivity();

  playerRef.value.currentTime = Math.min(
    Math.max(playerRef.value.currentTime + seconds, 0),
    duration.value || playerRef.value.currentTime,
  );
};

const seekTo = (event: Event) => {
  if (!playerRef.value) return;
  handleActivity();

  playerRef.value.currentTime = Number(
    (event.target as HTMLInputElement).value,
  );
};

const toggleMute = () => {
  if (!playerRef.value) return;
  handleActivity();

  playerRef.value.muted = !playerRef.value.muted;
};

const setVolume = (event: Event) => {
  if (!playerRef.value) return;
  handleActivity();

  playerRef.value.volume = Number((event.target as HTMLInputElement).value);
  playerRef.value.muted = false;
};

const adjustVolumeBy = (delta: number) => {
  if (!playerRef.value) return;
  handleActivity();

  const next = Math.min(1, Math.max(0, playerRef.value.volume + delta));
  playerRef.value.volume = next;
  if (next > 0) playerRef.value.muted = false;
};

const toggleFullscreen = async () => {
  if (!playerRef.value) return;
  handleActivity();

  if (isFullscreen.value) {
    await playerRef.value.exitFullscreen();
  } else {
    await playerRef.value.enterFullscreen();
  }
};

// Keyboard shortcuts route through the same handlers as the on-screen controls
// so activity tracking, clamping, etc. stay identical regardless of input method.
const keyShortcuts: MediaKeyShortcuts = {
  togglePaused: {
    keys: "k Space",
    onKeyDown: ({ event }) => {
      event.preventDefault();
      togglePlayback();
    },
  },
  toggleMuted: {
    keys: "m",
    onKeyDown: ({ event }) => {
      event.preventDefault();
      toggleMute();
    },
  },
  toggleFullscreen: {
    keys: "f",
    onKeyDown: ({ event }) => {
      event.preventDefault();
      toggleFullscreen();
    },
  },
  seekBackward: {
    keys: ["ArrowLeft", "j"],
    onKeyDown: ({ event }) => {
      event.preventDefault();
      seekBy(-10);
    },
  },
  seekForward: {
    keys: ["ArrowRight", "l"],
    onKeyDown: ({ event }) => {
      event.preventDefault();
      seekBy(10);
    },
  },
  volumeUp: {
    keys: "ArrowUp",
    onKeyDown: ({ event }) => {
      event.preventDefault();
      adjustVolumeBy(0.1);
    },
  },
  volumeDown: {
    keys: "ArrowDown",
    onKeyDown: ({ event }) => {
      event.preventDefault();
      adjustVolumeBy(-0.1);
    },
  },
};
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
