<!-- HomeHero.vue — Asosiy sahifa hero paneli (§7).
     Navy gradient + oltin border/halo + girih tekstura + shahar silueti (line-art)
     + poyezd rasmi + marshrut progress (o'tilgan/joriy pulsatsiya/kelasi). -->
<template>
  <div
    class="relative flex min-h-[260px] flex-col justify-between overflow-hidden rounded-[20px] border-2 border-(--accent-gold) p-[26px_28px] text-white"
    style="
      background: linear-gradient(150deg, #16265e, #0e1b45);
      box-shadow: var(--shadow-gold-halo), 0 18px 44px rgba(14, 27, 69, 0.25);
    "
  >
    <!-- Girih tekstura -->
    <div
      class="pointer-events-none absolute inset-0"
      style="
        background:
          repeating-conic-gradient(from 45deg, rgba(255, 255, 255, 0.05) 0 25%, transparent 0 50%),
          repeating-linear-gradient(135deg, rgba(232, 200, 122, 0.06) 0 10px, transparent 10px 22px);
        background-size: 56px 56px, auto;
      "
    />
    <!-- Shahar silueti (line-art SVG) -->
    <svg
      viewBox="0 0 520 170"
      preserveAspectRatio="xMinYMax meet"
      class="pointer-events-none absolute bottom-0 left-[8px] z-3 max-h-[72%] w-[64%] opacity-55"
    >
      <g fill="none" stroke="rgba(150,180,245,.55)" stroke-width="1.6">
        <path d="M20 170 V70 l8-16 8 16 V170" />
        <path d="M14 70 h28" />
        <path d="M70 170 V96 h70 V170" />
        <path d="M70 96 a35 35 0 0 1 70 0" />
        <path d="M105 61 v-14 m-5 7 h10" />
        <path d="M160 170 V84 h56 V170" />
        <path d="M160 118 h56" />
        <path d="M188 84 v-20 m-8 20 a8 12 0 0 1 16 0" />
        <path d="M240 170 V100 a30 42 0 0 1 60 0 V170" />
        <path d="M270 58 v-12" />
        <path d="M330 170 V80 l7-14 7 14 V170" />
      </g>
    </svg>
    <!-- O'ng-tepa romb ornament -->
    <div class="pointer-events-none absolute right-[22px] top-[22px] z-2 opacity-85">
      <div
        class="flex h-[34px] w-[34px] rotate-45 items-center justify-center border-[1.5px] border-[rgba(232,200,122,.6)]"
      >
        <div
          class="h-[16px] w-[16px] border-[1.5px] border-[rgba(232,200,122,.5)] bg-[rgba(232,200,122,.14)]"
        />
      </div>
    </div>
    <!-- Shtrix ichki hoshiya -->
    <div
      class="pointer-events-none absolute inset-[10px] z-3 rounded-[16px]"
      style="border: var(--border-gold-dash)"
    />
    <!-- Poyezd rasmi + navy parda -->
    <div class="pointer-events-none absolute bottom-[-12px] right-[-46px] z-1 w-[450px]">
      <img src="~/assets/img/train_image.png" alt="" class="block w-full" />
    </div>
    <div
      class="pointer-events-none absolute inset-0 z-2"
      style="background: linear-gradient(100deg, #14224f 40%, rgba(20, 34, 79, 0.4) 72%, transparent)"
    />

    <!-- Matn -->
    <div class="relative z-3">
      <div class="text-[11px] font-extrabold tracking-[.16em] text-(--accent-gold-light)">
        {{ heroLabel }}
      </div>
      <div class="mt-[8px] font-[Unbounded] text-[clamp(21px,2.4vw,29px)] font-semibold leading-[1.25]">
        {{ routeTitle }}
      </div>
      <div class="mt-[6px] text-[14px] text-[rgba(255,255,255,.78)]">
        <template v-if="nextStop">
          {{ $t("hero.nextStop") }}: <b class="text-white">{{ nextStop }}</b>
        </template>
        <template v-else>{{ $t("hero.enRoute") }}</template>
      </div>
    </div>

    <!-- Progress: boshlanish / joriy (pulsatsiya) / manzil -->
    <div class="relative z-3 flex max-w-[520px] flex-col gap-[8px]">
      <div class="flex items-center">
        <span class="h-[12px] w-[12px] flex-none rounded-full bg-(--accent-gold-light)" />
        <span class="h-[2px] flex-1 bg-(--accent-gold-light)" />
        <span
          class="tm-pulse h-[12px] w-[12px] flex-none rounded-full bg-(--accent-gold-light)"
        />
        <span class="h-[2px] flex-[.6] bg-[rgba(255,255,255,.3)]" />
        <span
          class="box-border h-[12px] w-[12px] flex-none rounded-full border-2 border-[rgba(255,255,255,.5)]"
        />
      </div>
      <div class="flex justify-between text-[12px] text-[rgba(255,255,255,.8)]">
        <span>{{ startLabel }}</span>
        <span class="font-extrabold text-(--accent-gold-light)">{{ currentLabel }}</span>
        <span>{{ endLabel }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TrainRoute, TrainStatus } from "~/types/app";

const props = defineProps<{
  route: TrainRoute | null;
  status: TrainStatus | null;
}>();

const stops = computed(() => props.route?.stops ?? []);
const curIdx = computed(() => {
  const arr = stops.value;
  let idx = -1;
  arr.forEach((s, i) => {
    if (s.passed) idx = i;
  });
  return idx;
});

const heroLabel = computed(
  () => props.status?.train_name || props.route?.departure || "AFROSIYOB",
);
const routeTitle = computed(() => {
  if (props.status?.route) return props.status.route;
  const r = props.route;
  return r ? `${r.departure} → ${r.destination}` : "";
});
const nextStop = computed(() => {
  const arr = stops.value;
  const i = curIdx.value;
  return i >= 0 && i + 1 < arr.length ? arr[i + 1].name : "";
});
const startLabel = computed(() => {
  const s = stops.value[0];
  return s ? `${s.name} ${s.eta || ""}`.trim() : "";
});
const endLabel = computed(() => {
  const s = stops.value[stops.value.length - 1];
  return s ? `${s.name} ${s.eta || ""}`.trim() : "";
});
const currentLabel = computed(() => {
  const s = stops.value[Math.max(0, curIdx.value)];
  return s ? s.name : "";
});
</script>

<style scoped>
.tm-pulse {
  animation: omPulse 2s infinite;
}
@keyframes omPulse {
  0%,
  100% {
    box-shadow: 0 0 0 5px rgba(201, 154, 60, 0.3);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(201, 154, 60, 0.12);
  }
}
</style>
