<template>
  <UCarousel
    v-if="bannerAds.length"
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
// Banner reklama: placement banner|both + vaqt oynasi (kiosk parity).
const { bannerAds } = useAds();
</script>
