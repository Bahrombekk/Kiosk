<template>
  <div
    class="flex flex-col items-center justify-center gap-[16px] py-[64px] text-center"
  >
    <UIcon
      name="i-lucide-wifi-off"
      class="text-[3rem] text-(--text-secondary)"
    />
    <p class="m-0 text-[1.25rem] text-(--text-secondary)">
      {{ $t("connectionError") }}
    </p>
    <UButton
      icon="i-lucide-refresh-cw"
      size="xl"
      class="rounded-[12px]"
      @click="emit('retry')"
    >
      {{ $t("retry") }}
    </UButton>
  </div>
</template>

<script setup lang="ts">
/**
 * Backend'ga ulanib bo'lmaganda ko'rsatiladigan umumiy holat: lokalizatsiya-
 * langan xabar + "Qayta urinish" tugmasi. Kioskda foydalanuvchida F5 refleksi
 * yo'q — jim bo'sh sahifa o'rniga aniq holat va qayta urinish yo'li beriladi.
 */
const emit = defineEmits<{ retry: [] }>();
</script>
