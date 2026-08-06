<!-- SearchField — yumaloq (pill) qidiruv maydoni (milliy dizayn). -->
<template>
  <label
    class="flex w-full items-center rounded-full bg-(--surface-bg) px-[20px] py-[13px] font-[Manrope] text-[14px] text-(--text-primary) shadow-(--shadow-card) md:w-auto"
  >
    <Icon name="lucide:search" size="18" class="text-(--icon-secondary)" />
    <input
      :value="modelValue"
      type="text"
      :placeholder="placeholder"
      class="ml-[8px] min-w-0 border-0 bg-transparent text-[14px] outline-none placeholder:text-(--text-secondary) md:w-[240px]"
      @input="
        $emit('update:modelValue', ($event.target as HTMLInputElement).value)
      "
    />
  </label>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue?: string;
    placeholder?: string;
  }>(),
  {
    modelValue: "",
    placeholder: "",
  },
);

defineEmits<{
  "update:modelValue": [value: string];
}>();
</script>
