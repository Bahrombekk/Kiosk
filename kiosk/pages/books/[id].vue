<template>
  <AudiobookPlayer v-if="book && showAudioPlayer" :book="book" />
  <TextBookReader v-else-if="book" :book="book" />
  <!-- Backend'ga ulanib bo'lmadi — aniq aloqa xatosi + qayta urinish -->
  <div
    v-else-if="fetchError"
    class="grid h-dvh place-items-center bg-(--primary-bg) text-(--text-primary)"
  >
    <FetchErrorState @retry="refresh" />
  </div>
  <!-- bg-white emas — dark rejimda ham mavzuga mos fon -->
  <div
    v-else
    class="grid h-dvh place-items-center bg-(--primary-bg) text-(--text-primary)"
  >
    {{ $t("mediaUnavailable") }}
  </div>
</template>

<script setup lang="ts">
import AudiobookPlayer from "~/components/views/books/details/AudiobookPlayer.vue";
import TextBookReader from "~/components/views/books/details/TextBookReader.vue";
import type { Book } from "~/types/app";

definePageMeta({
  layout: false,
});
const route = useRoute();

const {
  data: books,
  error: fetchError,
  refresh,
} = await useFetch<Book[]>("/api/books");
const book = computed(() =>
  books.value?.find((item) => item.id === Number(route.params.id)),
);
const showAudioPlayer = computed(
  () =>
    route.query.audible === "1" ||
    (book.value?.contentModes.audible && !book.value.contentModes.readable),
);

useHead({
  bodyAttrs: {
    class: "full-screen-page",
  },
});
</script>

<style lang="scss">
.full-screen-page {
  padding: 0;
  overflow: hidden;
}
</style>
