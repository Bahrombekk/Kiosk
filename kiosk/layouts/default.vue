<template>
  <div class="relative min-h-screen">
    <!-- Milliy xonatlas chizig'i (sahifa tepasi) -->
    <div class="khanatlas-top" />

    <!-- Chet girih medalyonlari (naqsh.svg) — faqat keng ekranda -->
    <img
      src="/naqsh.svg"
      class="naqsh-medallion naqsh-medallion--left hidden mdl:block"
      alt=""
      aria-hidden="true"
    />
    <img
      src="/naqsh.svg"
      class="naqsh-medallion naqsh-medallion--right hidden mdl:block"
      alt=""
      aria-hidden="true"
    />

    <!-- Kontent (max-width 1240, markazda) -->
    <div
      class="relative z-1 mx-auto max-w-[1240px] px-[clamp(16px,3vw,36px)] pt-[12px] pb-[48px]"
    >
      <AppHeader :label="toDisplayString(currentTitle) || ''" />
      <main class="pt-[18px] pb-[74px] mdl:pb-[18px]">
        <slot />
      </main>
    </div>

    <!-- Xonatlas chizig'i (sahifa pasti) -->
    <div class="khanatlas-bottom" />

    <!-- Qalqib chiquvchi reklama (pleyer sahifalarida layout: false) -->
    <AdPopup />
  </div>
</template>

<script setup lang="ts">
import { toDisplayString } from "vue";

const route = useRoute();
const currentTitle = computed(() => route.meta.layoutTitle || "");
</script>
