<template>
  <div
    class="grid grid-cols-1 lg:grid-cols-2 gap-[32px] rounded-[24px] bg-(--tertiary-bg) p-[16px] md:p-[24px_40px] lg:flex-row"
  >
    <div class="w-full">
      <h1 class="font-['Manrope'] text-[2.25rem] font-semibold">
        {{ $t("train") }}
      </h1>
      <p class="text-[1.25rem] text-(--text-secondary)">
        {{ from || "—" }} → {{ to || "—" }}
      </p>
      <div class="mt-[8px] flex flex-col gap-[12px]">
        <div
          v-for="item in rideInfo"
          :key="item.label"
          class="w-fit flex items-center gap-[6px] rounded-[12px] bg-(--surface-bg) p-[10px_24px] font-['Manrope'] text-[1rem] font-medium text-(--text-secondary)"
        >
          <component :is="item.icon" class="text-(--icon-secondary)" />
          <span class="m-0 whitespace-nowrap">{{ item.label }}</span>
        </div>
      </div>
    </div>
    <div class="w-full h-full">
      <div
        class="relative h-full w-full overflow-hidden rounded-[16px] bg-(--neutral-stroke)"
      >
        <img
          src="~/assets/img/corner_logo.png"
          alt="Logo"
          class="absolute top-0 left-0 h-auto w-1/2"
        />
        <img
          src="~/assets/img/train_image.png"
          alt="Poyezd"
          class="absolute top-1/2 right-0 h-auto w-full -translate-y-1/2"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { IconComponent } from "~/types/app";

defineProps<{
  rideInfo: { icon: IconComponent; label: string }[];
  from?: string;
  to?: string;
}>();
</script>
