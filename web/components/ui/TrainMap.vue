<!-- TrainMap.vue — PREMIUM oflayn vektor xarita (MapLibre GL + PMTiles).

  - Xarita ma'lumoti server oflayn PMTiles faylidan (/api/map) — internetsiz.
  - O'zbekiston chegarasi ta'kidlanadi; tashqi davlatlar yarim-shaffof qora
    "mask" bilan xiralashtiriladi (O'zbekiston yorqin ajralib turadi).
  - Marshrut HAQIQIY temir yo'l geometriyasi (/tashkent-khiva-rail.geojson)
    bo'ylab egri chiziladi; fayl bo'lmasa bekatlar orasida to'g'ri chiziq.
  - O'tilgan qism yashil, qolgani ko'k (oq casing bilan). Joriy bekat
    pulslanuvchi halqa, bekatlar chiroyli markerlar.
-->
<template>
  <div class="relative h-full min-h-[420px] w-full overflow-hidden rounded-[24px]">
    <div ref="mapEl" class="h-full w-full" />
    <div
      v-if="mapError"
      class="absolute inset-0 flex items-center justify-center bg-(--tertiary-bg) p-6 text-center text-(--text-secondary)"
    >
      {{ $t("mediaUnavailable") }}
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TrainRoute } from "~/types/app";

const props = defineProps<{ routeData: TrainRoute }>();

const mapEl = ref<HTMLElement | null>(null);
const mapError = ref(false);

let map: any = null;
let maplibregl: any = null;
let railGeo: any = null; // haqiqiy temir yo'l geometriyasi (bo'lsa)
let resizeObs: ResizeObserver | null = null;
const MARKERS: any[] = [];

const stops = computed(() => props.routeData?.stops ?? []);

function coords() {
  return stops.value
    .filter((s) => s.lat && s.lng)
    .map((s) => [s.lng, s.lat] as [number, number]);
}
function currentIdx() {
  let idx = -1;
  stops.value.forEach((s, i) => {
    if (s.passed) idx = i;
  });
  return idx;
}
function line(cs: [number, number][]) {
  return {
    type: "Feature" as const,
    geometry: { type: "LineString" as const, coordinates: cs },
    properties: {},
  };
}

// --- Marshrut geometriyasi: haqiqiy relslar bo'lsa undan, bekatlarni unga
// "yopishtirib" o'tilgan/qolgan qismga ajratamiz; bo'lmasa bekatlar bo'ylab. ---
function railLineString(): [number, number][] | null {
  if (!railGeo) return null;
  const feats = railGeo.type === "FeatureCollection" ? railGeo.features : [railGeo];
  // Eng uzun LineString'ni asosiy marshrut deb olamiz
  let best: [number, number][] = [];
  for (const f of feats) {
    const g = f.geometry;
    if (g?.type === "LineString" && g.coordinates.length > best.length) {
      best = g.coordinates;
    } else if (g?.type === "MultiLineString") {
      const flat = g.coordinates.flat();
      if (flat.length > best.length) best = flat;
    }
  }
  return best.length > 1 ? best : null;
}

function nearestIdxOnLine(lineCs: [number, number][], pt: [number, number]) {
  let bi = 0;
  let bd = Infinity;
  for (let i = 0; i < lineCs.length; i++) {
    const dx = lineCs[i][0] - pt[0];
    const dy = lineCs[i][1] - pt[1];
    const d = dx * dx + dy * dy;
    if (d < bd) {
      bd = d;
      bi = i;
    }
  }
  return bi;
}

