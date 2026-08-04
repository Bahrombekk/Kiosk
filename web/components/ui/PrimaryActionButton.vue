<template>
  <NuxtLink v-if="to" :to="to" :class="classes">
    <slot name="icon" />
    <slot />
  </NuxtLink>
  <button v-else type="button" :class="classes" @click="$emit('click')">
    <slot name="icon" />
    <slot />
  </button>
</template>

<script setup lang="ts">
import type { RouteLocationRaw } from "vue-router";

const props = withDefaults(
  defineProps<{
    variant?: "brand" | "warning";
    to?: RouteLocationRaw;
    size?: "md" | "lg";
  }>(),
  {
    variant: "brand",
    to: undefined,
    size: "lg",
  },
);

defineEmits<{
  click: [];
}>();

const classes = computed(() => [
  "flex w-full cursor-pointer items-center justify-center gap-[12px] rounded-[16px] text-white font-semibold",
  props.size === "lg" ? "p-[18px] text-[1.125rem]" : "p-[12px] text-[1rem]",
  props.variant === "warning" ? "bg-(--warning-base)" : "bg-(--brand-base)",
]);
</script>
