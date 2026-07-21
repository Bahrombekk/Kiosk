<!-- HomeHero.vue — Bosh sahifa hero (§7). Tayyor milliy banner
     (dashboard-hero.png, matnsiz toza versiya) fon; jonli matnlar bo'sh
     yuqori-chap maydonга + pastdagi 3 doira ostiga container-query (cqw) bilan
     joylanadi — har o'lchamда nisbat saqlanadi. -->
<template>
  <div class="tm-hero">
    <!-- Yuqori-chap: yorliq + sarlavha + keyingi bekat -->
    <div class="tm-hero-label">{{ heroLabel }}</div>
    <div class="tm-hero-title">{{ routeTitle }}</div>
    <div class="tm-hero-next">
      <template v-if="nextStop">
        {{ $t("hero.nextStop") }}: <b>{{ nextStop }}</b>
      </template>
      <template v-else>{{ $t("hero.enRoute") }}</template>
    </div>

    <!-- Pastdagi bekat yorliqlari (rasmdagi 3 doira ostida) -->
    <div class="tm-hero-stop tm-hero-stop--start">{{ startLabel }}</div>
    <div class="tm-hero-stop tm-hero-stop--cur">{{ currentLabel }}</div>
    <div class="tm-hero-stop tm-hero-stop--end">{{ endLabel }}</div>
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

const heroLabel = computed(() => {
  const name = props.status?.train_name || props.status?.route;
  if (name) return name;
  const r = props.route;
  return r ? `${r.departure} — ${r.destination}`.toUpperCase() : "AFROSIYOB";
});
const routeTitle = computed(() => {
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
.tm-hero {
  position: relative;
  width: 100%;
  aspect-ratio: 1672 / 941;
  border-radius: 20px;
  overflow: hidden;
  background: url("/dashboard-hero.png") center / cover no-repeat;
  color: #fff;
  container-type: inline-size;
}

/* Yuqori-chap matn bloki (poyezd o'ng yarimда, chap bo'sh) */
.tm-hero-label {
  position: absolute;
  top: 13%;
  left: 5.5%;
  font-size: 1cqw;
  font-weight: 800;
  letter-spacing: 0.16em;
  color: #e8c87a;
  white-space: nowrap;
}
.tm-hero-title {
  position: absolute;
  top: 20.5%;
  left: 5.5%;
  max-width: 44%;
  font-family: "Unbounded", sans-serif;
  font-weight: 600;
  font-size: 2.7cqw;
  line-height: 1.2;
}
.tm-hero-next {
  position: absolute;
  top: 39%;
  left: 5.5%;
  max-width: 44%;
  font-size: 1.35cqw;
  color: rgba(255, 255, 255, 0.85);
}
.tm-hero-next b {
  color: #fff;
  font-weight: 800;
}

/* Pastdagi bekat yorliqlari — rasmdagi doiralar ostida (≈13.5% / 50% / 86%) */
.tm-hero-stop {
  position: absolute;
  bottom: 4.2%;
  transform: translateX(-50%);
  font-size: 1.1cqw;
  font-weight: 700;
  white-space: nowrap;
  color: rgba(255, 255, 255, 0.85);
}
.tm-hero-stop--start {
  left: 13.5%;
}
.tm-hero-stop--cur {
  left: 50%;
  color: #e8c87a;
  font-weight: 800;
}
.tm-hero-stop--end {
  left: 86%;
}
</style>
