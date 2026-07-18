<template>
  <div
    class="mb-[24px] flex flex-col items-center justify-between gap-[12px] md:flex-row"
  >
    <ContentTabs v-model:active-key="activeCategoryModel" :items="items" />
    <SearchField
      v-model="searchQueryModel"
      :placeholder="$t('searchPlaceholder')"
    />
  </div>
</template>
<script setup lang="ts">
import type { IconItem } from "~/types/app";
defineProps<{
  items: IconItem[];
}>();

// selectedCategory modeli olib tashlandi — hech narsa o'rnatmasdi
// (v-show doim true bo'lib, o'lik kod edi).
const activeCategoryModel = defineModel("activeCategory", { type: String });
const searchQueryModel = defineModel("searchQuery", { type: String });
</script>
