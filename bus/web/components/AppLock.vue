<!-- AppLock.vue — GLOBAL qulf ekrani. Backend `/api/status`da blocked=true bo'lsa
     (litsenziya yaroqsiz/muddati o'tgan, bulutдan qo'lda blok, yoki texnik rejim)
     butun sayt ustiga to'liq ekran qulf tushadi — yo'lovchi kontent ko'rmaydi.
     15 soniyada bir tekshiradi: bulutдан blok/ochilса ~15s ichida aks etadi. -->
<template>
  <Transition name="lock-fade">
    <div v-if="blocked" class="lock-root">
      <div class="lock-card">
        <div class="lock-badge">
          <svg viewBox="0 0 24 24" width="46" height="46" fill="none"
               stroke="#e8c87a" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <rect x="4" y="10.5" width="16" height="10" rx="2.5" />
            <path d="M8 10.5V7a4 4 0 0 1 8 0v3.5" />
            <circle cx="12" cy="15.4" r="1.4" fill="#e8c87a" stroke="none" />
          </svg>
        </div>
        <h1 class="lock-title">Xizmat vaqtincha to'xtatilgan</h1>
        <p class="lock-sub">{{ reasonText }}</p>
        <p class="lock-foot">AVTOBUS<span>.UZ</span></p>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
const blocked = ref(false);
const reason = ref<string | null>(null);

const reasonText = computed(() => {
  if (reason.value === "maintenance")
    return "Texnik ishlar olib borilmoqda. Iltimos, birozdan so'ng qayta urinib ko'ring.";
  // license / default
  return "Ushbu qurilma xizmati faollashtirilmagan. Iltimos, operator bilan bog'laning.";
});

let timer: ReturnType<typeof setInterval> | undefined;
async function check() {
  try {
    const s = await $fetch<{ blocked?: boolean; lock_reason?: string | null }>(
      "/api/status",
      { headers: { "cache-control": "no-cache" } },
    );
    blocked.value = !!s?.blocked;
    reason.value = s?.lock_reason ?? null;
  } catch {
    // Tarmoq xatosi — qulfni O'ZGARTIRMAYMIZ (mavjud holat saqlanadi).
  }
}
onMounted(() => {
  check();
  timer = setInterval(check, 15000);
});
onBeforeUnmount(() => timer && clearInterval(timer));
</script>

<style scoped>
.lock-root {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: grid;
  place-items: center;
  padding: 24px;
  background-color: #0a1636;
  background-image:
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='46' height='46'%3E%3Cpath d='M23 3 43 23 23 43 3 23Z' fill='none' stroke='rgba(232,200,122,0.14)' stroke-width='1.4'/%3E%3Cpath d='M23 15 31 23 23 31 15 23Z' fill='rgba(232,200,122,0.08)'/%3E%3C/svg%3E"),
    radial-gradient(circle at 50% 30%, rgba(26, 58, 134, 0.55), transparent 70%),
    linear-gradient(135deg, #0e2150, #0a1636);
  background-repeat: repeat, no-repeat, no-repeat;
  background-size: 46px 46px, cover, cover;
}
.lock-card {
  text-align: center;
  max-width: 460px;
}
.lock-badge {
  width: 92px;
  height: 92px;
  margin: 0 auto 22px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: rgba(232, 200, 122, 0.1);
  border: 1.5px solid rgba(232, 200, 122, 0.35);
}
.lock-title {
  color: #fff;
  font-size: clamp(22px, 4vw, 30px);
  font-weight: 800;
  margin: 0 0 12px;
  font-family: "Unbounded", system-ui, sans-serif;
}
.lock-sub {
  color: rgba(255, 255, 255, 0.78);
  font-size: clamp(14px, 2vw, 16px);
  line-height: 1.5;
  margin: 0 0 28px;
}
.lock-foot {
  color: #fff;
  font-weight: 800;
  letter-spacing: 0.04em;
  font-family: "Unbounded", system-ui, sans-serif;
}
.lock-foot span {
  color: #e8c87a;
}
.lock-fade-enter-active,
.lock-fade-leave-active {
  transition: opacity 0.35s ease;
}
.lock-fade-enter-from,
.lock-fade-leave-to {
  opacity: 0;
}
</style>
