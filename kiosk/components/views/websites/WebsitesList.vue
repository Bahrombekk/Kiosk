<!-- WebsitesList.vue — sayt kartalari (§18): bosh harf belgisi + nom/havola +
     qisqa tavsif + "QR bilan ochish" tugmasi (QR modalni ochadi). -->
<template>
  <p
    v-if="!websites?.length"
    class="py-[48px] text-center text-[1.25rem] text-(--text-secondary)"
  >
    {{ $t("nothingFound") }}
  </p>
  <div
    v-else
    class="grid gap-[16px]"
    style="grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr)); animation: omFade 0.35s ease"
  >
    <div
      v-for="website in websites"
      :key="website.id"
      class="flex flex-col gap-[12px] rounded-[20px] bg-(--surface-bg) p-[20px] shadow-(--shadow-card)"
    >
      <div class="flex items-center gap-[12px]">
        <div
          class="flex h-[46px] w-[46px] flex-none items-center justify-center rounded-[14px] bg-(--brand-surface) font-[Unbounded] text-[16px] font-bold text-(--brand-base)"
        >
          {{ (website.name || "?").charAt(0).toUpperCase() }}
        </div>
        <div class="min-w-0">
          <div class="truncate text-[15px] font-extrabold text-(--text-primary)">
            {{ website.name }}
          </div>
          <div class="truncate text-[12px] font-bold text-(--brand-base)">
            {{ website.link_title }}
          </div>
        </div>
      </div>
      <div class="text-[13px] leading-[1.5] text-(--text-secondary)">
        {{ website.description_short }}
      </div>
      <button
        type="button"
        class="mt-auto self-start rounded-[12px] border-0 bg-(--brand-base) px-[18px] py-[11px] text-[12px] font-extrabold text-white transition-colors hover:bg-(--brand-hover)"
        @click="$emit('openWebsite', website)"
      >
        {{ $t("openWithQr") }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Website } from "~/types/app";

defineProps<{
  websites: Website[] | undefined;
}>();

defineEmits<{
  openWebsite: [website: Website];
}>();
</script>
