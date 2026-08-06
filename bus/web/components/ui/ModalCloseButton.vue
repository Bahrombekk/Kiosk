<template>
  <button
    type="button"
    :class="classes"
    @click="$emit('click')"
  >
    <Icon :name="iconName" :size="variant === 'text' ? '24' : '32px'" />
    <span v-if="variant === 'text'">
      <slot />
    </span>
  </button>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    variant?: "circle" | "text";
    icon?: string;
  }>(),
  {
    variant: "circle",
    icon: undefined,
  },
);

defineEmits<{
  click: [];
}>();

const iconName = computed(() => {
  if (props.icon) return props.icon;
  return props.variant === "text" ? "lucide:arrow-left" : "lucide:x";
});

const classes = computed(() => {
  if (props.variant === "text") {
    return "flex cursor-pointer items-center gap-[12px] rounded-[16px] bg-blue-600/15 p-[18px] text-[1.125rem] font-semibold text-(--brand-base)";
  }

  return "absolute top-[16px] right-[16px] z-3 flex cursor-pointer items-center justify-center rounded-full text-(--icon-secondary) outline-none";
});
</script>
