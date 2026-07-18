<template>
  <div class="grid grid-cols-1 gap-[24px] md:grid-cols-2">
    <div
      class="h-full rounded-[24px] bg-(--surface-bg) p-[20px] shadow-[0_8px_32px_rgba(0,0,0,0.05)]"
    >
      <div class="grid grid-cols-[64px_auto] gap-[16px] md:max-lg:grid-cols-1">
        <div
          class="flex h-[64px] w-[64px] items-center justify-center rounded-[10px] bg-(--tertiary-bg)"
        >
          <img
            src="~/assets/img/speed.png"
            alt="Tezlik"
            class="h-[64px] w-[64px]"
          />
        </div>
        <div class="flex flex-col gap-[4px] overflow-hidden text-ellipsis">
          <p class="m-0 overflow-hidden text-ellipsis text-[1.5rem]">
            {{ $t("speed") }}
          </p>
          <p class="m-0 text-[1rem] text-(--text-secondary)">{{ speedText }}</p>
        </div>
      </div>
    </div>
    <div
      class="h-full rounded-[24px] bg-(--surface-bg) p-[20px] shadow-[0_8px_32px_rgba(0,0,0,0.05)]"
    >
      <div class="grid grid-cols-[64px_auto] gap-[16px] md:max-lg:grid-cols-1">
        <div
          class="flex h-[64px] w-[64px] items-center justify-center rounded-[10px] bg-(--tertiary-bg)"
        >
          <img
            src="~/assets/img/temperature.png"
            alt="Harorat"
            class="h-[64px] w-[64px]"
          />
        </div>
        <div class="flex flex-col gap-[4px] overflow-hidden text-ellipsis">
          <p class="m-0 overflow-hidden text-ellipsis text-[1.5rem]">
            {{ $t("temperature") }}
          </p>
          <p class="m-0 text-[1rem] text-(--text-secondary)">{{ tempText }}</p>
        </div>
      </div>
    </div>
  </div>
  <div
    class="h-full rounded-[24px] bg-(--surface-bg) p-[20px] shadow-[0_8px_32px_rgba(0,0,0,0.05)]"
  >
    <div class="grid grid-cols-[64px_auto] gap-[16px]">
      <div
        class="flex h-[64px] w-[64px] items-center justify-center rounded-[10px] bg-(--tertiary-bg)"
      >
        <img
          src="~/assets/img/seat_location.png"
          alt="Joylashuv"
          class="h-[64px] w-[64px]"
        />
      </div>
      <div class="flex flex-col gap-[4px]">
        <p class="m-0 text-[1.5rem]">{{ $t("seatPlacement") }}: {{ wagonText }}</p>
        <p v-if="status?.wagon_note" class="m-0 text-[1rem] text-(--text-secondary)">
          {{ status.wagon_note }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TrainStatus } from "~/types/app";

const { t } = useI18n();

// Poyezd holati — serverdan olinadi va har 5 soniyada yangilanadi
// (tezlik/harorat/joriy bekat jonli o'zgaradi).
const { data: status, refresh } = await useFetch<TrainStatus>("/api/status");

let timer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  timer = setInterval(refresh, 5000);
});
onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});

const speedText = computed(() =>
  status.value ? `${status.value.speed} km/h` : "—",
);
const tempText = computed(() => {
  if (!status.value) return "—";
  const tVal = status.value.temperature;
  return `${tVal >= 0 ? "+" : ""}${tVal}°C`;
});
const wagonText = computed(() =>
  status.value?.wagon ? `${status.value.wagon}-${t("wagon")}` : "—",
);
</script>
