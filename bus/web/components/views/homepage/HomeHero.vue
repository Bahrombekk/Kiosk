<!-- HomeHero.vue — Bosh sahifa banneri (§7).
     Banner bulutdan almashtiriladi (`/api/hero`), qo'yilmagan bo'lsa ilova
     bilan keladigan standart rasm ko'rinadi.

     Rasm USTIGA hech narsa yozilmaydi. Avval bu yerda yo'nalish nomi, keyingi
     bekat va uchta bekat yorlig'i chizilardi — ular standart `dashboard-hero.png`
     dagi bo'sh joylarga moslab joylashtirilgandi. Operator o'zining tayyor
     banneri (masalan «Qarshi Smart Bus») qo'yganda esa o'sha yozuvlar
     bannerning o'z matni ustiga tushib, ikkalasini ham o'qib bo'lmay qolardi.
     O'sha ma'lumotlarning hammasi sahifaning o'zida — yo'nalish kartochkasi va
     bekatlar ro'yxatida — baribir ko'rsatiladi, shuning uchun yo'qotish yo'q. -->
<template>
  <div class="tm-hero">
    <!-- Bulutdan qo'yilgan banner (xato bo'lsa yashiriladi va CSS'dagi standart
         rasm ko'rinadi). `<img>` + @error ishlatilgan, chunki CSS ko'p qatlami
         bilan zaxira ishonchsiz: eski/yangi backend mos kelmaganda banner
         butunlay yo'qolib qolardi. -->
    <img
      v-if="heroOk"
      class="tm-hero-bg"
      :src="HERO_URL"
      alt=""
      @error="heroOk = false"
    >
  </div>
</template>

<script setup lang="ts">
// Bulut banneri yuklandimi. Xato bo'lsa `false` bo'ladi va standart rasm
// (CSS foni) ko'rinadi — bosh sahifa hech qachon bo'sh qolmaydi.
// `:src` (o'zgaruvchi) ishlatilgan, chunki literal `src="/api/hero"` ni Vite
// build vaqtida lokal asset deb o'ylab, importni yechishga urinadi va yiqiladi.
const HERO_URL = "/api/hero";
const heroOk = ref(true);
</script>

<style scoped>
.tm-hero {
  position: relative;
  width: 100%;
  aspect-ratio: 1672 / 941;
  border-radius: 20px;
  overflow: hidden;
  /* ASOS — ilova bilan keladigan standart banner. U doim mavjud, shuning uchun
     bosh sahifa hech qachon bo'sh ko'rinmaydi. Bulutdan qo'yilgan banner
     ustiga `<img class="tm-hero-bg">` bo'lib tushadi (xato bo'lsa yashiriladi). */
  background: url("/dashboard-hero.png") center / cover no-repeat;
}

.tm-hero-bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
</style>
