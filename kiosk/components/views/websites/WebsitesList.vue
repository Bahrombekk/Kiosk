<template>
  <!-- Bo'sh holat — jim bo'sh grid o'rniga aniq xabar -->
  <p
    v-if="!websites?.length"
    class="py-[48px] text-center text-[1.25rem] text-(--text-secondary)"
  >
    {{ $t("nothingFound") }}
  </p>
  <PageGrid v-else columns="websites" max-height="tall">
    <div
      v-for="website in websites"
      :key="website.id"
      class="flex flex-col overflow-hidden rounded-[16px] bg-(--surface-bg) shadow-[0_8px_32px_rgba(0,0,0,0.04)]"
    >
      <div class="flex items-center gap-[16px] p-[16px]">
        <div
          class="flex h-[52px] w-[52px] items-center justify-center rounded-[12px] bg-(--tertiary-bg)"
        />
        <div>
          <p class="m-0 text-[1.25rem]">{{ website.name }}</p>
          <p class="m-0 text-[0.875rem] text-(--brand-base)">
            {{ website.link_title }}
          </p>
        </div>
      </div>
      <div class="relative h-[132px] bg-(--tertiary-bg) rounded-t-[16px]">
        <GlobeIcon
          class="absolute top-0 left-[10px] z-1 h-[130px]! w-[130px]! text-(--brand-base) opacity-5"
        />
        <p
          class="relative z-3 m-0 px-[16px] pt-[20px] text-[0.875rem] text-(--text-secondary)"
        >
          {{ website.description_short }}
        </p>
        <button
          type="button"
          class="relative z-3 float-right mr-[16px] mb-[20px] flex h-[44px] w-[44px] cursor-pointer items-center justify-center rounded-full border-0 bg-(--surface-bg)"
          @click="$emit('openWebsite', website)"
        >
          <Icon name="i-lucide:arrow-right" size="1.25rem" />
        </button>
      </div>
    </div>
  </PageGrid>
</template>

<script setup lang="ts">
import GlobeIcon from "~/assets/svg/globe-alt.svg";
import type { Website } from "~/types/app";
defineProps<{
  websites: Website[] | undefined;
}>();
</script>
