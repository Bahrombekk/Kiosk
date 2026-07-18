<template>
  <label
    class="flex w-full items-center rounded-[16px] border border-(--neutral-stroke) bg-(--surface-bg) px-[16px] py-[14px] font-['Manrope'] text-[1rem] text-(--text-primary) md:w-auto"
  >
    <Icon
      name="lucide:search"
      size="18"
      class="text-(--icon-secondary) dark:text-(--icon-active)"
    />
    <input
      :value="modelValue"
      type="text"
      :placeholder="placeholder"
      class="ml-[8px] min-w-0 border-0 bg-transparent text-[1rem] outline-none placeholder:text-(--text-secondary)"
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
