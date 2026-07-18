<template>
  <UModal
    v-model:open="model"
    scrollable
    :ui="{
      content: 'max-w-[632px] h-auto! md:h-[393px]',
    }"
  >
    <template #content>
      <div
        v-if="selectedWebsite"
        class="flex flex-col gap-[20px] overflow-hidden rounded-[24px] bg-(--surface-bg) p-[24px]"
      >
        <div>
          <ModalCloseButton variant="text" @click="model = false">
            {{ $t("back") }}
          </ModalCloseButton>
        </div>
        <div
          class="flex items-center gap-[16px] rounded-[8px] bg-(--tertiary-bg) p-[12px]"
        >
          <div
            class="flex h-[52px] w-[52px] items-center justify-center rounded-[8px] bg-(--surface-bg)"
          />
          <div>
            <p class="m-0">{{ selectedWebsite.name }}</p>
            <p class="m-0 text-(--brand-base)">
              {{ selectedWebsite.link_title }}
            </p>
          </div>
        </div>
        <div class="text-(--text-secondary)">
          {{ selectedWebsite.description }}
        </div>
        <div
          class="flex flex-col items-center gap-[16px] rounded-[8px] border border-(--brand-base) bg-(--brand-surface) px-[12px] py-[16px] md:flex-row"
        >
          <div
            class="flex h-[168px] w-[168px] shrink-0 items-center justify-center rounded-[8px] bg-white p-[8px]"
          >
            <!-- QR sayt havolasidan JONLI generatsiya qilinadi — avvalgi statik
                 rasm hamma saytga bitta QR ko'rsatardi va prod buildda 404 edi -->
            <img
              v-if="qrDataUrl"
              :src="qrDataUrl"
              class="h-full w-full"
              alt="QR"
            />
          </div>
          <div>
            <p class="mb-[12px] mt-0 text-[1.25rem] text-(--text-primary)">
              {{ $t("openOnYourPhone") }}
            </p>
            <ol class="flex flex-col gap-[8px]">
              <li
                v-for="instruction in scanInstructions"
                :key="instruction.step"
                class="flex items-center gap-[8px] text-[1rem] text-(--text-secondary)"
              >
                <span
                  class="flex h-[32px] w-[32px] items-center justify-center rounded-full bg-(--surface-bg) font-semibold text-(--text-primary)"
                >
                  {{ instruction.step }}
                </span>
                {{ instruction.label }}
              </li>
            </ol>
          </div>
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import QRCode from "qrcode";
import type { ScanInstruction, Website } from "~/types/app";

const model = defineModel("isModalOpen", { type: Boolean });

const props = defineProps<{
  selectedWebsite: Website | undefined;
  scanInstructions: ScanInstruction[];
}>();

// Tanlangan saytning havolasidan QR (data URL) — sayt almashsa qayta chiziladi
const qrDataUrl = ref("");
watch(
  () => props.selectedWebsite?.link,
  async (link) => {
    try {
      qrDataUrl.value = link
        ? await QRCode.toDataURL(link, { width: 320, margin: 1 })
        : "";
    } catch {
      qrDataUrl.value = "";
    }
  },
  { immediate: true },
);
</script>
