<template>
  <div
    class="relative flex items-center justify-center overflow-hidden bg-cover bg-no-repeat"
    :class="frameClass"
  >
    <!-- loading=lazy: 200 kartali gridda ~400 eager so'rov bo'lmasin;
         @error: singan muqova brauzerning singan-rasm belgisi o'rniga
         yashiriladi (fon rangi qoladi) -->
    <img
      v-if="!broken"
      :src="backgroundSrc || src"
      :alt="alt"
      loading="lazy"
      class="absolute top-0 left-0 h-full w-full scale-[1.2] object-cover blur-[8px]"
      :class="blurClass"
      @error="broken = true"
    />
    <img
      v-if="!broken"
      :src="src"
      :alt="alt"
      loading="lazy"
      class="z-2"
      :class="imageClass"
      @error="broken = true"
    />
    <div
      v-else
      class="z-2 flex items-center justify-center bg-(--tertiary-bg) text-(--text-secondary)"
      :class="imageClass"
    >
      <UIcon name="i-lucide-image-off" class="text-[2rem]" />
    </div>
    <slot />
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    src: string;
    alt: string;
    backgroundSrc?: string;
    frameClass?: string;
    imageClass?: string;
    blurClass?: string;
  }>(),
  {
    backgroundSrc: "",
    frameClass: "",
    imageClass: "",
    blurClass: "",
  },
);

const broken = ref(false);
</script>
