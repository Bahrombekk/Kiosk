import type { Component } from "vue";

export type IconComponent = Component | string;

export type IconItem = {
  key: string;
  label: string;
  icon: IconComponent;
};

export type NavItem = {
  to: string;
  labelKey: string;
  icon: IconComponent;
};

export type MediaImage = {
  medium: string;
  original: string;
};

export type Book = {
  id: number;
  title: string;
  author: string;
  image: MediaImage;
  description: string;
  pageCount: number;
  genre: string;
  contentModes: {
    audible: boolean;
    readable: boolean;
  };
  // Kiosk parity: til filtri va tavsiya bo'limi uchun
  type: string; // book | audiobook
  lang: string | null; // uz|ru|en; null = barcha tillar
  isRecommended: boolean;
  audioUrl?: string;
  audioPeaks?: number[];
  textUrl?: string;
  textContent?: string;
  chapterTitle?: string;
};

export type Video = {
  id: number;
  name: string;
  image: MediaImage;
  summary: string;
  genres: string[];
  runtime: number;
  // Kiosk parity: tur (tab), til filtri, tavsiya
  type: string; // movie | cartoon | music
  lang: string | null; // uz|ru|en; null = barcha tillar
  isRecommended: boolean;
  mediaUrl?: string;
  mediaType?: string;
};
export type VideoGenreSection = {
  category: string;
  count: number;
  videos: Video[];
};

export type AudioTrack = {
  id: number;
  title: string;
  subtitle?: string;
  cover: string;
  src: string;
};

export type Website = {
  id: number;
  name: string;
  link: string;
  link_title: string;
  description_short: string;
  description: string;
};
export type ScanInstruction = {
  step: number;
  label: string;
};

export type Ad = {
  id: number;
  title: string; // proof-of-play statistikasi shu nom bo'yicha guruhlanadi
  ad_image_link: string;
  placement: string; // banner | popup | both
  mediaType: string; // image | video
  duration: number; // soniya
  intervalMin: number | null; // har necha daqiqada (bo'sh = umumiy sozlama)
  startTime: string | null; // HH:MM
  endTime: string | null; // HH:MM
  link: string | null;
};

export type TrainStop = {
  name: string;
  lat: number;
  lng: number;
  eta: string;
  passed: boolean;
};

export type TrainStatus = {
  speed: number;
  temperature: number;
  wagon: string | null;
  wagon_note: string | null;
  current_stop: string | null;
  train_name: string | null;
  route: string | null;
  blocked: boolean;
};

export type TrainRoute = {
  departure: string;
  destination: string;
  totalDistanceKm: number;
  currentProgressKm: number;
  stops: TrainStop[];
};
