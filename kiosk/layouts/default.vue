<template>
  <div class="">
    <div class="flex-none px-[16px] pt-[16px] md:px-[24px] md:pt-[24px]">
      <AppHeader :label="toDisplayString(currentTitle) || ''" />
    </div>
    <main class="flex-1 overflow-y-auto p-4 md:p-[24px]">
      <slot />
    </main>
    <!-- Qalqib chiquvchi reklama (media algoritmida chiqmaydi; pleyer sahifalari
         layout: false — playback vaqtida ulanmaydi) -->
    <AdPopup />
  </div>
</template>

<script setup lang="ts">
import { toDisplayString } from "vue";

const route = useRoute();
const currentTitle = computed(() => route.meta.layoutTitle || "");
</script>
