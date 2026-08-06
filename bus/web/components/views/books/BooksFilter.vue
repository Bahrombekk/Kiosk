<template>
  <div class="flex items-center justify-between">
    <ContentTabs v-model:active-key="model" :items="items" />
  </div>
</template>

<script setup lang="ts">
const model = defineModel("activeCategory");
import type { IconItem } from "~/types/app";
defineProps<{
  items: IconItem[];
}>();
</script>
