<template>
  <div
    class="h-full rounded-[24px] bg-(--surface-bg) p-[20px] shadow-[0_8px_32px_rgba(0,0,0,0.05)]"
  >
    <div class="flex flex-col gap-[20px]">
      <div class="text-[1.75rem]">{{ $t("weRecommend") }}</div>
      <!-- currentMovie yo'q bo'lsa /videos/undefined'ga o'tib ketmasin -->
      <div
        class="relative aspect-video w-full overflow-hidden rounded-[24px]"
        @click="currentMovie && navigateTo(`/videos/${currentMovie.id}`)"
      >
        <div
          class="absolute right-[8px] bottom-[8px] left-[8px] z-3 flex items-center justify-between rounded-[16px] border border-(--blurred-bg) bg-(--blurred-bg) px-[16px] py-[8px] backdrop-blur-[15px]"
        >
          <!-- .stop — busiz bosish ota div'ning navigateTo'siga ko'tarilib,
               "keyingi film" o'rniga pleyer sahifasi ochilib ketardi -->
          <UButton
            icon="i-lucide-chevron-left"
            color="neutral"
            variant="ghost"
            class="text-(--icon-active) hover:bg-white/20"
            @click.stop="handlePrev"
          />

          <div class="text-center">
            <h3
              class="text-(--text-primary) font-semibold text-[1rem] md:text-[1.25rem]"
            >
              {{ currentMovie?.name }}
            </h3>
            <p
              class="text-(--text-secondary) dark:text-(--text-primary) text-xs mt-0.5 font-medium"
            >
              {{ currentMovie ? formatVideoGenres(currentMovie.genres) : "" }}
              <span v-if="currentMovie">
                {{ formatVideoRuntime(currentMovie.runtime) }}
              </span>
            </p>
          </div>

          <UButton
            icon="i-lucide-chevron-right"
            color="neutral"
            variant="ghost"
            class="rounded-lg text-(--icon-active) hover:bg-white/20"
            @click.stop="handleNext"
          />
        </div>
        <UCarousel
          v-slot="{ item }"
          ref="carouselRef"
          autoplay
          loop
          :items="movies"
        >
          <div class="w-full">
            <img
              :src="item.image.original"
              loading="lazy"
              class="h-full w-full object-cover object-top"
            />
          </div>
        </UCarousel>
      </div>
      <div
        v-if="books?.length"
        class="relative grid w-full grid-cols-1 gap-[12px] overflow-hidden rounded-[12px] bg-(--text-primary) px-[16px] py-[20px] text-white sm:grid-cols-[30%_auto]"
      >
        <img
          :src="books[currentBookIndex]?.image.medium"
          :alt="books[currentBookIndex]?.title"
          class="absolute top-0 left-0 h-full w-full scale-[1.2] object-cover object-top blur-[5px]"
        />
        <img
          :src="books[currentBookIndex]?.image.original"
          :alt="books[currentBookIndex]?.title"
          class="z-3 mx-auto my-auto w-full rounded-[4px] border border-white/60 object-contain md:mx-0"
        />
        <div class="z-3 flex flex-col gap-[12px]">
          <div class="text-center md:text-left">
            <p class="m-0 text-[1.375rem] font-semibold">
              {{ books[currentBookIndex]?.title }}
            </p>
            <p class="m-0 text-[1rem] text-white/80">
              {{ books[currentBookIndex]?.author }}
            </p>
          </div>
          <div class="mt-auto flex flex-col gap-[12px]">
            <PrimaryActionButton
              v-if="books[currentBookIndex]?.contentModes.audible"
              :to="{
                name: 'books-id',
                params: { id: books[currentBookIndex]?.id },
                query: { audible: 1 },
              }"
              variant="warning"
              size="md"
            >
              <template #icon>
                <HeadphonesIcon class="h-[24px] w-[24px]" />
              </template>
              {{ $t("buttonActions.listen") }}
            </PrimaryActionButton>
            <PrimaryActionButton
              v-if="books[currentBookIndex]?.contentModes.readable"
              :to="{
                name: 'books-id',
                params: { id: books[currentBookIndex]?.id },
                query: { readable: 1 },
              }"
              variant="brand"
              size="md"
            >
              <template #icon>
                <BookOpenIcon class="h-[24px] w-[24px] pt-[5px]" />
              </template>
              {{ $t("buttonActions.read") }}
            </PrimaryActionButton>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import HeadphonesIcon from "~/assets/svg/headphones-alt.svg";
import BookOpenIcon from "~/assets/svg/book-open.svg";
import type { Book, Video } from "~/types/app";

const props = defineProps<{
  books: Book[] | undefined;
  movies: Video[] | undefined;
}>();

const books = computed(() => props.books);
const movies = computed(() => props.movies);
const { formatVideoGenres, formatVideoRuntime } = useVideoFormatting();

type CarouselApi = {
  selectedScrollSnap: () => number;
  on: (event: "select", callback: () => void) => void;
  off: (event: "select", callback: () => void) => void;
  scrollTo: (index: number) => void;
};

const carouselRef = useTemplateRef<{ emblaApi?: CarouselApi }>("carouselRef");
const currentBookIndex = ref(0);
const bookIntervalId = ref();

onMounted(() => {
  bookIntervalId.value = setInterval(() => {
    // Bo'sh ro'yxatda `x % 0 = NaN` bo'lib indeks abadiy buzilardi
    if (books.value?.length) {
      currentBookIndex.value =
        (currentBookIndex.value + 1) % books.value.length;
    }
  }, 10000);
});

// Ro'yxat kichraysa (masalan, til almashganda filtr) indeks chegaradan
// chiqib bo'sh karta ko'rsatilmasin
watch(books, (list) => {
  if (!list?.length) {
    currentBookIndex.value = 0;
  } else if (currentBookIndex.value >= list.length) {
    currentBookIndex.value = 0;
  }
});

onUnmounted(() => {
  clearInterval(bookIntervalId.value);
});

watchEffect((onCleanup) => {
  const embla = carouselRef.value?.emblaApi;
  if (!embla) return;

  const updateIndex = () => {
    activeIndex.value = embla.selectedScrollSnap();
  };
  embla.on("select", updateIndex);

  onCleanup(() => {
    embla.off("select", updateIndex);
  });
});

const activeIndex = ref(0);

const currentMovie = computed(() => {
  if (!movies.value) return;
  return movies.value[activeIndex.value];
});

const handlePrev = () => {
  if (!carouselRef.value?.emblaApi) return;
  if (!movies.value) return;

  if (activeIndex.value <= 0) {
    const lastIndex = movies.value.length - 1;
    activeIndex.value = lastIndex;
    carouselRef.value.emblaApi.scrollTo(lastIndex);
  } else {
    activeIndex.value--;
    carouselRef.value.emblaApi.scrollTo(activeIndex.value);
  }
};

const handleNext = () => {
  if (!carouselRef.value?.emblaApi) return;
  if (!movies.value) return;

  if (activeIndex.value >= movies.value.length - 1) {
    activeIndex.value = 0;
    carouselRef.value.emblaApi.scrollTo(0);
  } else {
    activeIndex.value++;
    carouselRef.value.emblaApi.scrollTo(activeIndex.value);
  }
};
</script>
