<template>
  <div class="flex w-full overflow-x-auto">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="flex cursor-pointer items-center gap-[10px] text-nowrap border-0 bg-transparent p-[12px] text-[1.125rem] font-medium text-(--text-secondary) md:p-[14px_21px]"
      :class="
        item.key === activeKey
          ? 'border-b border-(--brand-base) text-(--brand-base)!'
          : ''
      "
      @click="$emit('update:activeKey', item.key)"
    >
      <component
        :is="item.icon"
        class="text-(--icon-secondary)"
        :class="item.key === activeKey ? 'text-(--brand-base)!' : ''"
      />
      {{ item.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
import type { IconItem } from "~/types/app";

defineProps<{
  items: IconItem[];
}>();

const activeKey = defineModel("activeKey");
</script>
