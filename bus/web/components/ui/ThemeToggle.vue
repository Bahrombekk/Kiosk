<template>
  <ClientOnly>
    <button
      @click="toggleTheme"
      class="cursor-pointer bg-(--surface-bg) p-[16px] flex items-center justify-center rounded-full"
      aria-label="Toggle Theme"
    >
      <Icon :name="iconName" size="28px" />
    </button>
  </ClientOnly>
</template>

<script setup>
import { computed } from "vue";

const colorMode = useColorMode();
const iconName = computed(() => {
  return colorMode.value === "dark" ? "lucide:sun" : "lucide:moon";
});

const toggleTheme = () => {
  colorMode.preference = colorMode.value === "dark" ? "light" : "dark";
};
</script>
