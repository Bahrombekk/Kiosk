import type {
  Ad,
  Book,
  TrainRoute,
  TrainStop,
  Video,
  Website,
} from "~/types/app";

/**
 * Python (FastAPI) backend qaytaradigan xom yozuvlarni frontend tiplariga
 * (types/app.ts) o'giradi. Frontend komponentlari o'zgarmaydi — mapping shu
 * yerda markazlashgan.
 */

/** Python `content` jadvalining bir yozuvi (db.py 10-bo'lim sxemasi). */
export interface BackendContent {
  id: number;
  type: string; // movie|cartoon|music|book|audiobook
  title: string;
  author?: string | null;
  genre?: string | null;
  description?: string | null;
  duration?: number | null; // soniya
  pages?: number | null;
  cover_path?: string | null;
  file_path?: string | null;
  text_path?: string | null;
  lang?: string | null; // uz|ru|en; null = barcha tillar
  is_recommended?: number;
}

export interface BackendSite {
  id: number;
  name: string;
  url: string;
  description?: string | null;
  features?: string | null;
  icon?: string | null;
}

export interface BackendAd {
  id: number;
  title?: string | null;
  media_type?: "image" | "video" | null;
  placement?: string | null;
  duration?: number | null;
  interval_min?: number | null;
  start_time?: string | null;
  end_time?: string | null;
  link_url?: string | null;
}

export interface BackendStop {
  name: string;
  arrival_time?: string | null;
  departure_time?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  distance_km?: number | null;
}

export interface BackendStatus {
  speed?: number;
  temperature?: number;
  wagon?: string | null;
  wagon_note?: string | null;
  current_stop?: string | null;
  train_name?: string | null;
  route?: string | null;
  blocked?: boolean;
}

// Video bo'limiga tushadigan kontent turlari
export const VIDEO_TYPES = ["movie", "cartoon", "music"];
// Kitoblar bo'limiga tushadigan turlar (matn va/yoki audio)
export const BOOK_TYPES = ["book", "audiobook"];

/** Muqova — brauzerga xavfsiz proksi URL (kalit server tomonda qo'shiladi). */
function coverUrl(id: number): { medium: string; original: string } {
  const u = `/api/cover/${id}`;
  return { medium: u, original: u };
}

/** Fayl kengaytmasidan MIME turini aniqlaydi (pleyerlar uchun kerak). */
function mimeFromPath(p?: string | null): string | undefined {
  const ext = p?.split(".").pop()?.toLowerCase();
  switch (ext) {
    case "mp4":
    case "m4v":
      return "video/mp4";
    case "webm":
      return "video/webm";
    case "mkv":
      return "video/x-matroska";
    case "mov":
      return "video/quicktime";
    case "mp3":
      return "audio/mpeg";
    case "wav":
      return "audio/wav";
    case "m4a":
      return "audio/mp4";
    case "ogg":
      return "audio/ogg";
    case "flac":
      return "audio/flac";
    default:
      return undefined;
  }
}