function drawRoute() {
  if (!map || !maplibregl) return;
  const stationCs = coords();
  if (!stationCs.length) return;

  const rail = railLineString();
  const cur = currentIdx();

  let fullCs: [number, number][];
  let passedCs: [number, number][];

  if (rail) {
    // Relslar bo'ylab. O'tilgan qism = o'tilgan bekatlarning rail chizig'idagi
    // eng yaqin nuqtalari orasidagi bo'lak (min..max indeks) — bu borish HAM,
    // qaytish HAM yo'nalishida to'g'ri ishlaydi.
    fullCs = rail;
    const passedStations = stops.value.filter(
      (s) => s.passed && s.lat && s.lng,
    );
    if (passedStations.length) {
      const idxs = passedStations.map((s) =>
        nearestIdxOnLine(rail, [s.lng, s.lat]),
      );
      const lo = Math.min(...idxs);
      const hi = Math.max(...idxs);
      passedCs = rail.slice(lo, hi + 1);
    } else {
      passedCs = [];
    }
  } else {
    // Fallback: bekatlar orasida to'g'ri chiziq
    fullCs = stationCs;
    passedCs = [];
    if (cur >= 0) {
      for (let i = 0; i <= cur && i < stops.value.length; i++) {
        const s = stops.value[i];
        if (s.lat && s.lng) passedCs.push([s.lng, s.lat]);
      }
    }
  }

  ensureLine("route-casing", line(fullCs), {
    "line-color": "#ffffff",
    "line-width": 9,
    "line-opacity": 0.95,
  });
  ensureLine("route-remaining", line(fullCs), {
    "line-color": "#1445a7", // brend navy — qolgan yo'l
    "line-width": 5,
  });
  ensureLine("route-passed", line(passedCs), {
    "line-color": "#14939b", // firuza — o'tilgan yo'l
    "line-width": 5,
  });

  // Bekat markerlari
  MARKERS.forEach((m) => m.remove());
  MARKERS.length = 0;
  stops.value.forEach((s, i) => {
    if (!s.lat || !s.lng) return;
    const isCurrent = i === cur;
    const color = s.passed ? "#14939b" : "#1445a7";
    const el = document.createElement("div");
    if (isCurrent) {
      el.style.cssText =
        "width:22px;height:22px;border-radius:50%;background:#c99a3c;" +
        "border:3px solid #fff;box-shadow:0 0 0 4px rgba(201,154,60,.35)," +
        "0 2px 6px rgba(0,0,0,.5);animation:tm-pulse 1.8s ease-out infinite";
    } else {
      el.style.cssText =
        `width:13px;height:13px;border-radius:50%;background:${color};` +
        "border:3px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.45)";
    }
    const m = new maplibregl.Marker({ element: el })
      .setLngLat([s.lng, s.lat])
      .setPopup(
        new maplibregl.Popup({ offset: 16, closeButton: false }).setText(
          s.eta ? `${s.name} · ${s.eta}` : s.name,
        ),
      )
      .addTo(map);
    MARKERS.push(m);
  });

  const b = stationCs.reduce(
    (acc, c) => acc.extend(c),
    new maplibregl.LngLatBounds(stationCs[0], stationCs[0]),
  );
  map.fitBounds(b, { padding: 55, duration: 0, maxZoom: 8.5 });
}

function ensureLine(id: string, data: any, paint: any) {
  if (map.getSource(id)) {
    map.getSource(id).setData(data);
  } else {
    map.addSource(id, { type: "geojson", data });
    map.addLayer({
      id,
      type: "line",
      source: id,
      paint,
      layout: { "line-cap": "round", "line-join": "round" },
    });
  }
}

// PMTiles ichidagi HAQIQIY temir yo'lni ta'kidlab ko'rsatamiz (egri relslar,
// oflayn). Protomaps schema versiyalarida temir yo'l "transit" yoki "roads"
// source-layer'da bo'lishi mumkin — ikkala variantni ham qo'shamiz (mos
// kelmagani jim ko'rinmaydi, xato bermaydi). Temir yo'l uslubi: nuqtali chiziq.
function addRailway() {
  const railColor = "#1445a7"; // brend navy (dizayn faqat ivory)
  const candidates = [
    { sl: "transit", filt: ["==", ["get", "kind"], "rail"] },
    { sl: "roads", filt: ["==", ["get", "kind"], "rail"] },
    { sl: "transit", filt: ["==", ["get", "pmap:kind"], "rail"] },
  ];
  candidates.forEach((c, i) => {
    try {
      map.addLayer({
        id: `rail-hl-${i}`,
        source: "protomaps",
        "source-layer": c.sl,
        type: "line",
        filter: c.filt as any,
        paint: {
          "line-color": railColor,
          "line-width": ["interpolate", ["linear"], ["zoom"], 5, 1.2, 10, 2.6],
          "line-opacity": 0.5,
          "line-dasharray": [2, 2],
        },
      });
    } catch {
      /* source-layer mos kelmadi — jim o'tamiz */
    }
  });
}

