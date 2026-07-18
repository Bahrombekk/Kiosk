<template>
  <div
    class="mx-auto max-w-[1024px] rounded-[40px] bg-(--surface-bg) shadow-[0_8px_32px_rgba(0,0,0,0.05)] p-[16px]"
  >
    <MapsRideInfo
      :ride-info="rideInfo"
      :from="routeData?.departure"
      :to="routeData?.destination"
    />
    <MapsRouteInfo v-if="routeData" :route-info="routeData" />
  </div>
</template>

<script setup lang="ts">
import type { IconComponent, TrainRoute } from "~/types/app";
import CalendarIcon from "~/assets/svg/calendar-alt.svg";
import Clock5Icon from "~/assets/svg/clock-five.svg";
import ClockLinesIcon from "~/assets/svg/clock-lines.svg";

const { t, locale } = useI18n();

// Yo'nalish serverdan (bekatlar + joriy holat) — har 15 soniyada yangilanadi
// (joriy bekat o'zgarib borishi uchun).
const { data: routeData, refresh } = await useFetch<TrainRoute>("/api/route");
let timer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  timer = setInterval(refresh, 15000);
});
onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});

function parseHHMM(s: string): number | null {
  const m = /^(\d{1,2}):(\d{2})/.exec(s || "");
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

const rideInfo = computed<{ icon: IconComponent; label: string }[]>(() => {
  const stops = routeData.value?.stops ?? [];
  const first = stops[0]?.eta ?? "";
  const last = stops[stops.length - 1]?.eta ?? "";
  const a = parseHHMM(first);
  const b = parseHHMM(last);
  let dur = "";
  if (a !== null && b !== null) {
    let mins = b - a;
    if (mins < 0) mins += 24 * 60; // yarim tundan o'tadigan reys
    dur = `${Math.floor(mins / 60)}${t("hour_short")} ${mins % 60}${t("minutes_short")}`;
  }
  const today = new Date().toLocaleDateString(locale.value, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  return [
    { icon: CalendarIcon, label: today },
    { icon: Clock5Icon, label: `${t("departure")}: ${first}` },
    { icon: ClockLinesIcon, label: dur },
  ];
});
</script>