/** Janr satrini alohida janrlarga ajratadi ("Hujjatli, Tabiat" -> [..]). */
function splitGenres(g?: string | null): string[] {
  return (g || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

/** Admin kiritgan matndan HTML teglarni olib tashlaydi. Komponentlar endi
 * v-html ishlatmaydi ({{ }} bilan chiqaradi) — bu server tomondagi ikkinchi
 * himoya qatlami (stored-XSS oldini olish). */
function stripHtml(s?: string | null): string {
  return (s || "")
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function mapVideo(c: BackendContent): Video {
  return {
    id: c.id,
    name: c.title,
    image: coverUrl(c.id),
    summary: stripHtml(c.description),
    genres: splitGenres(c.genre),
    runtime: Math.round((c.duration || 0) / 60), // soniya -> daqiqa
    // Kiosk parity: tur (tab), til (filtr), tavsiya (Home)
    type: c.type,
    lang: c.lang ?? null,
    isRecommended: !!c.is_recommended,
    // Vidstack pleyer uchun: media Python `/api/stream/{id}` orqali striming
    // qilinadi (Range/seek qo'llanadi), tur fayl kengaytmasidan olinadi.
    // Fayl yo'q — mediaUrl ham yo'q: pleyer "media mavjud emas" ko'rsatadi
    // (avval 404 stream yoki demo klip o'ynardi).
    mediaUrl: c.file_path ? `/api/stream/${c.id}` : undefined,
    mediaType: mimeFromPath(c.file_path),
  };
}

export function mapBook(c: BackendContent): Book {
  return {
    id: c.id,
    title: c.title,
    author: c.author || "",
    image: coverUrl(c.id),
    description: stripHtml(c.description),
    pageCount: c.pages || 0,
    genre: (c.genre || "").trim(),
    contentModes: {
      readable: !!c.text_path,
      audible: !!c.file_path,
    },
    // Kiosk parity: tur, til (filtr), tavsiya (Home)
    type: c.type,
    lang: c.lang ?? null,
    isRecommended: !!c.is_recommended,
    // Audiokitob pleyeri (wavesurfer) va matn o'quvchi uchun manba URL'lar.
    // Matn TextBookReader tomonidan textUrl'dan tekis matn sifatida olinadi.
    audioUrl: c.file_path ? `/api/stream/${c.id}` : undefined,
    textUrl: c.text_path ? `/api/book/${c.id}/text` : undefined,
  };
}

function hostOf(url: string): string {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function mapWebsite(s: BackendSite): Website {
  return {
    id: s.id,
    name: s.name,
    link: s.url,
    link_title: hostOf(s.url),
    description_short: s.description || "",
    description: s.features || s.description || "",
  };
}

export function mapAd(a: BackendAd): Ad {
  return {
    id: a.id,
    title: a.title || `Reklama ${a.id}`,
    ad_image_link: `/api/ad-media/${a.id}`,
    placement: a.placement || "popup",
    mediaType: a.media_type || "image",
    duration: a.duration ?? 10,
    intervalMin: a.interval_min ?? null,
    startTime: a.start_time ?? null,
    endTime: a.end_time ?? null,
    link: a.link_url ?? null,
  };
}

/** Bekat vaqti "HH:MM" ko'rinishida (kelish, bo'lmasa jo'nash). */
function stopEta(s: BackendStop): string {
  return (s.arrival_time || s.departure_time || "").slice(0, 5);
}

/**
 * Python bekatlar ro'yxati + joriy status'dan frontend TrainRoute quradi.
 * `current_stop` (nomi bo'yicha) topilib, undan oldingi bekatlar "passed".
 */
export function mapRoute(
  stops: BackendStop[],
  status: BackendStatus | null,
): TrainRoute {
  const currentName = status?.current_stop || "";
  // Joriy bekat noma'lum bo'lsa (status yo'q / nom mos kelmadi) -1 qoladi —
  // avvalgi `= 0` fallback birinchi bekatni (va `<=` joriy bekatni ham)
  // noto'g'ri "o'tilgan" deb belgilar edi.
  const currentIdx = stops.findIndex((s) => s.name === currentName);

  const mapped: TrainStop[] = stops.map((s, i) => ({
    name: s.name,
    lat: s.latitude ?? 0,
    lng: s.longitude ?? 0,
    eta: stopEta(s),
    // Joriy bekat ham "yetib kelingan" (yashil chiziq/checkmark unga qadar)
    passed: currentIdx >= 0 && i <= currentIdx,
  }));

  const last = stops[stops.length - 1];
  return {
    departure: stops[0]?.name || "",
    destination: last?.name || "",
    totalDistanceKm: last?.distance_km ?? 0,
    currentProgressKm:
      currentIdx >= 0 ? (stops[currentIdx]?.distance_km ?? 0) : 0,
    stops: mapped,
  };
}
