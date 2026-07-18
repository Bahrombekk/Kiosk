<template>
  <UCarousel
    v-if="bannerAds.length"
    ref="carouselRef"
    v-slot="{ item }"
    :items="bannerAds"
    :autoplay="{ delay: 13000 }"
    :watch-drag="false"
    loop
    :ui="{
      viewport: 'max-h-[384px]',
    }"
  >
    <div class="aspect-13/10 rounded-[24px] overflow-hidden flex items-center">
      <img :src="item.ad_image_link" loading="lazy" class="w-full" />
    </div>
  </UCarousel>
</template>

<script setup lang="ts">
import type { Ad } from "~/types/app";

// Banner reklama: placement banner|both + vaqt oynasi (kiosk parity).
const { bannerAds } = useAds();
const { track } = useStats();

// Proof-of-play: har banner ekranga chiqqanida ad_play (kiosk home.py bilan
// parity — u ham banner namoyishini placement=banner bilan yozadi).
type CarouselApi = {
  selectedScrollSnap: () => number;
  on: (e: "select", cb: () => void) => void;
  off: (e: "select", cb: () => void) => void;
};
const carouselRef = useTemplateRef<{ emblaApi?: CarouselApi }>("carouselRef");

function logBanner(ad?: Ad) {
  if (ad) {
    track("ad_play", {
      ad_id: ad.id,
      title: ad.title,
      media_type: ad.mediaType,
      placement: "banner",
    });
  }
}

// Birinchi ko'rinayotgan banner (ro'yxat kelgach) + keyingi har almashish
watch(
  bannerAds,
  (list) => {
    if (list.length) logBanner(list[0]);
  },
  { immediate: true },
);

watchEffect((onCleanup) => {
  const embla = carouselRef.value?.emblaApi;
  if (!embla) return;
  const onSelect = () => logBanner(bannerAds.value[embla.selectedScrollSnap()]);
  embla.on("select", onSelect);
  onCleanup(() => embla.off("select", onSelect));
});
</script>
