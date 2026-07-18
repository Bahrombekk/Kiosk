<template>
  <div class="grid grid-cols-1 gap-[16px] pt-[24px] mdl:grid-cols-2">
    <RouteTimeline :route-data="props.routeInfo" />
    <TrainMap :route-data="props.routeInfo" />
  </div>
</template>

<script setup lang="ts">
import type { TrainRoute } from "~/types/app";

const props = defineProps<{
  routeInfo: TrainRoute;
}>();
</script>
