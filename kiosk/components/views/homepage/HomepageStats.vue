<!-- HomepageStats.vue — 3 stat karta (§8): tezlik / harorat / vagon.
     Oq karta, label + Unbounded qiymat (rangli) + izoh; o'ngda oltin-tus ikonka. -->
<template>
  <div class="grid grid-cols-[repeat(auto-fit,minmax(130px,1fr))] gap-[14px]">
    <div v-for="c in cards" :key="c.key" class="tm-stat">
      <img :src="c.icon" alt="" class="tm-stat-icon" />
      <span class="text-[10px] font-extrabold tracking-[.1em] text-(--text-secondary)">
        {{ c.label }}
      </span>
      <span class="font-[Unbounded] text-[22px] font-bold" :style="{ color: c.color }">
        {{ c.value }}
      </span>
      <span class="text-[11px] text-(--text-secondary)">{{ c.note }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TrainStatus } from "~/types/app";
import speedIcon from "~/assets/img/speed.png";
import tempIcon from "~/assets/img/temperature.png";
import seatIcon from "~/assets/img/seat_location.png";

const { t } = useI18n();
const { data: status, refresh } = await useFetch<TrainStatus>("/api/status");

let timer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  timer = setInterval(refresh, 5000);
});
onBeforeUnmount(() => timer && clearInterval(timer));

const cards = computed(() => {
  const s = status.value;
  const temp = s?.temperature;
  return [
    {
      key: "speed",
      label: t("speed"),
      value: s ? String(s.speed) : "—",
      note: t("hero.kmh"),
      icon: speedIcon,
      color: "#1445a7",
    },
    {
      key: "temp",
      label: t("temperature"),
      value:
        typeof temp === "number" ? `${temp >= 0 ? "+" : ""}${temp}°` : "—",
      note: t("hero.salon"),
      icon: tempIcon,
      color: "#14939b",
    },
    {
      key: "wagon",
      label: t("wagon").toUpperCase(),
      value: s?.wagon ? String(s.wagon) : "—",
      note: s?.wagon_note || t("hero.wagonNote"),
      icon: seatIcon,
      color: "#c99a3c",
    },
  ];
});
</script>

<style scoped>
.tm-stat {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--surface-bg);
  border-radius: 20px;
  padding: 16px;
  box-shadow: var(--shadow-card);
}
.tm-stat-icon {
  position: absolute;
  top: 50%;
  right: 10px;
  transform: translateY(-50%);
  width: 46px;
  height: 46px;
  opacity: 0.55;
  filter: grayscale(1) sepia(1) saturate(3) hue-rotate(-8deg);
}
</style>
