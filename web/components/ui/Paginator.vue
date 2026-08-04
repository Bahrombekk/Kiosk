<!-- Paginator.vue — sahifalash (1 2 3…) boshqaruvi. Sensorli ekran uchun katta
     tugmalar; aktiv sahifa navy, milliy dizayn. `total`/`perPage`dan sahifalar
     hisoblanadi, v-model:page joriy sahifani boshqaradi. -->
<template>
  <nav
    v-if="pageCount > 1"
    class="flex flex-wrap items-center justify-center gap-[8px] pt-[8px]"
    aria-label="Sahifalar"
  >
    <button
      type="button"
      class="tm-pg"
      :disabled="page <= 1"
      aria-label="Oldingi"
      @click="go(page - 1)"
    >
      ‹
    </button>

    <button
      v-for="(p, i) in items"
      :key="i"
      type="button"
      class="tm-pg"
      :class="{
        'tm-pg--active': p === page,
        'tm-pg--gap': p === '…',
      }"
      :disabled="p === '…'"
      @click="typeof p === 'number' && go(p)"
    >
      {{ p }}
    </button>

    <button
      type="button"
      class="tm-pg"
      :disabled="page >= pageCount"
      aria-label="Keyingi"
      @click="go(page + 1)"
    >
      ›
    </button>
  </nav>
</template>

<script setup lang="ts">
const props = defineProps<{
  total: number;
  perPage: number;
}>();

const page = defineModel<number>("page", { default: 1 });

const pageCount = computed(() => Math.max(1, Math.ceil(props.total / props.perPage)));

// Sahifa oynasi: 7 tagacha hammasi; ko'p bo'lsa 1 … (joriy atrofi) … oxirgi
const items = computed<(number | "…")[]>(() => {
  const n = pageCount.value;
  const cur = page.value;
  if (n <= 7) return Array.from({ length: n }, (_, i) => i + 1);
  const out: (number | "…")[] = [1];
  const lo = Math.max(2, cur - 1);
  const hi = Math.min(n - 1, cur + 1);
  if (lo > 2) out.push("…");
  for (let p = lo; p <= hi; p++) out.push(p);
  if (hi < n - 1) out.push("…");
  out.push(n);
  return out;
});

function go(p: number) {
  const clamped = Math.min(Math.max(1, p), pageCount.value);
  if (clamped !== page.value) page.value = clamped;
}

// Umumiy son kamaysa (filtr) joriy sahifa chegaradan chiqmasin
watch(pageCount, (n) => {
  if (page.value > n) page.value = n;
});
</script>

<style scoped>
.tm-pg {
  min-width: 40px;
  height: 40px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1.5px solid var(--stroke-2);
  background: var(--surface-bg);
  color: var(--text-muted-btn);
  font-family: var(--font-body);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}
.tm-pg:hover:not(:disabled):not(.tm-pg--active) {
  border-color: var(--brand-base);
  color: var(--brand-base);
}
.tm-pg--active {
  background: var(--brand-base);
  border-color: var(--brand-base);
  color: #fff;
  font-weight: 800;
}
.tm-pg--gap {
  border-color: transparent;
  background: transparent;
  cursor: default;
}
.tm-pg:disabled:not(.tm-pg--gap) {
  opacity: 0.4;
  cursor: default;
}
</style>
