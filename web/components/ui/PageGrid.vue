<template>
  <div
    class="mx-auto grid max-w-[1920px] gap-[24px] overflow-y-auto pb-[24px]"
    :class="[columnsClass, maxHeightClass]"
  >
    <slot />
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    columns: "books" | "videos" | "websites";
    maxHeight?: "default" | "tall";
  }>(),
  {
    maxHeight: "default",
  },
);

const columnsClass = computed(() => {
  if (props.columns === "books")
    return "grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-5";
  if (props.columns === "videos")
    return "grid-cols-1 sm:grid-cols-2 md:grid-cols-3";
  return "grid-cols-1 sm:grid-cols-2 md:grid-cols-3";
});

const maxHeightClass = computed(() =>
  props.maxHeight === "tall" ? "max-h-[82.7vh]" : "max-h-[72.4vh]",
);
</script>
