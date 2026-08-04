<template>
  <AudioPlayer
    :cover="book.image.original"
    :title="book.title"
    :subtitle="book.author"
    :src="book.audioUrl || ''"
    :back-to="{ name: 'books' }"
  />
</template>

<script setup lang="ts">
import type { Book } from "~/types/app";

defineProps<{
  book: Book;
}>();
</script>
