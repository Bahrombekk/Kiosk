<!-- components/TrainMap.vue -->
<template>
  <div class="relative h-[368px] w-full overflow-hidden rounded-[16px]">
    <LMap
      ref="map"
      :zoom="zoom"
      :center="center"
      :bounds="mapBounds"
      :use-global-leaflet="false"
      @ready="onMapReady"
    >
      <LTileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&amp;copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors'
        layer-type="base"
        name="OpenStreetMap"
      />

      <!-- 1. The Global Track Route (Gray Line) -->
      <LPolyline :lat-lngs="fullRouteCoords" color="#cbd5e1" :weight="6" />

      <!-- 2. The Already Traveled Track (Green Line) -->
      <LPolyline :lat-lngs="passedRouteCoords" color="#10b981" :weight="6" />

      <!-- 3. City Stop Markers -->
      <LMarker
        v-for="(stop, index) in routeData.stops"
        :key="'stop-' + index"
        :lat-lng="[stop.lat, stop.lng]"
      >
        <LPopup>
          <div class="p-1">
            <h3 class="font-bold text-sm">{{ stop.name }}</h3>
            <p class="text-xs text-gray-500">ETA: {{ stop.eta }}</p>
            <span
              class="text-xs px-1.5 py-0.5 rounded-full inline-block mt-1"
              :class="
                stop.passed
                  ? 'bg-green-100 text-green-800'
                  : 'bg-gray-100 text-gray-800'
              "
            >
              {{ stop.passed ? "Passed" : "Upcoming" }}
            </span>
          </div>
        </LPopup>
      </LMarker>
    </LMap>
  </div>
</template>

<script setup lang="ts">
import {
  LMap,
  LTileLayer,
  LPolyline,
  LMarker,
  LPopup,
} from "@vue-leaflet/vue-leaflet";
import type { TrainRoute } from "~/types/app";

const props = defineProps<{
  routeData: TrainRoute;
}>();

const zoom = ref(8);
const center = ref([41.311081, 69.240562]);

const fullRouteCoords = computed(() => {
  return props.routeData.stops.map((stop) => [stop.lat, stop.lng]);
});

// Extract only coordinates that the train has successfully cleared
const passedRouteCoords = computed(() => {
  return props.routeData.stops
    .filter((stop) => stop.passed)
    .map((stop) => [stop.lat, stop.lng]);
});

// 2. Automatically compute the map edges to enclose all stops
const mapBounds = computed(() => {
  if (!props.routeData.stops || props.routeData.stops.length === 0) {
    return [
      [41.311, 69.24],
      [41.311, 69.24],
    ]; // Fallback bounds
  }

  const lats = props.routeData.stops.map((s) => s.lat);
  const lngs = props.routeData.stops.map((s) => s.lng);

  // Find extreme ends of the train track path
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);

  return [
    [minLat, minLng],
    [maxLat, maxLng],
  ];
});
const onMapReady = async (leafletMapInstance) => {
  // Give Nuxt/Vue layout an extra frame to calculate concrete container pixel width/height
  await nextTick();

  if (fullRouteCoords.value.length > 0) {
    leafletMapInstance.invalidateSize();

    // 2. Programmatically force the viewport frame to zoom out and fit all stops
    leafletMapInstance.fitBounds(fullRouteCoords.value, {
      padding: [40, 40],
      animate: true,
    });
  }
};
</script>
