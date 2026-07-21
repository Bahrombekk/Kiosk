<!-- MapsView.vue — Xarita sahifasi (§17): chapda reys paneli (sarlavha +
     4 ma'lumot katakchasi + bekatlar timeline), o'ngda oflayn vektor xarita. -->
<template>
  <div
    class="grid items-stretch gap-[18px]"
    style="grid-template-columns: repeat(auto-fit, minmax(min(380px, 100%), 1fr)); animation: omFade 0.35s ease"
  >
    <!-- Chap panel -->
    <div class="flex flex-col gap-[18px] rounded-[24px] bg-(--surface-bg) p-[26px] shadow-(--shadow-card)">
      <div>
        <div class="text-[11px] font-extrabold tracking-[.16em] text-(--accent-gold)">
          {{ routeLabel }}
        </div>
        <div class="mt-[6px] font-[Unbounded] text-[23px] font-semibold leading-[1.3] text-(--text-primary)">
          {{ routeData?.departure || "—" }} → {{ routeData?.destination || "—" }}
        </div>
      </div>

      <!-- 4 ma'lumot katakchasi -->
      <div class="grid grid-cols-2 gap-[12px]">
        <div v-for="tile in infoTiles" :key="tile.label" class="rounded-[14px] bg-(--page-bg) px-[14px] py-[12px]">
          <div class="text-[10px] font-extrabold uppercase tracking-[.1em] text-(--text-secondary)">
            {{ tile.label }}
          </div>
          <div class="mt-[4px] text-[14px] font-extrabold text-(--text-primary)">
            {{ tile.value }}
          </div>
        </div>
      </div>

      <!-- Bekatlar timeline -->
      <div class="flex flex-col">
        <div
          v-for="(stop, i) in stops"
          :key="i"
          class="grid grid-cols-[20px_1fr_auto] items-start gap-[14px]"
        >
          <div class="flex flex-col items-center self-stretch">
            <span :class="dotClass(i)" />
            <span v-if="i < stops.length - 1" :class="lineClass(i)" />
          </div>
          <div class="pb-[22px]">
            <div :class="i === curIdx ? 'text-[14px] font-extrabold text-(--brand-base)' : 'text-[14px] font-bold text-(--text-primary)'">
              {{ stop.name }}
            </div>
            <div v-if="i === curIdx" class="text-[12px] text-(--text-secondary)">
              {{ $t("hero.enRoute") }}
            </div>
          </div>
          <div
            :class="i === curIdx ? 'text-[13px] font-extrabold text-(--accent-gold)' : 'text-[13px] font-semibold text-(--text-secondary)'"
          >
            {{ stop.eta }}
          </div>
        </div>
      </div>
    </div>

    <!-- O'ng: xarita -->
    <div class="relative min-h-[480px] overflow-hidden rounded-[24px] shadow-(--shadow-card)">
      <TrainMap v-if="routeData" :route-data="routeData" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TrainRoute, TrainStatus } from "~/types/app";

const { t, locale } = useI18n();

const { data: routeData, refresh } = await useFetch<TrainRoute>("/api/route");
const { data: status } = await useFetch<TrainStatus>("/api/status", {
  default: () => null,
});

let timer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  timer = setInterval(refresh, 15000);
});
onBeforeUnmount(() => timer && clearInterval(timer));

const stops = computed(() => routeData.value?.stops ?? []);

// Joriy (oxirgi o'tilgan) bekat indeksi
const curIdx = computed(() =>
  stops.value.reduce((last, s, i) => (s.passed ? i : last), -1),
);

const routeLabel = computed(() =>
  [status.value?.train_name, status.value?.route]
    .filter(Boolean)
    .join(" · ") || t("train").toUpperCase(),
);

// Sana — toLocaleDateString ISHLATILMAYDI (Chrome uz-UZ "M07" beradi);
// har til uchun oy nomlari massivdan.
const MONTHS: Record<string, string[]> = {
  uz: ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"],
  ru: ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"],
  en: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
};

function parseHHMM(s: string): number | null {
  const m = /^(\d{1,2}):(\d{2})/.exec(s || "");
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

const infoTiles = computed(() => {
  const arr = stops.value;
  const first = arr[0]?.eta ?? "—";
  const a = parseHHMM(arr[0]?.eta ?? "");
  const b = parseHHMM(arr[arr.length - 1]?.eta ?? "");
  let dur = "—";
  if (a !== null && b !== null) {
    let mins = b - a;
    if (mins < 0) mins += 24 * 60;
    dur = `${Math.floor(mins / 60)}${t("hour_short")} ${mins % 60}${t("minutes_short")}`;
  }
  const d = new Date();
  const months = MONTHS[locale.value] || MONTHS.uz;
  const today = `${d.getDate()} ${months[d.getMonth()]}`;
  const dist = routeData.value?.totalDistanceKm
    ? `${Math.round(routeData.value.totalDistanceKm)} km`
    : "—";
  return [
    { label: t("mapInfo.date"), value: today },
    { label: t("departure"), value: first },
    { label: t("mapInfo.duration"), value: dur },
    { label: t("mapInfo.distance"), value: dist },
  ];
});

function dotClass(i: number): string {
  const base = "h-[12px] w-[12px] flex-none rounded-full";
  if (i < curIdx.value) return `${base} bg-(--brand-base)`;
  if (i === curIdx.value) return `${base} tm-dot-pulse bg-(--accent-gold)`;
  return `${base} border-2 border-(--stroke-2) bg-(--surface-bg) box-border`;
}
function lineClass(i: number): string {
  return i < curIdx.value
    ? "w-[2px] flex-1 self-stretch bg-(--brand-base)"
    : "w-[2px] flex-1 self-stretch bg-(--stroke-2)";
}
</script>

<style scoped>
.tm-dot-pulse {
  animation: omPulse 2s infinite;
}
@keyframes omPulse {
  0%,
  100% {
    box-shadow: 0 0 0 4px rgba(201, 154, 60, 0.28);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(201, 154, 60, 0.1);
  }
}
</style>