// O'zbekiston chegara + tashqi mask (premium ajratish). Dizayn ivory bo'lgani
// uchun tashqi davlatlar ivory parda bilan xiralashtiriladi, chegara oltin
// porlash bilan ta'kidlanadi — O'zbekiston yorqin ajralib turadi.
async function addBoundary() {
  // Mask: O'zbekiston TASHQARISI ivory parda (ichi teshik) — qo'shni davlatlar
  // sahifa foniga singib ketadi, O'zbekiston to'liq rangda qoladi.
  try {
    const mask = await $fetch("/uzbekistan-mask.geojson").catch(() => null);
    if (mask) {
      map.addSource("uz-mask", { type: "geojson", data: mask });
      map.addLayer({
        id: "uz-mask",
        type: "fill",
        source: "uz-mask",
        paint: {
          "fill-color": "#f1ead9", // page-bg'ga yaqin ivory
          "fill-opacity": 0.66,
        },
      });
    }
  } catch {
    /* mask ixtiyoriy */
  }
  // Chegara: oltin porlash (keng, xira) + asosiy oltin chiziq
  try {
    const b = await $fetch("/uzbekistan-boundary.geojson").catch(() => null);
    if (b) {
      map.addSource("uz-boundary", { type: "geojson", data: b });
      map.addLayer({
        id: "uz-boundary-glow",
        type: "line",
        source: "uz-boundary",
        paint: {
          "line-color": "#c99a3c",
          "line-width": 7,
          "line-opacity": 0.22,
          "line-blur": 3,
        },
        layout: { "line-cap": "round", "line-join": "round" },
      });
      map.addLayer({
        id: "uz-boundary",
        type: "line",
        source: "uz-boundary",
        paint: {
          "line-color": "#c99a3c",
          "line-width": 2.2,
          "line-opacity": 0.95,
        },
        layout: { "line-cap": "round", "line-join": "round" },
      });
    }
  } catch {
    /* ixtiyoriy */
  }
}

onMounted(async () => {
  try {
    maplibregl = (await import("maplibre-gl")).default;
    const { Protocol } = await import("pmtiles");
    const themeMod = await import("protomaps-themes-base");
    const layersFn: any =
      (themeMod as any).default || (themeMod as any).layers || themeMod;

    // Haqiqiy temir yo'l geometriyasi (bo'lsa) — oldindan yuklaymiz
    railGeo = await $fetch("/tashkent-khiva-rail.geojson").catch(() => null);

    const protocol = new Protocol();
    maplibregl.addProtocol("pmtiles", protocol.tile);

    const origin = window.location.origin;
    const flavor = "light"; // dizayn faqat ivory — xarita ham doim light

    map = new maplibregl.Map({
      container: mapEl.value!,
      style: {
        version: 8,
        glyphs: `${origin}/api/map/fonts/{fontstack}/{range}.pbf`,
        sources: {
          protomaps: {
            type: "vector",
            url: `pmtiles://${origin}/api/map/data/uzbekistan.pmtiles`,
            attribution: "© OpenStreetMap",
          },
        },
        layers: typeof layersFn === "function" ? layersFn("protomaps", flavor) : [],
      },
      center: [64.5, 41.3],
      zoom: 5,
      attributionControl: false,
      dragRotate: false,
    });
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );
    // Konteyner o'lchami o'zgarsa (flex/grid tartib, mobil "order", panel
    // balandligi) — canvas'ni qayta o'lchaymiz. Busiz MapLibre init paytida
    // balandlik hali yakunlanmagan bo'lsa bo'sh (oq) qolardi.
    if (typeof ResizeObserver !== "undefined" && mapEl.value) {
      resizeObs = new ResizeObserver(() => map && map.resize());
      resizeObs.observe(mapEl.value);
    }
    map.on("load", async () => {
      map.resize();
      await addBoundary();
      drawRoute();
    });
    map.on("error", (e: any) => {
      if (e?.error?.status === 404 || e?.error?.status === 403) mapError.value = true;
    });
  } catch (err) {
    console.error("[TrainMap] MapLibre yuklanmadi:", err);
    mapError.value = true;
  }
});

watch(
  () => props.routeData,
  () => {
    if (map && map.isStyleLoaded && map.isStyleLoaded()) drawRoute();
  },
  { deep: true },
);

onBeforeUnmount(() => {
  if (resizeObs) resizeObs.disconnect();
  MARKERS.forEach((m) => m.remove());
  if (map) map.remove();
});
</script>

<style>
@keyframes tm-pulse {
  0% {
    box-shadow:
      0 0 0 0 rgba(201, 154, 60, 0.55),
      0 2px 6px rgba(0, 0, 0, 0.5);
  }
  70% {
    box-shadow:
      0 0 0 13px rgba(201, 154, 60, 0),
      0 2px 6px rgba(0, 0, 0, 0.5);
  }
  100% {
    box-shadow:
      0 0 0 0 rgba(201, 154, 60, 0),
      0 2px 6px rgba(0, 0, 0, 0.5);
  }
}
</style>
