<!-- WebsitesModal.vue — QR modal: sayt nomi/havolasi + jonli QR + 3 qadamli
     ko'rsatma (navy/firuza/oltin raqamlar) + Ortga. -->
<template>
  <UModal
    v-model:open="model"
    scrollable
    :ui="{ content: 'max-w-[460px] rounded-[24px]' }"
  >
    <template #content>
      <div
        v-if="selectedWebsite"
        class="flex flex-col items-center gap-[16px] rounded-[24px] bg-(--page-bg) p-[28px] text-center"
      >
        <div class="font-[Unbounded] text-[19px] font-semibold text-(--text-primary)">
          {{ selectedWebsite.name }}
        </div>
        <div class="text-[13px] font-extrabold text-(--brand-base)">
          {{ selectedWebsite.link_title }}
        </div>
        <div class="rounded-[16px] bg-(--surface-bg) p-[16px] shadow-(--shadow-card)">
          <img
            v-if="qrDataUrl"
            :src="qrDataUrl"
            class="block h-[180px] w-[180px]"
            alt="QR"
          />
          <div v-else class="h-[180px] w-[180px]" />
        </div>
        <div class="flex flex-col gap-[8px] text-left text-[13px] text-[#4d5464]">
          <div
            v-for="(instruction, i) in scanInstructions"
            :key="instruction.step"
            class="flex items-center gap-[10px]"
          >
            <span
              class="inline-flex h-[22px] w-[22px] flex-none items-center justify-center rounded-full text-[11px] font-extrabold"
              :class="stepClass(i)"
            >
              {{ instruction.step }}
            </span>
            {{ instruction.label }}
          </div>
        </div>
        <button
          type="button"
          class="rounded-[12px] border-0 bg-(--brand-base) px-[26px] py-[12px] text-[13px] font-extrabold text-white transition-colors hover:bg-(--brand-hover)"
          @click="model = false"
        >
          {{ $t("back") }}
        </button>
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

// 3 qadam rangi: navy / firuza / oltin (§QR)
function stepClass(i: number): string {
  const map = [
    "bg-(--brand-base) text-white",
    "bg-(--accent-teal) text-white",
    "bg-(--accent-gold) text-(--text-on-gold)",
  ];
  return map[i % map.length];
}

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

// Sayt QR modali ochilishi statistikaga (admin "QR va SOS" -> Sayt QR ochildi)
const { track } = useStats();
watch(model, (open) => {
  if (open && props.selectedWebsite) {
    track("site_qr", { site: props.selectedWebsite.name });
  }
});
</script>
