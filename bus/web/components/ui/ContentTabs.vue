<!-- ContentTabs — pill segment (milliy dizayn): oq yumaloq idish + tugmalar,
     aktiv navy. Videolar (tur) va Kitoblar (janr) filtrida ishlatiladi. -->
<template>
  <div
    class="inline-flex max-w-full gap-[4px] overflow-x-auto rounded-full bg-(--surface-bg) p-[6px] shadow-(--shadow-card)"
  >
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="cursor-pointer whitespace-nowrap rounded-full border-0 px-[clamp(13px,1.6vw,22px)] py-[10px] text-[14px] transition-colors"
      :class="
        item.key === activeKey
          ? 'bg-(--brand-base) font-extrabold text-white'
          : 'bg-transparent font-semibold text-(--text-muted-btn) hover:text-(--brand-base)'
      "
      @click="$emit('update:activeKey', item.key)"
    >
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
