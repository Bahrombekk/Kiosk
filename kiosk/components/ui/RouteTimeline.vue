<template>
  <div class="overflow-y-auto">
    <!-- Horizontal layout mirrors the real train track layout -->
    <!-- :model-value (boshqariladigan) — :default-value faqat mount paytida
         o'qilardi, 15s'lik yangilanishlarda joriy bekat siljimay qotib qolardi -->
    <UTimeline
      :items="timelineItems"
      :model-value="currentStopIndex"
      color="info"
      :ui="{
        root: 'max-h-[360px]',
      }"
    />
  </div>
</template>

<script setup lang="ts">
import type { TrainRoute } from "~/types/app";

const props = defineProps<{
  routeData: TrainRoute;
}>();

// Find the index of the train's current/last passed stop (-1 = noma'lum,
// hech bir bekat "yetib kelingan" deb belgilanmaydi)
const currentStopIndex = computed(() => {
  return props.routeData.stops.reduce((lastIdx, stop, idx) => {
    return stop.passed ? idx : lastIdx;
  }, -1);
});

// Format your train data to match the Nuxt UI TimelineItem structure
const timelineItems = computed(() => {
  return props.routeData.stops.map((stop) => ({
    title: stop.name,
    description: `ETA: ${stop.eta}`,
    // Dynamically change icons based on whether the train passed the city
    icon: stop.passed
      ? "i-heroicons-check-circle-20-solid"
      : "i-heroicons-clock",
  }));
});
</script>
