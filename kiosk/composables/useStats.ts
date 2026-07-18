/**
 * useStats — veb foydalanish statistikasi (kiosk services/stats.py veb muqobili).
 *
 * - device_id: brauzer localStorage'idagi barqaror `web-<uuid>` — noyob
 *   foydalanuvchi (unique visitor) o'lchovi. Har telefon/brauzer bir marta
 *   yaratadi va saqlaydi; kesh tozalansa qayta sanaladi (sanoat standarti).
 * - Eventlar navbatga qo'shiladi (localStorage), davriy ravishda `/api/stats`
 *   (Nitro proksi -> backend, source=web) ga batch bilan yuboriladi. Backend
 *   o'chiq bo'lsa navbat saqlanadi.
 * - Sessiya: birinchi eventda boshlanadi, `session_end` sahifa yopilganda yoki
 *   uzoq harakatsizlikda yuboriladi (davomiyligi bilan).
 *
 * State modul darajasida (singleton) — SPA bo'ylab bitta navbat/sessiya.
 */
const QUEUE_KEY = "kiosk_stats_queue";
const DEVICE_KEY = "kiosk_web_device_id";
const FLUSH_MS = 30_000;
const IDLE_END_MS = 5 * 60_000; // 5 daqiqa harakatsizlik -> sessiya tugadi
const MAX_QUEUE = 400;

// Backend STATS_EVENTS bilan mos bo'lishi shart (aks holda jim tashlanadi).
type StatEvent =
  | "session_start"
  | "session_end"
  | "screen_view"
  | "lang_change"
  | "content_open"
  | "ad_play"
  | "site_qr";

interface QueuedEvent {
  ts: string;
  session: string;
  event: StatEvent;
  data: Record<string, unknown>;
}

let queue: QueuedEvent[] = [];
let deviceId = "";
let sessionId = "";
let sessionStartMs = 0;
let lastActivityMs = 0;
let flushTimer: ReturnType<typeof setInterval> | undefined;
let started = false;

function uuid(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID().replace(/-/g, "").slice(0, 12);
  }
  return Math.random().toString(16).slice(2, 14);
}

function loadDeviceId(): string {
  try {
    let id = localStorage.getItem(DEVICE_KEY);
    if (!id) {
      id = "web-" + uuid();
      localStorage.setItem(DEVICE_KEY, id);
    }
    return id;
  } catch {
    return "web-" + uuid(); // localStorage yo'q (incognito) — sessiyalik id
  }
}

function loadQueue() {
  try {
    const raw = localStorage.getItem(QUEUE_KEY);
    queue = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(queue)) queue = [];
  } catch {
    queue = [];
  }
}

function saveQueue() {
  try {
    if (queue.length > MAX_QUEUE) queue = queue.slice(-MAX_QUEUE);
    localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
  } catch {
    /* kvota to'lgan / yo'q — statistika ikkilamchi, jim o'tamiz */
  }
}

function ensureSession() {
  const now = Date.now();
  // Uzoq harakatsizlikdan keyin yangi tashrif = yangi sessiya
  if (sessionId && now - lastActivityMs > IDLE_END_MS) {
    endSession();
  }
  if (!sessionId) {
    sessionId = uuid();
    sessionStartMs = now;
    pushRaw("session_start", { lang: currentLang() });
  }
  lastActivityMs = now;
}

function currentLang(): string {
  try {
    return useNuxtApp().$i18n?.locale?.value || "uz";
  } catch {
    return "uz";
  }
}

function pushRaw(event: StatEvent, data: Record<string, unknown>) {
  queue.push({
    ts: new Date().toISOString().slice(0, 19),
    session: sessionId,
    event,
    data,
  });
  saveQueue();
}

function endSession() {
  if (!sessionId) return;
  const dur = Math.round((Date.now() - sessionStartMs) / 1000);
  pushRaw("session_end", { duration_s: dur });
  sessionId = "";
  sessionStartMs = 0;
}

async function flush() {
  if (!queue.length) return;
  const batch = queue.slice(0, 200);
  try {
    await $fetch("/api/stats", {
      method: "POST",
      body: { device_id: deviceId, events: batch },
    });
    // Faqat yuborilgan qismni olib tashlaymiz (yuborish paytida yangi
    // eventlar qo'shilgan bo'lishi mumkin).
    queue = queue.slice(batch.length);
    saveQueue();
  } catch {
    /* backend o'chiq — navbat qoladi, keyingi siklda qayta urinamiz */
  }
}

/** Bitta hisob nuqtasi — komponentlardan chaqiriladi (content_open va h.k.). */
function track(event: StatEvent, data: Record<string, unknown> = {}) {
  if (!import.meta.client) return;
  ensureSession();
  pushRaw(event, data);
}

/** Plugin (stats.client.ts) bir marta chaqiradi — init + davriy flush. */
function initStats() {
  if (started || !import.meta.client) return;
  started = true;
  deviceId = loadDeviceId();
  loadQueue();
  ensureSession();
  flush(); // oldingi tashrifdan qolgan navbatni darhol yuborishga urinamiz
  flushTimer = setInterval(flush, FLUSH_MS);
  // Sahifa yopilishi/berkitilishi: sessiyani yakunlab, navbatni jo'natamiz.
  window.addEventListener("pagehide", () => {
    endSession();
    // sendBeacon — sahifa yopilayotganda ham yetib boradi
    try {
      if (queue.length && navigator.sendBeacon) {
        navigator.sendBeacon(
          "/api/stats",
          new Blob(
            [JSON.stringify({ device_id: deviceId, events: queue })],
            { type: "application/json" },
          ),
        );
        queue = [];
        saveQueue();
      }
    } catch {
      /* jim */
    }
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush();
  });
}

export function useStats() {
  return { track, initStats, flush };
}
