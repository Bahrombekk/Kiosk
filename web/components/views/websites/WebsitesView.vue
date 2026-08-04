<template>
  <FetchErrorState v-if="error" @retry="refresh" />
  <template v-else>
    <WebsitesModal
      :selectedWebsite="selectedWebsite"
      :scanInstructions="scanInstructions"
      v-model:isModalOpen="isModalOpen"
    />
    <WebsitesList :websites="websites" @openWebsite="openWebsite" />
  </template>
</template>

<script setup lang="ts">
import type { ScanInstruction, Website } from "~/types/app";

const { t } = useI18n();
const { data: websites, error, refresh } =
  await useFetch<Website[]>("/api/websites");

const isModalOpen = ref(false);
const selectedWebsite = ref<Website>();
const scanInstructions = computed<ScanInstruction[]>(() => [
  { step: 1, label: t("scanInstructions.pointCamera") },
  { step: 2, label: t("scanInstructions.clickLink") },
  { step: 3, label: t("scanInstructions.canUseAtHome") },
]);

function openWebsite(website: Website) {
  selectedWebsite.value = website;
  isModalOpen.value = true;
}
</script>
