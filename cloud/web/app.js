/* KioskCloud admin paneli — build'siz vanilla JS.
 *
 * Tuzilishi:
 *   1) API klient          — /api/admin/* bilan ishlaydi (sessiya cookie)
 *   2) Ikonkalar           — lucide yo'llari (dizayn to'plami bilan bir xil)
 *   3) Holat (S) + render  — holat o'zgarsa sahifa qayta chiziladi
 *   4) Sahifalar           — Boshqaruv, Serverlar(+tafsilot), Kutubxona,
 *                            Navbat, Statistika, Loglar, Ulash kalitlari
 *   5) Modallar            — kontent yuklash, tarqatish (3 qadam), e'lon
 *
 * Hodisalar delegatsiya bilan: har bosiladigan element `data-act` beradi.
 * Shu sababli render'dan keyin listener qayta ulanmaydi (xotira oqmaydi).
 */
"use strict";

// Backend bilan bir xil bo'lishi kerak (cloud/main.py -> APP_BUILD). Statik
// fayllar diskdan o'qiladi va brauzer yangi UI'ni darhol oladi, lekin
// endpointlar faqat bulut QAYTA ISHGA TUSHGANDA yangilanadi — mos kelmasa
// yuqorida ogohlantirish chiqadi ("Not Found" bilan boshi qotmasin).
// ═══════════════════════════════════════════════════════════════════════════
//  MUNDARIJA (bo'limlar raqamlangan — "// ==== N)" ni qidiring)
//    1) API klient       — api.get/post/put/patch/del (X-API-Key sessiya-cookie)
//    2) Ikonkalar        — ic(name,...) SVG
//    3) Yordamchi        — esc() (XSS!), bytes, ago, donut/hbars grafiklar
//    4) Holat            — S (global state), PAGES
//    5) Yuklash          — load(): sahifaga qarab /api/admin/* tortadi
//    6) Render           — render() + pageDash/pageServers/pageServer/pageLibrary/
//                          pageQueue/pageStats/pageLogs/pageAds/pageSites/pageStops/pageTokens
//    7) Modallar         — kontent/reklama/sayt/bekat formalari
//    8) Hodisalar        — data-act klik handlerlari (bitta delegated listener)
//    9) Yuklashlar       — putBlob(), pickFiles() (fayl → /blob → kutubxona)
//   10) Boshla           — boot(), URL-hash marshrut
//  Vertikalga qarab yorliqlar: vmeta(s) (poyezd/avtobus). Server matni HTML'ga
//  chiqsa DOIM esc() bilan. Kesh-bust: UI_BUILD == cloud/main.py APP_BUILD.
// ═══════════════════════════════════════════════════════════════════════════
const UI_BUILD = "2026-08-07.4";

// ======================================================== 1) API klient
async function req(method, url, body) {
  const opt = { method, headers: {}, credentials: "same-origin" };
  if (body !== undefined) {
    opt.headers["Content-Type"] = "application/json";
    opt.body = JSON.stringify(body);
  }
  const r = await fetch(url, opt);
  if (r.status === 401) { S.auth = false; render(); throw new Error("kirish kerak"); }
  const txt = await r.text();
  let data = null;
  try { data = txt ? JSON.parse(txt) : null; } catch { data = null; }
  if (r.status === 404 && /^\/api\//.test(String(url))) {
    // Endpoint yo'q — deyarli har doim backend eski (UI diskdan yangilangan,
    // Python jarayoni esa yo'q). Aniq aytamiz.
    S.staleBackend = true;
    throw new Error("Bu imkoniyat backendda yo'q — bulutni QAYTA ISHGA "
                    + "TUSHIRING (statik UI yangilangan, Python jarayoni eski)");
  }
  if (!r.ok) throw new Error((data && (data.detail || data.error)) || `Xato ${r.status}`);
  return data;
}
const api = {
  get: (u) => req("GET", u),
  post: (u, b) => req("POST", u, b || {}),
  put: (u, b) => req("PUT", u, b || {}),
  patch: (u, b) => req("PATCH", u, b || {}),
  del: (u) => req("DELETE", u),
};

/** Faylni xom tana (PUT) bilan yuklaydi — progress uchun XHR. */
function putBlob(file, onPct) {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open("PUT", "/api/admin/blob?name=" + encodeURIComponent(file.name));
    x.upload.onprogress = (e) => {
      if (e.lengthComputable && onPct) onPct(Math.round(100 * e.loaded / e.total), e.loaded, e.total);
    };
    x.onload = () => {
      let d = null;
      try { d = JSON.parse(x.responseText); } catch { /* bo'sh */ }
      if (x.status >= 200 && x.status < 300) resolve(d);
      else reject(new Error((d && d.detail) || `Yuklash xatosi ${x.status}`));
    };
    x.onerror = () => reject(new Error("tarmoq xatosi"));
    x.send(file);
  });
}

// ========================================================= 2) Ikonkalar
const P = {
  layoutDashboard: "M3 3h7v7H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 14h7v7H3z",
  server: "M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01",
  clapperboard: "M4 8h16v12H4zM4 8l2-4h12l2 4M9 4l1 4M14 4l1 4",
  send: "M22 2 11 13M22 2l-7 20-4-9-9-4z",
  barChart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  fileText: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h4",
  lock: "M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4",
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14M20 20l-4.5-4.5",
  plus: "M12 5v14M5 12h14",
  check: "M4 12.5 9 17.5 20 6.5",
  x: "M6 6l12 12M18 6 6 18",
  refresh: "M20 12a8 8 0 1 1-2.3-5.6M20 4v4h-4",
  megaphone: "M4 10v4l12 5V5zM4 10H3v4h1M18 9a3 3 0 0 1 0 6",
  trash: "M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v6M14 11v6",
  image: "M3 5h18v14H3zM8.5 10a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3M21 15l-5-5L7 19",
  monitor: "M3 4h18v12H3zM8 20h8M12 16v4",
  wifi: "M2 8.5a15 15 0 0 1 20 0M5 12a10 10 0 0 1 14 0M8.5 15.5a5 5 0 0 1 7 0M12 19h.01",
  copy: "M9 9h11v11H9zM5 15H4V4h11v1",
  save: "M5 3h11l3 3v15H5zM8 3v6h8M8 15h8",
  pencil: "M4 20h4L20 8l-4-4L4 16zM14 6l4 4",
  music: "M9 18V5l10-2v13M9 18a3 3 0 1 1-3-3 3 3 0 0 1 3 3M19 16a3 3 0 1 1-3-3 3 3 0 0 1 3 3",
  bookOpen: "M12 6v14M12 6C10 4 7 4 3 5v13c4-1 7-1 9 1M12 6c2-2 5-2 9-1v13c-4-1-7-1-9 1",
  headphones: "M4 15v-3a8 8 0 0 1 16 0v3M4 15h3v6H5a1 1 0 0 1-1-1zM20 15h-3v6h2a1 1 0 0 0 1-1z",
  star: "m12 3 2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.8l6.5-.9z",
  globe: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M3 12h18M12 3c2.5 2.4 2.5 15.2 0 18M12 3c-2.5 2.4-2.5 15.2 0 18",
  mapPin: "M12 22s7-6.1 7-11a7 7 0 1 0-14 0c0 4.9 7 11 7 11M12 13a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5",
  disk: "M4 4h16v16H4zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6M8 4v4h8V4",
  power: "M12 4v8M6.3 7.3a8 8 0 1 0 11.4 0",
  chevronRight: "M9 5l7 7-7 7",
  chevronLeft: "M15 5l-7 7 7 7",
  menu: "M4 7h16M4 12h16M4 17h16",
  clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M12 7v5l3.5 2",
  download: "M12 3v12M7 10l5 5 5-5M5 21h14",
};
function ic(name, size = 18, color = "currentColor", sw = 1.8) {
  // Bitta `d` ichida bir nechta subpath ("M…M…") bo'lishi normal — stroke bilan
  // to'g'ri chiziladi, shuning uchun yo'lni bo'lmaymiz.
  const d = P[name] || P.check;
  return `<svg class="ico" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none"
    stroke="${color}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round"
    style="flex:none"><path d="${d}"/></svg>`;
}

const TYPES = {
  movie: ["Kino", "#1D4ED8", "#DBEAFE", "clapperboard"],
  cartoon: ["Multfilm", "#7C3AED", "#EDE9FE", "star"],
  music: ["Musiqa", "#047857", "#D1FAE5", "music"],
  book: ["Kitob", "#B45309", "#FEF3C7", "bookOpen"],
  audiobook: ["Audiokitob", "#0F766E", "#CCFBF1", "headphones"],
};
const LANGS = { uz: "O'zbekcha", ru: "Ruscha", en: "Inglizcha" };

// Yuklash formasi turga qarab o'z yorliqlarini oladi (dizayn bo'yicha):
//   [nom yorlig'i, muallif yorlig'i, muqova yorlig'i]
const UT = {
  movie: ["Kino nomi", "Rejissor", "Afisha (poster)"],
  cartoon: ["Multfilm nomi", "Studiya", "Afisha (poster)"],
  music: ["Qo'shiq nomi", "Ijrochi", "Albom muqovasi"],
  book: ["Kitob nomi", "Muallif", "Muqova"],
  audiobook: ["Audiokitob nomi", "Muallif", "Muqova"],
};
const GENRES = ["Drama", "Komediya", "Jangari", "Tarixiy", "Sarguzasht",
                "Ilmiy-fantastika", "Bolalar uchun", "Estrada", "Klassik",
                "Ma'rifiy"];
const TABS = ["Kinolar", "Multfilmlar", "Musiqa", "Kitoblar", "Audiokitoblar",
              "Yangi"];

// =========================================================== 3) Yordamchi
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function bytes(n) {
  n = Number(n) || 0;
  if (n >= 1024 ** 3) return (n / 1024 ** 3).toFixed(1) + " GB";
  if (n >= 1024 ** 2) return (n / 1024 ** 2).toFixed(0) + " MB";
  if (n >= 1024) return (n / 1024).toFixed(0) + " KB";
  return n + " B";
}

// --- Bekat koordinatalari: O'zbekiston temir yo'l bekatlari ro'yxati ---
// (server/assets/uz_stations.json nusxasi). Nom tanlanganда lat/lng avtomatik
// to'ladi va masofa (km) haversine bilan hisoblanadi — xarita to'g'ri chiqadi.
async function loadStations() {
  if (S.stations) return;
  try {
    const r = await fetch("/static/uz_stations.json");
    const d = await r.json();
    const list = (d && d.stations) || [];
    S.stations = list;
    S.stationMap = {};
    list.forEach((s) => { S.stationMap[(s.name || "").toLowerCase()] = s; });
  } catch (e) { S.stations = []; S.stationMap = {}; }
}
function stationByName(name) {
  return (S.stationMap || {})[String(name || "").trim().toLowerCase()] || null;
}
/** Ikki koordinata orasidagi masofa (km, haversine). */
function haversineKm(a, b) {
  if (a.lat == null || b.lat == null) return null;
  const R = 6371, rad = (x) => x * Math.PI / 180;
  const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng);
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat))
    * Math.sin(dLng / 2) ** 2;
  return Math.round(R * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s)));
}
function dur(sec) {
  sec = Number(sec) || 0;
  if (!sec) return "";
  const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
           : `${m}:${String(s).padStart(2, "0")}`;
}
function parseDur(v) {
  v = String(v || "").trim();
  if (!v) return 0;
  if (/^\d+$/.test(v)) return parseInt(v, 10);
  const p = v.split(":").map((x) => parseInt(x, 10) || 0);
  return p.length === 3 ? p[0] * 3600 + p[1] * 60 + p[2] : p[0] * 60 + (p[1] || 0);
}
/** "3 daqiqa oldin" ko'rinishi (SQLite 'YYYY-MM-DD HH:MM:SS' lokal vaqt). */
function ago(ts) {
  if (!ts) return "hech qachon";
  const t = new Date(String(ts).replace(" ", "T"));
  if (isNaN(t)) return String(ts);
  const s = Math.max(0, (Date.now() - t.getTime()) / 1000);
  if (s < 45) return "hozir";
  if (s < 3600) return Math.round(s / 60) + " daq oldin";
  if (s < 86400) return Math.round(s / 3600) + " soat oldin";
  return Math.round(s / 86400) + " kun oldin";
}
const clock = (ts) => String(ts || "").slice(11, 19) || String(ts || "").slice(0, 10);
/** Qurilma HOZIR faolmi — oxirgi hodisasi `mins` daqiqa ichidami (real vaqt).
 *  `ago()` bilan bir xil tahlil (mos bo'lsin). */
function liveWithin(ts, mins = 5) {
  const t = new Date(String(ts).replace(" ", "T"));
  return !isNaN(t) && (Date.now() - t.getTime()) < mins * 60000;
}

// ---- Analitika: yorliq xaritalari + diagramma yordamchilari ----
const CHART_COLORS = ["#2563EB", "#7C3AED", "#047857", "#B45309", "#DB2777",
                      "#0891B2", "#65A30D", "#DC2626", "#475569"];
const AD_PLACE_LBL = { banner: "Banner", popup: "Popup", pre: "Kino boshi",
  mid: "Kino o'rtasi", end: "Kino oxiri", media: "Kino ichida", both: "Popup+Banner" };
const EVENT_LBL = { content_open: "Kontent ochilishi", ad_play: "Reklama",
  site_qr: "Sayt QR", qr_route: "Bekat QR", sos_open: "SOS", lang_change: "Til almashish" };
const SCREEN_LBL = { home: "Asosiy", videos: "Videolar", books: "Kitoblar",
  music: "Musiqa", sites: "Saytlar", map: "Xarita", settings: "Sozlamalar" };
const clabel = (map, k) => map[k] || (k == null ? "—" : String(k));

/** SVG donut (halqa) diagramma + yonida yozuvlar. segs=[{label,n}]. */
function donut(segs, centerLabel = "jami") {
  segs = (segs || []).filter((s) => s.n > 0);
  const total = segs.reduce((a, s) => a + s.n, 0);
  if (!total) return `<div class="empty">Ma'lumot yo'q</div>`;
  const R = 54, C = 2 * Math.PI * R;
  let off = 0;
  const arcs = segs.map((s, i) => {
    const len = C * (s.n / total);
    const col = s.color || CHART_COLORS[i % CHART_COLORS.length];
    const el = `<circle r="${R}" cx="70" cy="70" fill="none" stroke="${col}"
      stroke-width="20" stroke-dasharray="${len} ${C - len}"
      stroke-dashoffset="${-off}" transform="rotate(-90 70 70)"></circle>`;
    off += len; return el;
  }).join("");
  const legend = segs.map((s, i) => {
    const col = s.color || CHART_COLORS[i % CHART_COLORS.length];
    return `<div class="row" style="gap:8px;padding:3px 0">
      <span class="dotm" style="background:${col}"></span>
      <div style="flex:1;min-width:0" class="dim">${esc(s.label)}</div>
      <div class="strong mono">${s.n}</div>
      <div class="dim mono" style="width:42px;text-align:right">${
        Math.round(100 * s.n / total)}%</div></div>`;
  }).join("");
  return `<div class="donutwrap">
    <svg viewBox="0 0 140 140" width="132" height="132">${arcs}
      <text x="70" y="66" text-anchor="middle" style="font:800 22px Unbounded,sans-serif;fill:var(--text)">${total}</text>
      <text x="70" y="86" text-anchor="middle" style="font:700 10px Manrope,sans-serif;fill:var(--muted)">${esc(centerLabel)}</text>
    </svg>
    <div class="donut-legend">${legend}</div></div>`;
}

/** Gorizontal bar ro'yxati (eng ko'p ekranlar/saytlar). items=[{label,n}]. */
function hbars(items) {
  items = items || [];
  if (!items.length) return `<div class="empty">Ma'lumot yo'q</div>`;
  const max = Math.max(...items.map((x) => x.n), 1);
  return items.map((x, i) => `<div class="hbar">
    <div class="hbar-top"><span class="lbl">${esc(x.label)}</span>
      <span class="val">${x.n}</span></div>
    <div class="hbar-track"><i style="width:${Math.max(3, 100 * x.n / max)}%;
      background:${CHART_COLORS[i % CHART_COLORS.length]}"></i></div></div>`).join("");
}

/** Kartaga o'ralган statistika bloki. */
function statCard(title, body, sub) {
  return `<section class="card"><div class="card-head"><div>
    <div class="card-title">${title}</div>${sub
      ? `<div class="card-sub">${sub}</div>` : ""}</div></div>${body}</section>`;
}

/** Sessiya davomiyligi (boshlangan → oxirgi hodisa). */
function durText(a, b) {
  const t1 = new Date(String(a || "").replace(" ", "T"));
  const t2 = new Date(String(b || a || "").replace(" ", "T"));
  if (isNaN(t1) || isNaN(t2)) return "—";
  const m = Math.max(0, Math.round((t2 - t1) / 60000));
  if (m < 1) return "1 daq";
  return m >= 60 ? `${Math.floor(m / 60)} s ${m % 60} daq` : `${m} daq`;
}

function toast(msg, kind = "") {
  const box = document.querySelector(".toasts") || (() => {
    const d = document.createElement("div"); d.className = "toasts";
    document.body.appendChild(d); return d;
  })();
  const t = document.createElement("div");
  t.className = "toast " + kind;
  t.textContent = msg;
  box.appendChild(t);
  setTimeout(() => t.remove(), 4200);
}

// ============================================================= 4) Holat
const S = {
  auth: null,            // null = hali tekshirilmagan
  build: "",             // backend versiyasi (health)
  user: null,            // kim kirgan {username, role}
  loginUser: "",         // login maydonidagi qiymat (xatoda saqlanadi)
  remember: false,
  staleBackend: false,   // UI yangi, backend eski (qayta ishga tushirish kerak)
  page: "dash",
  serverId: null,        // tafsilot ochilgan server
  loading: false,
  err: "",
  data: {},              // sahifa ma'lumoti
  q: "",                 // qidiruv
  libType: "",           // kutubxona turi filtri
  logFilter: { level: "", server_id: "" },
  statDays: 14,
  statSource: "",        // "" = kiosk+veb, "kiosk", "web"
  statServer: "",        // "" = barcha serverlar, aks holda bitta server id
  srvForm: {},           // server sozlamalari formasidagi O'ZGARISHLAR
  stopsDraft: null,      // bekatlar jadvalining tahrirlanayotgan nusxasi
  schedule: { on: false, date: "", time: "", group: "" },  // rejalashtirish
  sel: new Set(),        // kutubxonada belgilangan id'lar
  modal: null,           // {kind:'upload'|'deploy'|'announce'|'token', ...}
  form: {},              // modal formasi qiymatlari
  // Yuklangan fayllar SLOT bo'yicha (dizaynda ham shunday: o'ngda muqova,
  // pastda media kartasi, kitob uchun matn qatori). Bir slotga yangi fayl
  // tashlansa eskisini almashtiradi.
  up: { media: null, cover: null, text: null, hero: null },
  pickKind: "",          // "" = kengaytmadan aniqlanadi, aks holda majburiy slot
  flags: { visible: true, rec: true, cache: true },
  pickAll: true,
  adPick: null,          // reklama qaysi serverlarga (Set)
  pickOff: {},           // deploy: o'chirilgan serverlar
  opts: { skip_existing: true },
  dstep: 1,
};

const NAV = [
  ["dash", "Boshqaruv", "layoutDashboard"],
  ["servers", "Serverlar", "server"],
  ["library", "Kontent", "clapperboard"],
  ["ads", "Reklama", "megaphone"],
  ["sites", "Saytlar", "globe"],
  ["queue", "Navbat", "send"],
  ["update", "Yangilanish", "download"],
  ["stats", "Statistika", "barChart"],
  ["logs", "Loglar", "fileText"],
  ["tokens", "Ulash kalitlari", "lock"],
];
const TITLES = {
  dash: ["Boshqaruv", "Barcha poyezd serverlari va kiosklar bir ekranda"],
  servers: ["Serverlar", "Har bir poyezd serveri va uning kiosklari"],
  library: ["Kontent kutubxonasi", "Bulutdagi manba katalog — shundan serverlarga tarqatiladi"],
  queue: ["Tarqatish navbati", "Faol va tugagan ishlar, jonli jarayon"],
  update: ["Yangilanish", "Dastur (Avtobus.exe) versiyasini masofadan yangilash"],
  stats: ["Statistika", "Barcha kiosklardan yig'ilgan foydalanish ma'lumoti"],
  logs: ["Loglar", "Serverlardan kelgan hodisalar"],
  tokens: ["Ulash kalitlari", "Yangi poyezd serverini bulutga ulash uchun bir martalik token"],
  server: ["Server tafsiloti", "Kiosklar, sozlamalar, veb, sessiyalar"],
  ads: ["Reklama", "Bulutdagi reklamalar — qaysi serverlarga ketishini belgilaysiz"],
  sites: ["Saytlar", "Kiosklardagi «Saytlar» bo'limi — barcha serverlarga bir xil ketadi"],
  stops: ["Bekatlar", "Shu poyezdning yo'nalish jadvali"],
};

// ============================================================ 5) Yuklash
async function load(silent) {
  if (!silent) { S.loading = true; render(); }
  try {
    if (S.page === "dash") S.data.dash = await api.get("/api/admin/overview");
    else if (S.page === "servers") S.data.servers = await api.get("/api/admin/servers");
    else if (S.page === "server") {
      S.data.server = await api.get("/api/admin/servers/" + S.serverId);
      const _vt = (S.data.server && S.data.server.server && S.data.server.server.vertical) || "train";
      S.data.brandingLib = await api.get(
        "/api/admin/branding/library?kind=hero&vertical=" + _vt);
    }
    else if (S.page === "library") {
      const p = new URLSearchParams();
      if (S.libType) p.set("type", S.libType);
      if (S.q) p.set("q", S.q);
      S.data.library = await api.get("/api/admin/content?" + p);
      S.data.servers = await api.get("/api/admin/servers");
    } else if (S.page === "queue") S.data.jobs = await api.get("/api/admin/jobs");
    else if (S.page === "update") {
      S.data.update = await api.get("/api/admin/update");
      S.data.servers = await api.get("/api/admin/servers");
    }
    else if (S.page === "stats") {
      const p = new URLSearchParams({ days: String(S.statDays) });
      if (S.statSource) p.set("source", S.statSource);
      if (S.statServer) p.set("server_id", S.statServer);
      S.data.stats = await api.get("/api/admin/stats?" + p);
      S.data.servers = await api.get("/api/admin/servers");
    }
    else if (S.page === "logs") {
      const p = new URLSearchParams({ limit: "200" });
      if (S.logFilter.level) p.set("level", S.logFilter.level);
      if (S.logFilter.server_id) p.set("server_id", S.logFilter.server_id);
      if (S.q) p.set("q", S.q);
      S.data.logs = await api.get("/api/admin/logs?" + p);
      S.data.servers = await api.get("/api/admin/servers");
    } else if (S.page === "tokens") S.data.tokens = await api.get("/api/admin/enroll-tokens");
    else if (S.page === "ads") {
      S.data.ads = await api.get("/api/admin/ads");
      S.data.servers = await api.get("/api/admin/servers");
    } else if (S.page === "sites") S.data.sites = await api.get("/api/admin/sites");
    else if (S.page === "stops") {
      S.data.stops = await api.get(`/api/admin/servers/${S.serverId}/stops`);
      S.data.server = await api.get("/api/admin/servers/" + S.serverId);
      await loadStations();
    }
    S.err = "";
  } catch (e) {
    S.err = e.message;
  } finally {
    S.loading = false;
    render();
  }
}

function go(page, id) {
  S.page = page;
  S.serverId = id || null;
  S.q = "";
  S.srvForm = {};
  document.body.classList.remove("nav-open");
  // Joriy bo'limni URL hashда saqlaymiz — refresh qilganда o'sha bo'limда
  // qoladi (avval har refresh «Boshqaruv»ga qaytarardi).
  try {
    const h = id ? `${page}/${encodeURIComponent(id)}` : page;
    if (location.hash.slice(1) !== h) history.replaceState(null, "", "#" + h);
  } catch (e) { /* hash yozib bo'lmasa — muhim emas */ }
  load();
}

// Ruxsat etilgan bo'lim kalitlari (hashдан tiklashда tekshiriladi)
const PAGES = ["dash", "servers", "server", "library", "queue", "stats",
               "logs", "tokens", "ads", "sites", "stops"];

/** URL hashдан joriy bo'limни (va server id'ни) tiklaydi. */
function restoreFromHash() {
  const parts = decodeURIComponent((location.hash || "").replace(/^#/, "")).split("/");
  if (parts[0] && PAGES.includes(parts[0])) {
    S.page = parts[0];
    if (parts[1]) S.serverId = parts[1];
  }
}

// ============================================================= 6) Render
/** Qayta chizishdan OLDIN saqlab qolinadigan holat.
 *
 *  Panel har 5 soniyada jonli yangilanadi va butun DOM qaytadan yasaladi.
 *  Hech narsa qilmasak scroll nolga qaytib "tepaga otib yuboradi", yozilayotgan
 *  maydondan fokus ham uchadi. Shuning uchun scroll, fokus va kursor joyini
 *  eslab qolib, chizilgandan keyin tiklaymiz. */
function _snapshot(app) {
  const page = app.querySelector(".page");
  const ae = document.activeElement;
  let sel = null, caret = null;
  if (ae && ae.dataset) {
    if (ae.dataset.srv) sel = `[data-srv="${ae.dataset.srv}"]`;
    else if (ae.dataset.bind) sel = `[data-bind="${ae.dataset.bind}"]`;
    else if (ae.dataset.act === "q") sel = '[data-act="q"]';
    if (sel) {
      try {
        caret = [ae.selectionStart, ae.selectionEnd];
      } catch { caret = null; }          // number/select — selection yo'q
    }
  }
  const modal = app.querySelector(".modal");
  return { scroll: page ? page.scrollTop : 0, sel, caret,
           modalScroll: modal ? modal.scrollTop : 0 };
}

function _restore(app, k) {
  const page = app.querySelector(".page");
  if (page && k.scroll) page.scrollTop = k.scroll;
  const modal = app.querySelector(".modal");
  if (modal && k.modalScroll) modal.scrollTop = k.modalScroll;
  if (!k.sel) return;
  const el = app.querySelector(k.sel);
  if (!el) return;
  el.focus({ preventScroll: true });
  if (k.caret) {
    try { el.setSelectionRange(k.caret[0], k.caret[1]); } catch { /* mumkin emas */ }
  }
}

function render() {
  const app = document.getElementById("app");
  const keep = _snapshot(app);
  app.className = "";
  if (S.auth === null) {
    app.className = "boot";
    app.textContent = "Yuklanmoqda…";
    return;
  }
  app.innerHTML = S.auth ? viewShell() : viewLogin();
  _restore(app, keep);
}

/** Kirish ekrani — chapda brend, o'ngda forma (dizayn 1a).
 *  Telefonда bitta ustunga tushadi (styles.css @media). */
function viewLogin() {
  const blocked = /juda ko'p urinish/i.test(S.err || "");
  const points = [
    ["server", "Obyekt o'zi ulanadi — oq IP kerak emas"],
    ["refresh", "Uzilsa navbatda turadi, o'zi davom etadi"],
    ["lock", "Har bir buyruq imzolangan (Ed25519)"],
  ];
  return `<div class="login-wrap"><div class="login-card">

    <aside class="login-brand">
      <div class="side-logo" style="padding:0 0 26px">
        <div class="side-mark">K</div>
        <div><div class="side-name">KioskCloud</div>
          <div class="side-sub">Markaziy boshqaruv</div></div>
      </div>
      <h2 class="login-h">Barcha kiosklar<br>bitta panelda</h2>
      <p class="login-p">Obyektlaringiz bulutga o'zi ulanadi — oq IP, port
        yoki VPN kerak emas.</p>
      <div style="margin-top:22px">
        ${points.map(([i, t]) => `<div class="login-pt">
          ${ic(i, 16, "#93C5FD")}<span>${t}</span></div>`).join("")}
      </div>
      <div class="login-spacer"></div>
      <div class="row" style="gap:8px">
        <span class="dot live"></span>
        <span style="color:#E2E8F0;font-size:12px;font-weight:700">Bulut ishlayapti</span>
        <span class="dim" style="margin-left:auto">${esc(S.build || "v1.0")}</span>
      </div>
    </aside>

    <form class="login-form" data-act="login">
      <h1>Kirish</h1>
      <p>Davom etish uchun login va parolni kiriting.</p>
      ${S.err ? `<div class="err-box">
        <b>${blocked ? "Vaqtincha bloklandi" : "Login yoki parol xato"}</b><br>
        <span style="font-weight:600">${esc(S.err)}</span></div>` : ""}
      <div class="field"><label>Login</label>
        <input name="username" value="${esc(S.loginUser || "")}"
          autocomplete="username" placeholder="admin" autofocus></div>
      <div class="field"><label>Parol</label>
        <input type="password" name="password" autocomplete="current-password"></div>
      <label class="row" style="gap:9px;margin:2px 0 18px;cursor:pointer">
        <input type="checkbox" name="remember" style="width:16px;height:16px">
        <span style="font-size:12.5px;font-weight:700">Meni eslab qol</span>
        <span class="dim" style="margin-left:auto">${S.remember ? "7 kun" : "12 soat"}</span>
      </label>
      <button class="btn pri" style="width:100%;justify-content:center;padding:13px"
        type="submit" ${blocked ? "disabled" : ""}>Kirish</button>
      ${blocked ? `<div class="dim" style="margin-top:16px;line-height:1.6">
        Blok IP bo'yicha qo'yiladi — 5 daqiqadan keyin qayta urinib ko'ring.
      </div>` : ""}
    </form>
  </div></div>`;
}

function viewShell() {
  const d = S.data.dash || {};
  const k = d.kpis || {};
  const jobs = (S.data.jobs || d.jobs || []).filter((j) => j.state === "running");
  // Sidebar badge'lari: Serverlar — jami soni (dizaynda «50»), Navbat — faol ish
  const badges = { servers: k.servers_total || "", queue: jobs.length || "" };
  const [title, sub] = TITLES[S.page] || ["", ""];
  return `<div class="shell">
    <aside class="side">
      <div class="side-logo">
        <div class="side-mark">K</div>
        <div><div class="side-name">KioskCloud</div>
          <div class="side-sub">Markaziy boshqaruv</div></div>
      </div>
      <nav class="side-nav">
        ${NAV.map(([id, label, icon]) => `
          <button class="nav-item ${S.page === id || (id === "servers" && S.page === "server") ? "on" : ""}"
                  data-act="go" data-page="${id}">
            ${ic(icon, 18)}<span class="lbl">${label}</span>
            ${badges[id] ? `<span class="nav-badge">${badges[id]}</span>` : ""}
          </button>`).join("")}
      </nav>
      <div class="side-spacer"></div>
      ${sideStatus(k)}
    </aside>
    <div class="main">
      <header class="top">
        <button class="burger" data-act="burger">${ic("menu", 18)}</button>
        <div><div class="top-title">${esc(title)}</div><div class="top-sub">${esc(sub)}</div></div>
        <div class="top-spacer"></div>
        ${["library", "logs"].includes(S.page) ? `
          <div class="search">${ic("search", 16, "#94A3B8")}
            <input placeholder="${S.page === "library" ? "Kontent nomi…" : "Log matni…"}"
                   value="${esc(S.q)}" data-act="q"></div>` : ""}
        ${S.page === "library" ? `
          <button class="btn" data-act="upload-open">${ic("plus", 16)} Kontent yuklash</button>` : ""}
        ${S.page === "dash" ? `
          <button class="btn" data-act="sync-all">${ic("refresh", 16)} Hammasini sinxronla</button>` : ""}
        ${S.page === "tokens" ? `
          <button class="btn pri" data-act="token-open">${ic("plus", 16)} Yangi kalit</button>` : ""}
        ${S.page === "ads" ? `
          <button class="btn pri" data-act="ad-new">${ic("plus", 16, "#fff")} Yangi reklama</button>` : ""}
        ${S.page === "sites" ? `
          <button class="btn pri" data-act="site-new">${ic("plus", 16, "#fff")} Yangi sayt</button>` : ""}
      </header>
      <main class="page">
        ${S.staleBackend ? `<div class="err-box" style="margin-bottom:14px">
          <b>Bulut backendi eski.</b> Brauzer yangi panelni oldi, lekin server
          jarayoni yangilanmagan — shu sababli ba'zi bo'limlar «Not Found»
          beradi. Terminalда bulutni to'xtatib qayta ishga tushiring:
          <code>py main.py</code>${S.build
            ? ` &nbsp;(backend: ${esc(S.build)}, panel: ${UI_BUILD})` : ""}
        </div>` : ""}
        ${S.err ? `<div class="err-box" style="margin-bottom:14px">${esc(S.err)}</div>` : ""}
        ${S.loading && !Object.keys(S.data).length
          ? `<div class="empty"><div class="spin dark" style="margin:0 auto 10px"></div>Yuklanmoqda…</div>`
          : pageBody()}
      </main>
    </div>
  </div>
  ${S.modal ? modalView() : ""}
  <div class="toasts"></div>`;
}

/** Sidebar pasti: bulut holati (progress bilan) + kim kirgan (dizayn bo'yicha). */
function sideStatus(k) {
  const on = k.servers_online || 0, total = k.servers_total || 0;
  const pct = total ? Math.round(100 * on / total) : 0;
  const off = Math.max(0, total - on);
  const u = S.user || {};
  const initials = (u.username || "A").slice(0, 2).toUpperCase();
  return `<div class="side-status">
    <div class="row" style="margin-bottom:9px">
      <span class="dot ${on ? "live" : "off"}"></span>
      <span class="side-status-title" style="flex:1">${
        on ? "Bulut ishlayapti" : "Server ulanmagan"}</span>
      <span class="side-nums"><b>${on}</b>/${total}</span>
    </div>
    <div class="side-bar"><i style="width:${pct}%"></i></div>
    <div class="side-status-note">${off
      ? `${off} ta obyekt SIM-signalsiz — navbat saqlanmoqda`
      : `${k.kiosks_online || 0} / ${k.kiosks_total || 0} kiosk onlayn`}</div>
    <div class="side-hr"></div>
    <div class="side-user">
      <div class="avatar">${esc(initials)}</div>
      <div style="flex:1;min-width:0">
        <div class="side-user-name">${esc(u.username || "Admin")}</div>
        <div class="side-user-role">${u.role === "super" ? "Super admin" : esc(u.role || "admin")}${
          u.ttl ? " · " + (u.ttl > 86400 ? Math.round(u.ttl / 86400) + " kun"
                                        : Math.round(u.ttl / 3600) + " soat") : ""}</div>
      </div>
      <button class="side-out" data-act="logout" title="Chiqish">
        ${ic("power", 15)}</button>
    </div>
  </div>`;
}

function pageBody() {
  switch (S.page) {
    case "dash": return pageDash();
    case "servers": return pageServers();
    case "server": return pageServer();
    case "library": return pageLibrary();
    case "queue": return pageQueue();
    case "update": return pageUpdate();
    case "stats": return pageStats();
    case "logs": return pageLogs();
    case "tokens": return pageTokens();
    case "ads": return pageAds();
    case "sites": return pageSites();
    case "stops": return pageStops();
    default: return "";
  }
}

// --------------------------------------------------------------- Yangilanish
/** Dastur (Avtobus.exe) versiyasini masofadan yangilash — kod-only paket. */
function pageUpdate() {
  const u = S.data.update || {};
  const servers = S.data.servers || [];
  const approved = servers.filter((s) => s.approved);
  const has = !!u.version;
  // Har bir qurilma versiyasini eng yangi yuklangан bilan solishtiramiz
  const statusOf = (s) => {
    const v = (s.version || "").trim();
    if (!v) return ["mut", "noma'lum"];
    if (!has) return ["acc", "v" + v];
    return verCmp(v, u.version) >= 0 ? ["ok", "Yangilangan"] : ["warn", "Eski"];
  };
  const nNew = has ? approved.filter((s) => (s.version || "") && verCmp(s.version, u.version) >= 0).length : 0;
  const nOld = has ? approved.length - nNew : 0;
  return `
  <div class="grid" style="gap:18px;max-width:920px">
  <div class="card">
    <div class="upd-hero">
      <div class="upd-ico">${ic("download", 24, "#fff")}</div>
      <div>
        <div style="font-family:Unbounded,sans-serif;font-size:16px;font-weight:600;letter-spacing:-.3px">Dastur yangilanishi</div>
        <div class="dim">Avtomatik — qurilma o'zi tortib olib o'rnatadi</div>
      </div>
    </div>
    <div class="dim" style="margin:14px 0 16px;line-height:1.6">
      Kod-only <b>AvtobusUpdate.exe</b> ni yuklang va qurilmalarga yuboring.
      Qurilma onlayn bo'lganda <b>o'zi</b> tortib oladi, sha256 tekshiradi va
      jimgina o'rnatadi — <b>qo'lda borish shart emas</b>. Ma'lumot (baza,
      kontent, litsenziya) saqlanadi. Offlayn bo'lsa navbatda turadi.
    </div>
    <div class="row" style="gap:12px;align-items:center;flex-wrap:wrap">
      <input id="upd-ver" placeholder="Yangi versiya (masalan 1.0.1)"
        value="${esc(u.version || "")}"
        style="padding:10px 13px;border:1px solid #e2e8f0;border-radius:11px;font-size:14px">
      <label class="btn pri" style="cursor:pointer">
        ${ic("download", 16, "#fff")} AvtobusUpdate.exe tanlash
        <input type="file" accept=".exe" data-act="update-file" style="display:none">
      </label>
    </div>
    <div id="upd-prog" class="dim" style="margin-top:12px"></div>
    ${has ? `<div class="card" style="margin-top:18px;background:#f8fafc;border:1px solid #eef2f7">
        <div style="font-weight:600;font-size:15px">Joriy yuklangan: v${esc(u.version)}</div>
        <div class="dim" style="margin-top:4px">${bytes(u.size)} · yuklangan ${esc(u.at || "")}</div>
        <div class="dim" style="word-break:break-all;margin-top:2px">sha256: ${esc((u.sha256 || "").slice(0, 24))}…</div>
        <button class="btn pri" style="margin-top:14px" data-act="update-push">
          ${ic("send", 15, "#fff")} ${approved.length} ta tasdiqlangan qurilmaga yuborish</button>
        <div class="dim" style="margin-top:8px">Faqat joriy versiyadan yuqori bo'lsa o'rnatiladi (pasaytirmaydi).</div>
      </div>`
    : `<div class="card empty" style="margin-top:18px">Hali yangilanish yuklanmagan —
        yuqoridan <b>AvtobusUpdate.exe</b> ni tanlang.</div>`}
  </div>

  <div class="card">
    <div class="row" style="margin-bottom:14px">
      <h3 class="sec-title" style="margin:0;flex:1">Qurilmalar versiyasi (${approved.length})</h3>
      ${has ? `<span class="pill ok">${nNew} yangilangan</span>
               ${nOld ? `<span class="pill warn">${nOld} eski</span>` : ""}` : ""}
    </div>
    ${approved.length ? `<div class="tbl-wrap"><table class="tbl">
      <thead><tr><th>Avtobus</th><th>Holat</th><th>Versiya</th><th>Yangilanish</th></tr></thead>
      <tbody>${approved.map((s) => {
        const [cls, txt] = statusOf(s);
        return `<tr>
          <td><b>${esc(s.name)}</b><div class="dim">${esc(s.route || "yo'nalish ko'rsatilmagan")}</div></td>
          <td>${s.online ? `<span class="pill ok">onlayn</span>`
                         : `<span class="pill mut">oflayn</span>`}</td>
          <td class="mono">${esc(s.version || "—")}</td>
          <td><span class="pill ${cls}">${txt}</span></td>
        </tr>`;
      }).join("")}</tbody></table></div>
      ${has ? `<div class="dim" style="margin-top:12px">Eng yangi yuklangan:
        <b>v${esc(u.version)}</b>. «Eski» qurilmalar keyingi «Yuborish»да yoki
        o'zi ulanganда yangilanadi.</div>` : ""}`
      : `<div class="empty">Tasdiqlangan qurilma yo'q.</div>`}
  </div>
  </div>`;
}

/** Versiyalarni solishtiradi: a<b -> -1, a==b -> 0, a>b -> 1 (1.0.10 > 1.0.9). */
function verCmp(a, b) {
  const pa = String(a).split("."), pb = String(b).split(".");
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (parseInt(pa[i]) || 0) - (parseInt(pb[i]) || 0);
    if (d) return d < 0 ? -1 : 1;
  }
  return 0;
}

/** AvtobusUpdate.exe ni xom tana (PUT) bilan yuklaydi — progress uchun XHR. */
function putUpdate(file, version, onPct) {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open("PUT", "/api/admin/update/upload?version=" + encodeURIComponent(version));
    x.upload.onprogress = (e) => {
      if (e.lengthComputable && onPct) onPct(Math.round(100 * e.loaded / e.total));
    };
    x.onload = () => {
      let d = null; try { d = JSON.parse(x.responseText); } catch { /* bo'sh */ }
      if (x.status >= 200 && x.status < 300) resolve(d);
      else reject(new Error((d && d.detail) || `Yuklash xatosi ${x.status}`));
    };
    x.onerror = () => reject(new Error("tarmoq xatosi"));
    x.send(file);
  });
}

// --------------------------------------------------------------- Boshqaruv
/** O'zi ulangan, hali tasdiqlanmagan serverlar — bir bosishda tasdiqlanadi. */
function pendingBlock(servers) {
  const pend = (servers || []).filter((s) => !s.approved);
  if (!pend.length) return "";
  return `<div class="card" style="margin-bottom:16px;border-left:4px solid var(--accent)">
    <div class="card-head">
      <div><div class="card-title">Yangi server ulanmoqchi — tasdiqlang
        (${pend.length})</div>
        <div class="card-sub">Bu qurilmalar bulut domenini bilib o'zi ulandi.
          Tasdiqlanmaguncha ularga kontent ham, buyruq ham yuborilmaydi.</div></div>
    </div>
    ${pend.map((s) => {
      const busHint = s.vertical === "bus";
      return `<div class="list-row wrap">
      <span class="dot ${s.online ? "live" : "off"}"></span>
      <div style="flex:1;min-width:0">
        <div class="strong">${esc(s.name)}</div>
        <div class="dim">${esc(s.id)} · versiya ${esc(s.version || "?")} ·
          o'zini «${busHint ? "Avtobus" : "Poyezd"}» deb bildirdi · ${ago(s.last_seen)}</div>
      </div>
      <button class="btn sm ghost" data-act="srv-reject" data-id="${s.id}">Rad etish</button>
      <button class="btn sm ${busHint ? "ghost" : "pri"}" data-act="srv-approve"
        data-id="${s.id}" data-vertical="train">${ic("check", 14, busHint ? undefined : "#fff", 2.6)} Poyezd sifatida</button>
      <button class="btn sm ${busHint ? "pri" : "ghost"}" data-act="srv-approve"
        data-id="${s.id}" data-vertical="bus">${ic("check", 14, busHint ? "#fff" : undefined, 2.6)} Avtobus sifatida</button>
    </div>`;
    }).join("")}
  </div>`;
}

function pageDash() {
  const d = S.data.dash;
  if (!d) return "";
  const k = d.kpis, st = d.storage || {};
  const kpi = (label, value, note) =>
    `<div class="kpi"><div class="kpi-label">${label}</div>
      <div class="kpi-value">${value}</div><div class="kpi-note">${note}</div></div>`;
  return `
  ${pendingBlock(d.servers)}
  <div class="grid k4">
    ${kpi("Serverlar", `${k.servers_online} / ${k.servers_total}`, "onlayn / jami")}
    ${kpi("Kiosklar", `${k.kiosks_online} / ${k.kiosks_total}`, "onlayn / jami")}
    ${kpi("Bugungi sessiyalar", k.sessions_today, "barcha poyezdlar")}
    ${kpi("Sinxronlanmagan", k.unsynced, k.unsynced ? "manifest kutilmoqda" : "hammasi joyida")}
  </div>

  <div class="grid split" style="margin-top:16px">
    <section class="card">
      <div class="card-head">
        <div><div class="card-title">Serverlar holati</div>
          <div class="card-sub">Har bir poyezd serveri va uning kiosklari</div></div>
        <a class="card-link" href="#" data-act="go" data-page="servers">Barchasi →</a>
      </div>
      ${d.servers.length ? d.servers.slice(0, 7).map(srvRow).join("")
        : `<div class="empty">Hali birorta server ulanmagan.<br>
             <b>Ulash kalitlari</b> bo'limidan token yarating.</div>`}
    </section>
    <div class="col" style="gap:16px">
      <section class="card">
        <div class="card-head">
          <div class="card-title">Tarqatish navbati</div>
          <span class="pill acc">${d.jobs.length} faol</span>
        </div>
        ${d.jobs.length ? d.jobs.map(jobMini).join("")
          : `<div class="empty">Faol ish yo'q</div>`}
      </section>
      <section class="card">
        <div class="card-head"><div class="card-title">Ombor</div></div>
        <div class="row"><div style="flex:1">
          <div class="dim">${st.files || 0} fayl · ${bytes(st.used)}</div>
          <div class="dim">diskda bo'sh: ${bytes(st.free)}</div>
        </div>${ic("disk", 28, "#94A3B8")}</div>
      </section>
      <section class="card">
        <div class="card-head"><div class="card-title">So'nggi hodisalar</div></div>
        ${(d.events || []).length ? d.events.map((e) => `
          <div class="row" style="padding:7px 0">
            <span class="dot ${e.kind === "err" ? "off" : e.kind === "warn" ? "sync" : "live"}"
                  style="animation:none"></span>
            <div style="flex:1;font-size:12.5px">${esc(e.text)}</div>
            <div class="dim">${ago(e.ts)}</div>
          </div>`).join("") : `<div class="empty">Hodisa yo'q</div>`}
      </section>
    </div>
  </div>`;
}

function srvRow(s) {
  const sync = s.synced ? "ok" : "warn";
  return `<div class="list-row click" data-act="go" data-page="server" data-id="${s.id}">
    <span class="dot ${s.online ? (s.synced ? "live" : "sync") : "off"}"></span>
    <div style="flex:1;min-width:0">
      <div class="strong">${esc(s.name)}</div>
      <div class="dim">${esc(s.route || "yo'nalish ko'rsatilmagan")}</div>
    </div>
    <div class="col-hide" style="text-align:right">
      <div style="font-size:12.5px">${s.kiosks_online}/${s.kiosks_total} kiosk</div>
      <div class="dim">${s.assigned} kontent</div>
    </div>
    <span class="pill ${sync}">${s.synced ? "sinxron" : "rev " + s.applied_rev + "→" + s.desired_rev}</span>
    <div class="dim mob-hide" style="width:88px;text-align:right">${ago(s.last_seen)}</div>
  </div>`;
}

function jobMini(j) {
  const pct = jobPct(j);
  return `<div style="padding:9px 0">
    <div class="row"><div style="flex:1;font-size:12.5px;font-weight:700">${esc(j.title || j.kind)}</div>
      <div class="dim">${pct}%</div></div>
    <div class="dim" style="margin:3px 0 6px">${j.n_done}/${j.n_targets} server · ${j.n_items} fayl</div>
    <div class="bar flow"><i style="width:${pct}%"></i></div>
  </div>`;
}
function jobPct(j) {
  if (!j.targets || !j.targets.length) return 0;
  return Math.round(j.targets.reduce((a, t) => a + (t.state === "done" ? 100 : t.pct || 0), 0)
                    / j.targets.length);
}

// --------------------------------------------------------------- Serverlar
function pageServers() {
  const list = S.data.servers || [];
  return `${pendingBlock(list)}
    <div class="row" style="margin-bottom:14px">
      <div class="dim">${list.length} server · ${list.filter((s) => s.online).length} onlayn</div>
      <div style="flex:1"></div>
      <button class="btn sm" data-act="sync-all">${ic("refresh", 14)} Hammasini sinxronla</button>
    </div>
    <div class="card" style="padding:14px 4px"><div class="tbl-wrap"><table class="tbl">
      <thead><tr>
        <th style="padding-left:14px">Server / poyezd</th><th>Kiosklar</th>
        <th>Sinxronizatsiya</th><th class="col-hide">Disk</th>
        <th class="col-hide">Litsenziya</th><th>Oxirgi ko'rilgan</th><th></th>
      </tr></thead><tbody>
      ${list.length ? list.map((s) => `<tr class="click" data-act="go" data-page="server" data-id="${s.id}">
        <td style="padding-left:14px"><div class="row">
          <span class="dot ${s.online ? (s.synced ? "live" : "sync") : "off"}"></span>
          <div><div class="strong">${esc(s.name)}</div>
            <div class="dim">${esc(s.route || "—")} · ${esc(s.id)}</div></div>
        </div></td>
        <td class="num">${s.kiosks_online}/${s.kiosks_total}</td>
        <td>${s.synced ? `<span class="pill ok">sinxron · ${s.assigned} fayl</span>`
                       : `<span class="pill warn">rev ${s.applied_rev} → ${s.desired_rev}</span>`}</td>
        <td class="col-hide"><div style="min-width:90px">
          <div class="bar ${s.disk_pct > 90 ? "err" : s.disk_pct > 75 ? "warn" : "ok"}">
            <i style="width:${s.disk_pct}%"></i></div>
          <div class="dim" style="margin-top:3px">${s.disk_pct}% · ${bytes(s.disk_free)} bo'sh</div>
        </div></td>
        <td class="col-hide">${licPill(s)}</td>
        <td class="dim">${ago(s.last_seen)}</td>
        <td>${ic("chevronRight", 16, "#94A3B8")}</td>
      </tr>`).join("") : `<tr><td colspan="7"><div class="empty">
          Server yo'q. <b>Ulash kalitlari</b> bo'limida token yaratib, poyezd
          serverida <code>KIOSK_CLOUD_URL</code> va tokenni ko'rsating.
        </div></td></tr>`}
      </tbody></table></div></div>`;
}

function licPill(s) {
  const l = (s.license || "").toLowerCase();
  if (l === "active") return `<span class="pill ok">Faol</span>`;
  if (l === "trial") return `<span class="pill warn">${esc(s.license_note || "Sinov")}</span>`;
  if (l === "expired") return `<span class="pill err">Muddati tugagan</span>`;
  if (l === "blocked") return `<span class="pill err">Bloklangan</span>`;
  return `<span class="pill mut">—</span>`;
}

// ---------------------------------------------------------- Server tafsiloti
function pageServer() {
  const d = S.data.server;
  if (!d) return "";
  const s = d.server;
  const stat = (label, value, note) =>
    `<div class="kpi"><div class="kpi-label">${label}</div>
      <div class="kpi-value">${value}</div>
      ${note ? `<div class="kpi-note">${note}</div>` : ""}</div>`;
  const ks = d.kiosks || [];
  const sess = d.kiosk_sessions || {};
  return `
  <a class="back" href="#" data-act="go" data-page="servers">← Serverlar ro'yxati</a>

  <div class="card srv-head">
    <div class="srv-ic">${ic("server", 22, "#fff")}</div>
    <div style="flex:1;min-width:200px">
      <div class="row wrap" style="gap:9px">
        <div class="top-title">${esc(s.name)}</div>
        ${s.online ? `<span class="pill ok">Onlayn</span>`
                   : `<span class="pill mut">Offlayn</span>`}
        ${s.approved ? "" : `<span class="pill warn">tasdiqlanmagan</span>`}
        ${s.synced ? "" : `<span class="pill warn">rev ${s.applied_rev}→${s.desired_rev}</span>`}
        ${licPill(s)}
      </div>
      <div class="dim" style="margin-top:4px">
        ${esc(s.route || "yo'nalish ko'rsatilmagan")} · ${esc(s.id)} ·
        v${esc(s.version || "?")} · oxirgi ko'rilgan ${ago(s.last_seen)}</div>
    </div>
    ${s.approved ? "" : `<button class="btn sm pri" data-act="srv-approve"
      data-id="${s.id}">${ic("check", 14, "#fff", 2.6)} Tasdiqlash</button>`}
    <button class="btn sm pri" data-act="cmd" data-kind="sync_now">
      ${ic("refresh", 14, "#fff")} Hoziroq sinxronla</button>
    <button class="btn sm" data-act="announce-open">${ic("megaphone", 14)} E'lon</button>
    <button class="btn sm" data-act="cmd" data-kind="cache_clear">
      ${ic("trash", 14)} Kesh tozalash</button>
    <button class="btn sm ghost" data-act="rename-open" title="Serverga nom berish">
      ${ic("pencil", 14)}</button>
    <button class="btn sm ghost" data-act="stops-open" title="Bekatlar jadvali">
      ${ic("mapPin", 14)}</button>
    <button class="btn sm ghost" data-act="srv-del" title="Ro'yxatdan o'chirish">
      ${ic("x", 14)}</button>
  </div>

  <div class="grid k4" style="margin-top:16px">
    ${stat("Kiosklar", `${s.kiosks_online} / ${s.kiosks_total}`)}
    ${stat("Bugungi sessiyalar", d.sessions_today)}
    ${stat("Kontent", s.assigned + " ta")}
    ${stat("Disk", s.disk_pct + "% band", bytes(s.disk_free) + " bo'sh")}
  </div>

  ${opsCard(d.ops)}
  ${srvWebCard(s)}
  ${srvMaintenanceCard(s)}
  ${srvSettingsCard(s)}
  ${srvBrandingCard(s, d.branding || {})}
  ${srvAdsCard(s)}
  ${srvLicenseCard(s)}

  <h3 class="sec-title">Kiosklar (${ks.length})</h3>
  ${ks.length ? `<div class="kgrid">${ks.map((k) => kioskCard(k, sess)).join("")}</div>`
    : `<div class="card empty">Kiosk ma'lumoti yo'q — kiosklar serverga
        ulanganda shu yerda o'zi paydo bo'ladi.</div>`}

  <h3 class="sec-title">Shu serverdagi kontent (${d.content.length})</h3>
  <div class="card" style="padding:14px 4px"><div class="tbl-wrap"><table class="tbl">
    <thead><tr><th style="padding-left:14px">Sarlavha</th><th>Turi</th><th>Til</th>
      <th>Hajm</th><th></th></tr></thead>
    <tbody>${d.content.length ? d.content.map((c) => `<tr>
      <td style="padding-left:14px" class="strong">${esc(c.title)}</td>
      <td>${typePill(c.type)}</td><td class="dim">${esc(LANGS[c.lang] || "Barcha")}</td>
      <td class="num">${bytes(c.media_size || c.text_size)}</td>
      <td><button class="btn sm danger" data-act="srv-remove-content" data-id="${c.id}">
        ${ic("trash", 13)} olib tashlash</button></td></tr>`).join("")
      : `<tr><td colspan="5"><div class="empty">Bu serverga hali kontent tayinlanmagan</div></td></tr>`}
    </tbody></table></div></div>

  ${srvLocalCatalogCard(d)}

  <h3 class="sec-title">Foydalanuvchi sessiyalari</h3>
  <div class="card" style="padding:14px 4px"><div class="tbl-wrap scroll-y">
    <table class="tbl">
    <thead><tr><th style="padding-left:14px">Kiosk</th><th>Boshlangan</th>
      <th>Davomiylik</th><th>Ko'rilgan kontent</th>
      <th class="col-hide">Hodisa</th><th>Til</th></tr></thead>
    <tbody>${d.sessions.length ? d.sessions.map((u) => {
      // Kiosk nomi (label yoki «Vagon N») — device_id o'rniga o'qiladigan nom
      const k = ks.find((x) => x.device_id === u.device_id) || {};
      const kn = k.label || (k.kiosk_no ? "Vagon " + k.kiosk_no : u.device_id);
      return `<tr>
      <td style="padding-left:14px" class="strong">${esc(kn || "—")}</td>
      <td class="dim">${esc(String(u.started || "").slice(5, 16).replace("T", " "))}</td>
      <td class="dim">${durText(u.started, u.ended)}</td>
      <td>${esc(u.content)}</td>
      <td class="col-hide num">${u.events}</td>
      <td class="dim">${esc((u.lang || "uz").toUpperCase())}</td>
      </tr>`;
    }).join("") : `<tr><td colspan="6"><div class="empty">Sessiya yo'q</div></td></tr>`}
    </tbody></table></div></div>

  <h3 class="sec-title">Shu serverning loglari</h3>
  ${logTable(d.logs, false)}`;
}

/** Poyezdda MAVJUD lokal katalog (serverdan telemetriya bilan keladi).
 *  Panel «bu serverда nima bor»ni ko'rsatadi — lokal qo'shilgan kontent ham
 *  ko'rinadi (avval faqat bulut tayinlagan kontent ko'rinardi). */
function srvLocalCatalogCard(d) {
  const lc = d.local_catalog;
  if (!lc) {
    return `<h3 class="sec-title">Poyezdda mavjud (lokal katalog)</h3>
      <div class="card empty">Server hali lokal katalogini yubormagan —
        eski versiya bo'lishi yoki ulanishni kutayotgan bo'lishi mumkin.</div>`;
  }
  const content = lc.content || [], ads = lc.ads || [], sites = lc.sites || [];
  const route = lc.route || {};
  const stopsN = (route["0"] || []).length + (route["1"] || []).length;
  const orig = (o) => o === "cloud" ? `<span class="pill acc">bulut</span>`
                                    : `<span class="pill mut">lokal</span>`;
  return `<h3 class="sec-title">Poyezdda mavjud (lokal katalog)</h3>
    <div class="card" style="margin-bottom:12px">
      <div class="card-sub">Server O'ZIDA hozir turgan kontent — poyezdда admin
        qo'lда qo'shган (<b>lokal</b>) va bulutdan kelган (<b>bulut</b>) birga.
        Faqat KO'RSATISH uchun; bulutdan boshqarish «Kontent» bo'limida.</div>
      <div class="row wrap" style="gap:8px;margin-top:10px">
        <span class="pill mut">${content.length} kontent</span>
        <span class="pill mut">${ads.length} reklama</span>
        <span class="pill mut">${sites.length} sayt</span>
        <span class="pill mut">${stopsN} bekat</span>
      </div>
    </div>
    <div class="card" style="padding:14px 4px"><div class="tbl-wrap${
      content.length > 14 ? " scroll-tall" : ""}"><table class="tbl">
      <thead><tr><th style="padding-left:14px">Sarlavha</th><th>Turi</th>
        <th>Manba</th><th>Holat</th></tr></thead>
      <tbody>${content.length ? content.map((c) => `<tr>
        <td style="padding-left:14px" class="strong">${esc(c.title || "(nomsiz)")}</td>
        <td>${typePill(c.type)}</td>
        <td>${orig(c.origin)}</td>
        <td>${c.visible ? `<span class="pill ok">ko'rinadi</span>`
                        : `<span class="pill warn">yashirin</span>`}</td>
      </tr>`).join("") : `<tr><td colspan="4"><div class="empty">
        Lokal kontent yo'q</div></td></tr>`}
      </tbody></table></div></div>`;
}

/** Kiosk kartochkasi (dizayn bo'yicha): holat · ko'rsatkichlar · buyruqlar.
 *  Jadval o'rniga kartochka — 8 vagonli poyezdda bir qarashda ko'rinadi. */
function kioskCard(k, sess) {
  const name = k.label || (k.kiosk_no ? "Vagon " + k.kiosk_no : k.device_id);
  const n = sess[k.device_id] || 0;
  // `cache_enabled` heartbeatда keladi. Eski serverdan kelmasa `undefined`
  // bo'ladi — u holda holatni "noma'lum" deb ko'rsatamiz, chunki "yoqilgan"
  // deb yozib qo'yish yolg'on bo'lardi.
  const cache = k.cache_enabled;
  const cacheOn = cache === 1 || cache === true;
  const cacheKnown = cache !== undefined && cache !== null;
  return `<article class="kcard">
    <div class="row" style="margin-bottom:3px">
      <span class="dot ${k.online ? "live" : "off"}"></span>
      <div class="strong" style="flex:1;min-width:0">${esc(name)}</div>
      <span class="pill ${k.online ? "ok" : "mut"}">${k.online ? "Onlayn" : "Offlayn"}</span>
    </div>
    <div class="dim" style="margin-bottom:12px">${esc(k.device_id)}${
      k.room ? " · xona " + esc(k.room) : ""} · ${ago(k.last_seen)}</div>

    <div class="kmetrics">
      <div><div class="kml">SESSIYALAR</div><div class="kmv">${n}</div></div>
      <div><div class="kml">KESHDA</div><div class="kmv">${k.cached_n} fayl</div></div>
      <div><div class="kml">BO'SH DISK</div><div class="kmv">${bytes(k.disk_free)}</div></div>
    </div>

    <div class="krow">
      <div style="flex:1;min-width:0">
        <div class="kml">LOKAL KESH</div>
        <div class="row" style="gap:7px;margin-top:3px">
          ${cacheKnown
            ? `<span class="pill ${cacheOn ? "ok" : "warn"}">${
                cacheOn ? "yoqilgan" : "o'chirilgan"}</span>
               <span class="dim">${cacheOn
                 ? "media kioskga yuklanadi" : "faqat serverdan striming"}</span>`
            : `<span class="pill mut">noma'lum</span>
               <span class="dim">server holatni hali yubormadi</span>`}
        </div>
      </div>
      <button class="btn sm ${cacheOn ? "ghost" : ""}" data-act="kiosk-cmd"
        data-dev="${esc(k.device_id)}"
        data-kind="${cacheOn ? "cache_off" : "cache_on"}">
        ${ic("power", 13)} ${cacheOn ? "O'chirish" : "Yoqish"}</button>
    </div>

    <div class="row" style="gap:7px;margin-top:12px;flex-wrap:wrap">
      <button class="btn sm ghost" data-act="kiosk-cmd" data-dev="${esc(k.device_id)}"
        data-kind="sync">${ic("refresh", 13)} Sinxronla</button>
      <button class="btn sm ghost" data-act="kiosk-cmd" data-dev="${esc(k.device_id)}"
        data-kind="cache_clear">${ic("trash", 13)} Keshni tozalash</button>
      <div style="flex:1"></div>
      <button class="btn sm ghost" data-act="klabel-open" data-dev="${esc(k.device_id)}"
        data-label="${esc(k.label || "")}" title="Nom berish">${ic("pencil", 13)}</button>
      <button class="btn sm ghost" data-act="kiosk-forget" data-dev="${esc(k.device_id)}"
        title="Ro'yxatdan olib tashlash">${ic("x", 13)}</button>
    </div>
  </article>`;
}

/** Vertikalga qarab yorliqlarni beradi (poyezd/avtobus). Bir platformada har xil
 *  qurilma turlari — server.vertical bo'yicha panel matnlari moslanadi. */
function vmeta(s) {
  const bus = (s && s.vertical) === "bus";
  return {
    bus,
    kind: bus ? "Avtobus" : "Poyezd",
    webTitle: bus ? "Veb ilova (avtobus.uz)" : "Veb ilova (poyezd.uz)",
    webDim: bus
      ? "Yo'lovchilar avtobus Wi-Fi'idan brauzer bilan kiradi."
      : "Yo'lovchilar vagon Wi-Fi'idan brauzer bilan kiradi. Node.js topilmasa ko'tarilmaydi.",
    maintTitle: bus ? "Texnik rejim (qulf)" : "Texnik rejim (kiosk qulf)",
    maintDim: bus
      ? "Yoqilса sayt yo'lovchilarga «Texnik ishlar» qulf ekрани chiqadi. Kontent o'chmaydi — o'chirsangiz o'zi ochiladi."
      : "Yoqilса barcha kiosklarга «Texnik ishlar» qulf ekрани chiqadi. Kontent o'chmaydi — o'chirsangiz o'zi ochiladi.",
    labels: bus
      ? { wagon_number: "Avtobus raqami", train_name: "Avtobus nomi", wagon_note: "Avtobus izohi" }
      : {},
    hide: bus ? ["kiosk_location", "media_cache"] : [],
    heroSub: bus
      ? "Avtobus veb-sahifasidagi katta banner. Yuklangan rasmlar shu yerda saqlanadi — bittasiga bosib shu serverga qo'yasiz."
      : "Poyezd.uz va kiosk asosiy sahifasidagi katta banner. Yuklangan rasmlar shu yerda saqlanadi — bittasiga bosib shu serverga qo'yasiz.",
  };
}

/** Veb ilova kartasi — holat + masofadan yoqish/o'chirish. */
function srvWebCard(s) {
  const on = !!s.web_running;
  const wanted = String((s.settings || {}).web_enabled ?? "1") !== "0";
  const M = vmeta(s);
  return `<h3 class="sec-title">${M.webTitle}</h3>
  <div class="card"><div class="row wrap">
    <span class="dot ${on ? "live" : "off"}"></span>
    <div style="flex:1;min-width:200px">
      <div class="strong">${on ? "Ishlayapti" : "Ishlamayapti"}
        ${!on && wanted ? `<span class="pill warn">yoqilgan, lekin ko'tarilmagan</span>` : ""}
        ${on && !wanted ? `<span class="pill warn">sozlamada o'chiq</span>` : ""}</div>
      <div class="dim">${M.webDim}</div>
    </div>
    <button class="btn sm" data-act="web-cmd" data-kind="start"
      ${on ? "disabled" : ""}>${ic("globe", 14)} Yoqish</button>
    <button class="btn sm ghost" data-act="web-cmd" data-kind="stop"
      ${on ? "" : "disabled"}>O'chirish</button>
  </div>
  ${schedPicker("web", "Masalan tunda o'chirib, ertalab yoqish")}
  </div>`;
}

/** Texnik rejim — kiosklarni masofadan qulflash ("Texnik ishlar" ekrani).
 *  Xavfsiz: kontent o'chmaydi, o'chirilганда o'zi ochiladi. Butunlay o'chirish
 *  (backend to'xtatish) ATAYLAB yo'q — poyezdда kiosk ishlamay qolmasин. */
function srvMaintenanceCard(s) {
  const on = String((s.settings || {}).maintenance ?? "0") === "1";
  const M = vmeta(s);
  const onTxt = M.bus
    ? (on ? "Yoqilgan — sayt qulflangan" : "O'chirilgan — sayt ishlayapti")
    : (on ? "Yoqilgan — kiosklar qulflangan" : "O'chirilgan — kiosklar ishlayapti");
  return `<h3 class="sec-title">${M.maintTitle}</h3>
  <div class="card"><div class="row wrap">
    <span class="dot ${on ? "" : "off"}"
      style="${on ? "background:var(--warn);animation:none" : ""}"></span>
    <div style="flex:1;min-width:220px">
      <div class="strong">${onTxt}</div>
      <div class="dim">${M.maintDim}</div>
    </div>
    <button class="btn sm ${on ? "ghost" : "danger"}" data-act="maint-cmd"
      data-on="1" ${on ? "disabled" : ""}>${ic("power", 14)} Qulflash</button>
    <button class="btn sm ${on ? "pri" : "ghost"}" data-act="maint-cmd"
      data-on="0" ${on ? "" : "disabled"}>Ochish</button>
  </div>
  ${schedPicker("maint", "Masalan tunda qulflab, ertalab ochish")}
  </div>`;
}

/** Serverning sozlamalari — masofadan tahrirlanadi. */
const SRV_FIELDS = [
  ["wagon_number", "Vagon raqami", "text", "12"],
  ["train_name", "Poyezd nomi", "text", "076Ф Afrosiyob"],
  ["route", "Yo'nalish", "text", "Toshkent — Xiva"],
  ["depart_time", "Jo'nash vaqti", "text", "08:30"],
  ["kiosk_location", "Kiosk joylashuvi", "text", "3-vagon, o'rta"],
  ["wagon_note", "Vagon izohi", "text", ""],
  ["speed_auto", "Tezlik avtomatik", "bool", ""],
  ["speed", "Tezlik (km/soat)", "num", "210"],
  ["weather_auto", "Ob-havo avtomatik", "bool", ""],
  ["temperature", "Harorat (°C)", "num", "22"],
  ["media_cache", "Kiosk lokal keshi", "bool", ""],
  ["cache_limit_gb", "Kesh chegarasi (GB)", "num", "50"],
  ["sos_enabled", "SOS tugmasi", "bool", ""],
  ["default_theme", "Standart mavzu (light/dark)", "text", "light"],
];

function srvSettingsCard(s) {
  const cur = s.settings || {};
  const v = (k) => (S.srvForm[k] !== undefined ? S.srvForm[k] : (cur[k] ?? ""));
  const M = vmeta(s);
  return `<h3 class="sec-title">Server sozlamalari</h3>
  <div class="card">
    <div class="list-row" style="border:0;padding:0 0 12px">
      <div style="flex:1"><div class="strong" style="font-size:12.5px">Qurilma turi</div>
        <div class="dim">Panel yorliqlari shunga qarab moslanadi</div></div>
      <div class="vseg">
        <button class="vseg-btn ${!M.bus ? "on" : ""}" data-act="srv-vertical"
          data-id="${s.id}" data-vertical="train" type="button">Poyezd</button>
        <button class="vseg-btn ${M.bus ? "on" : ""}" data-act="srv-vertical"
          data-id="${s.id}" data-vertical="bus" type="button">Avtobus</button>
      </div>
    </div>
    <div class="card-sub" style="margin-bottom:14px">Bu qiymatlar ${M.bus ? "avtobus" : "poyezd"}
      serveridan o'qildi. O'zgartirib «Yuborish»ni bosing — server ularni
      darhol qo'llaydi${M.bus ? "" : " va kiosklarga yetkazadi"}.</div>
    <div class="grid k3">
      ${SRV_FIELDS.filter(([k]) => !M.hide.includes(k)).map(([k, label0, kind, ph]) => {
        const label = M.labels[k] || label0;
        if (kind === "bool") {
          const on = String(v(k) ?? "1") !== "0";
          return `<div class="list-row" style="border:0;padding:6px 0">
            <div style="flex:1"><div class="strong" style="font-size:12.5px">${label}</div></div>
            <button class="tgl ${on ? "on" : ""}" data-act="srv-bool"
              data-key="${k}" data-val="${on ? "0" : "1"}"><i></i></button>
          </div>`;
        }
        return `<div class="field" style="margin:0">
          <label>${label}</label>
          <input data-srv="${k}" value="${esc(v(k))}" placeholder="${esc(ph)}"
            ${kind === "num" ? 'inputmode="numeric"' : ""}></div>`;
      }).join("")}
    </div>
    <div class="field full" style="margin:14px 0 0">
      <label>SOS raqamlari (har biri yangi qatorda)</label>
      <textarea data-srv="sos_numbers">${esc(v("sos_numbers"))}</textarea></div>
    ${saveRow("main")}
  </div>`;
}

/* Har bir sozlama kartasining O'Z saqlash qatori bor: shu kartada
   o'zgartirilgan maydonlar aynan shu tugma bilan yuboriladi. Avval bitta
   umumiy tugma edi va «Reklama sozlamalari» kartasida saqlash ko'rinmasdi. */
const FIELD_GROUPS = {
  main: [...SRV_FIELDS.map((f) => f[0]), "sos_numbers"],
  ads: ["ad_algorithm", "media_ad_slots", "ad_interval_min"],
  lic: ["trial_enabled", "trial_start", "trial_days"],
};

function dirtyKeys(group) {
  return (FIELD_GROUPS[group] || []).filter((k) => S.srvForm[k] !== undefined);
}

/** Modallar va kartalar uchun umumiy reja tanlagich (sana + vaqt).
 *  `group` — qaysi joy uchun (bir vaqtda faqat bittasi ochiq turadi). */
function schedPicker(group, note) {
  const on = S.schedule.on && S.schedule.group === group;
  return `<div class="list-row" style="margin-top:12px">
    <button class="tgl ${on ? "on" : ""}" data-act="sched-toggle"
      data-group="${group}" type="button"><i></i></button>
    <div style="flex:1;min-width:140px">
      <div class="strong" style="font-size:12.5px">Rejalashtirib yuborish</div>
      <div class="dim">${note || "O'chirilgan bo'lsa darhol (server offlayn "
        + "bo'lsa ulangan zahoti) qo'llanadi"}</div>
    </div>
    ${on ? `
      <input type="date" data-sched="date" value="${esc(S.schedule.date)}">
      <input type="time" data-sched="time" value="${esc(S.schedule.time)}">` : ""}
  </div>`;
}

/** Rejalashtirilgan bo'lsa `apply_at` qiymati, aks holda undefined. */
function schedValue(group) {
  if (!(S.schedule.on && S.schedule.group === group)) return undefined;
  if (!S.schedule.date) return undefined;
  return `${S.schedule.date} ${S.schedule.time || "00:00"}`;
}

function saveRow(group) {
  const keys = dirtyKeys(group);
  const n = keys.length;
  const sch = S.schedule.on && S.schedule.group === group;
  return `<div class="save-row">
    ${sch ? `<div class="row" style="gap:8px;flex:1;min-width:240px">
        ${ic("clock", 15, "#64748B")}
        <input type="date" data-sched="date" value="${esc(S.schedule.date)}">
        <input type="time" data-sched="time" value="${esc(S.schedule.time)}">
        <span class="dim">shu vaqtdan keyin qo'llanadi</span>
      </div>`
      : `<div class="dim" style="flex:1">${n
          ? `${n} maydon o'zgardi — hali yuborilmadi`
          : "O'zgarish yo'q"}</div>`}
    ${n ? `<button class="btn ghost sm" data-act="srv-reset" data-group="${group}">
      Bekor qilish</button>` : ""}
    <button class="btn sm" data-act="sched-toggle" data-group="${group}"
      ${n ? "" : "disabled"}>${ic("clock", 14)} ${sch
        ? "Rejani bekor qilish" : "Rejalashtirib saqlash"}</button>
    <button class="btn pri sm" data-act="srv-save" data-group="${group}"
      ${n ? "" : "disabled"}>${ic("send", 14, "#fff")} ${sch
        ? "Rejaga qo'yish" : "Hozir saqlash"}</button>
  </div>`;
}

/** Brending — asosiy sahifadagi hero banner rasmini almashtirish. */
/** Banner galereyasi — mavzu tanlagandek: yuklangan rasmlar saqlanib turadi,
 *  bittasiga bosib shu serverga qo'yiladi. Joriy rasm belgilangan bo'ladi. */
function srvBrandingCard(s, branding) {
  const hero = branding.hero;
  const lib = S.data.brandingLib || [];
  const up = S.up.hero;
  const curSha = hero && hero.sha;
  const M = vmeta(s);
  return `<h3 class="sec-title">Asosiy sahifa banneri (hero)</h3>
  <div class="card">
    <div class="card-sub" style="margin-bottom:14px">${M.heroSub}
      Reklama karuseli esa <b>Reklama</b> bo'limida.</div>
    <input type="file" accept="image/*" multiple class="u-hide" data-act="file-input">

    <div class="bgal">
      <!-- Standart: ilovaning O'ZIDAGI banner (brending qo'yilmaganda shu
           ko'rinadi). Katakchada aynan o'sha rasmning kichik nusxasi turadi. -->
      <div class="bthumb ${curSha ? "" : "on"}" data-act="hero-clear"
        title="Ilovadagi standart banner (dashboard-hero.png)">
        <div class="bthumb-img">
          <img src="${M.bus ? "/static/default-hero-bus.png" : "/static/default-hero.jpg"}"
            alt="" loading="lazy"></div>
        <div class="bthumb-n">Standart rasm</div>
        ${curSha ? "" : `<span class="bthumb-ok">${ic("check", 12, "#fff", 3)}</span>`}
      </div>

      ${lib.map((b) => `<div class="bthumb ${curSha === b.sha ? "on" : ""}"
          data-act="hero-pick" data-id="${b.id}"
          title="${esc(b.name || "")} · ${bytes(b.size)}">
        <div class="bthumb-img">
          <img src="/api/admin/branding/library/${b.id}/image" alt=""
            loading="lazy" onerror="this.remove()"></div>
        <div class="bthumb-n">${esc(b.name || "banner")}</div>
        ${curSha === b.sha ? `<span class="bthumb-ok">${ic("check", 12, "#fff", 3)}</span>`
          : ""}
        <button class="bthumb-x" data-act="hero-del" data-id="${b.id}"
          title="Kutubxonadan o'chirish">${ic("x", 11)}</button>
      </div>`).join("")}

      <!-- Yangi rasm qo'shish (eng ko'pi 5 ta; to'lса — o'chirib joy oching) -->
      ${lib.length < 5 || up ? `<div class="bthumb add ${up ? "on" : ""}"
          data-act="pick-hero">
        <div class="bthumb-img" style="display:grid;place-items:center">
          ${up && up.preview ? `<img src="${up.preview}" alt="">`
            : ic("plus", 22, "#94A3B8", 2.4)}</div>
        <div class="bthumb-n">${up
          ? (up.state === "up" ? up.pct + "% yuklanmoqda…" : esc(up.name))
          : "Yangi rasm"}</div>
      </div>` : `<div class="bthumb" style="display:grid;place-items:center;
          text-align:center;border-style:dashed">
        <div class="dim" style="padding:10px">Eng ko'pi 5 ta —<br>o'chirib
          joy oching</div></div>`}
    </div>

    <div class="row wrap" style="margin-top:14px;gap:12px">
      <div class="dim" style="flex:1;min-width:240px;line-height:1.6">
        Tavsiya: <b>1672 × 941</b> (16:9 ga yaqin), jpg yoki png. Matnsiz toza
        rasm bo'lsa yaxshi — ${M.bus ? "avtobus" : "poyezd"} nomi va bekatlar ustiga jonli yoziladi.
        ${lib.length ? `<br>Kutubxonada ${lib.length} banner.` : ""}
      </div>
      ${up && up.state === "done"
        ? `<button class="btn sm pri" data-act="hero-save">
            ${ic("send", 14, "#fff")} Yuklash va shu serverga qo'yish</button>` : ""}
    </div>
  </div>`;
}

/** Reklama sozlamalari — algoritm, media joylashuvi, oraliq. */
const AD_ALGOS = [
  ["weighted", "Vaznli — har reklamaning o'z oralig'i hisobga olinadi"],
  ["queue", "Navbat bilan — har oraliqda ro'yxatdagi keyingisi"],
  ["random", "Tasodifiy — har safar aralash tartibda"],
];
const AD_SLOTS = [["pre,mid,end", "Boshi + o'rtasi + oxiri"],
                  ["pre,mid", "Boshi + o'rtasi"], ["pre,end", "Boshi + oxiri"],
                  ["pre", "Faqat boshida"], ["mid,end", "O'rtasi + oxiri"],
                  ["end", "Faqat oxirida"]];

function srvAdsCard(s) {
  const cur = s.settings || {};
  const v = (k, d = "") => (S.srvForm[k] !== undefined ? S.srvForm[k] : (cur[k] ?? d));
  const algos = String(v("ad_algorithm", "weighted")).split(",")
    .map((x) => x.trim()).filter(Boolean);
  const slots = String(v("media_ad_slots", "pre,mid,end"));
  return `<h3 class="sec-title">Reklama sozlamalari</h3>
  <div class="card">
    <div class="card-sub" style="margin-bottom:14px">Reklamalarning O'ZI
      «Reklama» bo'limida — bu yerda ular <b>qanday ko'rsatilishi</b>
      boshqariladi. Saqlash uchun quyidagi «Yuborish» tugmasini bosing.</div>
    <div class="grid k2">
      <div>
        <label class="up-label" style="display:block;margin-bottom:8px">Popup
          reklama tartibi (bittasini tanlang)</label>
        ${AD_ALGOS.map(([k, t]) => `<div class="flag" data-act="algo-toggle"
            data-key="${k}" style="margin-bottom:10px">
          <span class="box ${algos.includes(k) ? "on" : ""}">${
            algos.includes(k) ? ic("check", 12, "#fff", 3.2) : ""}</span>
          <div class="flag-sub" style="margin:0;color:var(--text);font-weight:600">${t}</div>
        </div>`).join("")}
        <div class="hint" style="margin-top:6px">Reklama QAYERDA chiqishi (popup /
          banner / kino ichida) endi har reklamaning o'zida — «Reklama» bo'limида
          «Joylashuv» orqali tanlanadi.</div>
      </div>
      <div>
        <div class="field"><label>Reklama oralig'i (daqiqa)</label>
          <input data-srv="ad_interval_min" value="${esc(v("ad_interval_min", "10"))}"
            inputmode="numeric"></div>
        <div class="field"><label>Kino ichида reklama joylashuvi</label>
          <select data-srv="media_ad_slots">
            ${AD_SLOTS.map(([k, t]) => `<option value="${k}"
              ${slots === k ? "selected" : ""}>${t}</option>`).join("")}
          </select>
          <div class="hint">Media joylashuvли reklamalar kinoning qaysi qismида
            chiqishini belgilaydi (boshi / o'rtasi / oxiri).</div></div>
      </div>
    </div>
    ${saveRow("ads")}
  </div>`;
}

/** Litsenziya — holat, Qurilma ID, bloklash, license.key yuborish. */
function srvLicenseCard(s) {
  const li = s.license_info || {};
  const cur = s.settings || {};
  const v = (k, d = "") => (S.srvForm[k] !== undefined ? S.srvForm[k] : (cur[k] ?? d));
  const trialOn = String(v("trial_enabled", "0")) === "1";
  const blocked = String(v("trial_blocked", "0")) === "1" || li.blocked;
  const state = li.valid ? ["ok", "Yaroqli"]
    : li.present ? ["err", "Yaroqsiz"] : ["warn", "Fayl yo'q (dev rejim)"];
  return `<h3 class="sec-title">Litsenziya va bloklash</h3>
  <div class="card">
    <div class="row wrap" style="margin-bottom:14px">
      <span class="pill ${state[0]}">${state[1]}</span>
      ${blocked ? `<span class="pill err">KIOSKLAR BLOKLANGAN</span>` : ""}
      ${li.customer ? `<span class="dim">${esc(li.customer)}</span>` : ""}
      ${li.expires ? `<span class="dim">muddat: ${esc(li.expires)}${
        li.days_left != null ? ` (${li.days_left} kun)` : ""}</span>`
        : `<span class="dim">muddatsiz</span>`}
      ${li.max_kiosks ? `<span class="dim">kiosk limiti: ${li.max_kiosks}</span>` : ""}
      ${li.reason && !li.valid ? `<span class="dim">${esc(li.reason)}</span>` : ""}
    </div>

    <div class="field"><label>Qurilma ID (yangi license.key shu ID uchun yasaladi)</label>
      <div class="row" style="gap:8px">
        <input value="${esc(li.hw_id || "—")}" readonly id="hwid" style="flex:1">
        <button class="btn sm ghost" data-act="copy-hw">${ic("copy", 14)} Ko'chirish</button>
      </div></div>

    <div class="field"><label>license.key mazmunini shu yerga qo'ying</label>
      <textarea data-bind="lictext" rows="3"
        placeholder="KIOSK-LIC-v1.eyJ…  (vendor bergan fayl matni)"
        >${esc(F("lictext", ""))}</textarea>
      <div class="hint">Imzo serverда tekshiriladi — yaroqsiz fayl mavjud
        yaroqli litsenziyani almashtirmaydi.</div></div>
    <div class="row" style="margin-bottom:18px">
      <div style="flex:1"></div>
      <button class="btn sm pri" data-act="lic-send">
        ${ic("send", 14, "#fff")} Litsenziyani yuborish</button>
    </div>

    <div class="grid k3">
      <div class="list-row" style="border:0;padding:6px 0">
        <div style="flex:1"><div class="strong" style="font-size:12.5px">Sinov
          muddati nazorati</div></div>
        <button class="tgl ${trialOn ? "on" : ""}" data-act="srv-bool"
          data-key="trial_enabled" data-val="${trialOn ? "0" : "1"}"><i></i></button>
      </div>
      <div class="field" style="margin:0"><label>Boshlanish sanasi</label>
        <input data-srv="trial_start" value="${esc(v("trial_start"))}"
          placeholder="2026-08-01"></div>
      <div class="field" style="margin:0"><label>Necha kun</label>
        <input data-srv="trial_days" value="${esc(v("trial_days", "30"))}"
          inputmode="numeric"></div>
    </div>

    ${dirtyKeys("lic").length ? saveRow("lic") : ""}

    ${schedPicker("lic2", "Masalan to'lov kuni kelmasa — 1-sanada bloklash")}
    <div class="row" style="margin-top:16px">
      <div class="dim" style="flex:1">Bloklash DARHOL ishlaydi — kiosklarda
        qulf ekrani chiqadi (offlayn bo'lsa ulanganda).</div>
      ${blocked
        ? `<button class="btn sm" data-act="lic-block" data-val="0">
            ${ic("check", 14)} Blokni ochish</button>`
        : `<button class="btn sm danger" data-act="lic-block" data-val="1">
            ${ic("lock", 14)} Kiosklarni bloklash</button>`}
    </div>
  </div>`;
}

/** Navbatda turgan / rejalashtirilgan buyruqlar. */
function opsCard(ops) {
  if (!ops || !ops.length) return "";
  return `<h3 class="sec-title">Navbatda turgan buyruqlar (${ops.length})</h3>
  <div class="card">
    ${ops.map((o) => `<div class="list-row">
      ${ic(o.apply_at ? "clock" : "send", 17, "#475569")}
      <div style="flex:1;min-width:0">
        <div class="strong">${esc(o.label || o.kind)}</div>
        <div class="dim">${o.apply_at
          ? `rejalashtirilgan: <b>${esc(o.apply_at.slice(0, 16))}</b>`
          : "server onlayn bo'lishi bilan qo'llanadi"}
          · qo'shilgan ${esc(String(o.created_at || "").slice(5, 16))}</div>
      </div>
      <button class="btn sm ghost" data-act="op-cancel" data-id="${o.id}">
        Bekor qilish</button>
    </div>`).join("")}
  </div>`;
}

// -------------------------------------------------------------- Kutubxona
function typePill(t) {
  const [label, fg, bg] = TYPES[t] || ["?", "#475569", "#F1F5F9"];
  return `<span class="pill" style="color:${fg};background:${bg}">${label}</span>`;
}

function pageLibrary() {
  const list = S.data.library || [];
  const tabs = [["", "Barchasi"]].concat(Object.entries(TYPES).map(([k, v]) => [k, v[0]]));
  // Joriy ro'yxatdagi HAMMA element tanlanganmi (filtr/qidiruv bo'yicha)
  const allOn = list.length > 0 && list.every((c) => S.sel.has(c.id));
  return `
  <div class="filters">
    ${tabs.map(([k, label]) => `<button class="chip ${S.libType === k ? "on" : ""}"
        data-act="lib-type" data-type="${k}">${label}</button>`).join("")}
    ${list.length ? `<button class="chip ${allOn ? "on" : ""}" data-act="sel-all"
        style="margin-left:auto">${ic("check", 14, allOn ? "#fff" : "#64748b", 3)}
        ${allOn ? "Tanlovni olib tashlash" : `Barchasini tanlash (${list.length})`}</button>` : ""}
  </div>
  ${list.length ? `<div class="lib">${list.map(libCard).join("")}</div>`
    : `<div class="card empty">Kutubxona bo'sh — yuqoridagi
        <b>Kontent yuklash</b> tugmasi bilan birinchi faylni qo'shing.</div>`}
  ${S.sel.size ? `<div class="selbar">
      <div class="grow">${S.sel.size} ta tanlandi</div>
      <button class="btn sm ghost" style="color:#fff;border-color:#334155" data-act="sel-clear">Bekor qilish</button>
      <button class="btn sm danger" data-act="remove-open">${ic("trash", 14)} Kiosklardan o'chirish</button>
      <button class="btn sm pri" data-act="deploy-open">Tarqatish ${ic("chevronRight", 14, "#fff")}</button>
    </div>` : ""}`;
}

function libCard(c) {
  const [label, fg, bg, icon] = TYPES[c.type] || ["?", "#475569", "#F1F5F9", "clapperboard"];
  const on = S.sel.has(c.id);
  return `<article class="lib-card ${on ? "sel" : ""}" data-act="sel" data-id="${c.id}">
    <div class="lib-check">${on ? ic("check", 14, "#fff", 3) : ""}</div>
    <div class="lib-cover">
      ${c.cover_sha
        ? `<img src="/api/admin/cover/${c.id}" alt="" loading="lazy"
             onerror="this.remove()">`
        : `<div class="lib-noc">${ic(icon, 26, fg)}
             <span>Muqova yo'q</span></div>`}
      ${c.duration ? `<span class="lib-dur">${dur(c.duration)}</span>` : ""}
    </div>
    <div class="lib-body">
      <div class="lib-title">${esc(c.title)}</div>
      <div class="lib-meta">
        <span class="pill" style="color:${fg};background:${bg}">${label}</span>
        <span class="dim">${bytes(c.media_size || c.text_size)}</span>
      </div>
      <div class="row" style="margin-top:9px">
        <span class="dim" style="flex:1">${c.deployed} serverda</span>
        <button class="btn sm ghost" data-act="content-edit" data-id="${c.id}"
                title="Tahrirlash">${ic("pencil", 13)}</button>
        <button class="btn sm ghost" data-act="content-del" data-id="${c.id}"
                title="Kutubxonadan butunlay o'chirish">${ic("trash", 13)}</button>
      </div>
    </div>
  </article>`;
}

// ----------------------------------------------------------------- Navbat
/* Navbat: ishlar HOLAT bo'yicha guruhlanadi, progress esa har bir NISHON
   uchun bitta segment (dizayn: 12 obyektga → 12 blok). Shu ko'rinishда
   "nechta tugadi / nechta yuklanmoqda / nechta kutmoqda" bir qarashda ayon. */
const JOB_ICON = { deploy: "send", remove: "trash", announce: "megaphone",
                   cache_clear: "trash", sync: "refresh" };
const T_STATE = {
  done: ["done", "tugadi", "#22C55E"], running: ["run", "yuklanmoqda", "#2563EB"],
  queued: ["wait", "kutmoqda", "#CBD5E1"], pending: ["wait", "kutmoqda", "#CBD5E1"],
  error: ["err", "xato", "#EF4444"],
};

function pageQueue() {
  const jobs = S.data.jobs || [];
  if (!jobs.length) {
    return `<div class="card empty">Hali tarqatish bo'lmagan —
      <b>Kutubxona</b> bo'limidan kontent tanlab «Tarqatish» bosing.</div>`;
  }
  // KPI: faol / navbatda / xato / yuborilayotgan hajm
  const running = jobs.filter((j) => j.state === "running");
  const queuedJobs = running.filter((j) =>
    j.targets.every((t) => t.state === "queued" || t.state === "pending"));
  const activeJobs = running.filter((j) => !queuedJobs.includes(j));
  const errJobs = jobs.filter((j) => j.state === "error");
  const doneJobs = jobs.filter((j) => j.state === "done" || j.state === "cancelled");
  const inFlight = running.reduce((a, j) =>
    a + j.targets.reduce((b, t) => b + (t.bytes_total || 0), 0), 0);

  const kpi = (color, label, val) => `<div style="min-width:88px">
    <div class="row" style="gap:6px;margin-bottom:2px">
      <span class="dot" style="background:${color};animation:none"></span>
      <span class="kpi-label" style="font-size:10.5px">${label}</span></div>
    <div style="font-family:Unbounded,sans-serif;font-size:22px;font-weight:600">${val}</div>
  </div>`;

  // Uzun guruh (masalan 50 kioskка ko'p tarqatishдан keyingi «Tugagan»)
  // kartani cheksiz cho'zmasin — 6 tadan ortiq bo'lsa ichida skroll bo'ladi.
  const group = (title, color, list) => list.length ? `
    <div class="row" style="gap:9px;margin:22px 0 10px">
      <span class="dot" style="background:${color};animation:none"></span>
      <div class="strong" style="font-size:14px">${title}</div>
      <span class="dim">${list.length} ta</span>
    </div>
    <div class="card ${list.length > 6 ? "scroll-y" : ""}" style="padding:6px 0"
      >${list.map(jobRow).join("")}</div>` : "";

  return `
  <div class="row wrap" style="gap:16px;align-items:stretch">
    <div class="card" style="flex:1;min-width:300px;display:flex;gap:26px;align-items:center">
      ${kpi("#4F46E5", "FAOL", activeJobs.length)}
      ${kpi("#94A3B8", "NAVBATDA", queuedJobs.length)}
      ${kpi("#EF4444", "XATO", errJobs.length)}
      ${kpi("#0F172A", "YUBORILMOQDA", bytes(inFlight))}
    </div>
    <div class="card" style="flex:1.2;min-width:280px;display:flex;align-items:center;
      gap:12px;background:var(--accent-soft);box-shadow:none;border-color:transparent">
      ${ic("wifi", 18, "#4F46E5")}
      <div class="dim" style="color:#334155;line-height:1.6">Offlayn obyektlar
        navbatda turadi — SIM-internet tiklanishi bilan <b>o'zi</b> davom etadi,
        fayl to'xtagan joyidan (Range) yuklanadi.</div>
    </div>
  </div>

  ${group("Bajarilmoqda", "#2563EB", activeJobs)}
  ${group("Navbatda", "#94A3B8", queuedJobs)}
  ${group("Xato", "#EF4444", errJobs)}
  ${group("Tugagan", "#22C55E", doneJobs)}`;
}

function jobRow(j) {
  const pct = jobPct(j);
  const n = { done: 0, running: 0, wait: 0, err: 0 };
  const segs = j.targets.map((t) => {
    const st = T_STATE[t.state] || T_STATE.pending;
    n[st[0] === "run" ? "running" : st[0] === "wait" ? "wait"
      : st[0] === "err" ? "err" : "done"]++;
    return `<i class="seg ${st[0]}" title="${esc(t.name || t.server_id)} — ${st[1]}"></i>`;
  }).join("");
  const legend = [
    n.done && `<span><i class="dotm" style="background:#22C55E"></i>${n.done} tugadi</span>`,
    n.running && `<span><i class="dotm" style="background:#2563EB"></i>${n.running} yuklanmoqda</span>`,
    n.wait && `<span><i class="dotm" style="background:#CBD5E1"></i>${n.wait} kutmoqda</span>`,
    n.err && `<span><i class="dotm" style="background:#EF4444"></i>${n.err} xato</span>`,
  ].filter(Boolean).join("");

  const kindLabel = j.kind === "remove" ? "O'chirish" : j.kind === "deploy"
    ? (j.items && j.items[0] ? (TYPES[j.items[0].type] || [])[0] || "Kontent" : "Kontent")
    : j.kind;
  const size = (j.items || []).reduce((a, c) => a + (c.media_size || 0), 0);
  const err = (j.targets.find((t) => t.state === "error") || {}).error;

  const isRun = j.state === "running";
  const isErr = j.state === "error";
  const allWait = isRun && n.done === 0 && n.running === 0;

  // O'RTA: faqat FAOL ishда ingichka progress + legenda ko'rinadi. Tugagan/xato
  // ishда katta bar o'rniga bo'sh spacer — qator ixcham qoladi.
  const mid = isRun
    ? `<div class="job-p">
         <div class="segs">${segs || `<i class="seg wait"></i>`}</div>
         <div class="job-legend">${legend}</div>
       </div>`
    : `<div class="job-p"></div>`;

  // O'NG: holat pill + izoh + amal
  let pill, sub, action = "";
  if (isRun) {
    pill = allWait ? `<span class="pill mut">Kutilmoqda</span>`
                   : `<span class="pill acc mono">${pct}%</span>`;
    sub = allWait ? "onlayn kutilmoqda" : etaText(j);
    action = `<button class="btn sm ghost" data-act="job-cancel" data-id="${j.id}">${allWait ? "Bekor" : "To'xtatish"}</button>`;
  } else if (isErr) {
    pill = `<span class="pill err">✕ Xato</span>`;
    sub = err ? esc(err.slice(0, 42)) : "";
    action = `<button class="btn sm ghost" data-act="job-retry" data-id="${j.id}">Qayta</button>`;
  } else if (j.state === "cancelled") {
    pill = `<span class="pill mut">Bekor qilindi</span>`;
    sub = ago(j.done_at || j.created_at);
  } else {
    pill = `<span class="pill ok">✓ Tugadi</span>`;
    sub = ago(j.done_at || j.created_at);
  }

  return `<div class="job">
    <div class="job-ic">${ic(JOB_ICON[j.kind] || "send", 18, "#475569")}</div>
    <div class="job-t">
      <div class="strong">${esc(j.title || j.kind)}${size
        ? ` — ${bytes(size)}` : ""}</div>
      <div class="dim">${esc(kindLabel)} · ${j.n_targets} obyektga</div>
    </div>
    ${mid}
    <div class="job-r">
      ${pill}
      ${sub ? `<div class="dim" style="margin-top:5px">${sub}</div>` : ""}
    </div>
    <div class="job-a">${action}</div>
  </div>`;
}

/** Qolgan vaqtni baholaydi (tezlikni bilmaymiz — nishonlar nisbatidan). */
function etaText(j) {
  const done = j.targets.filter((t) => t.state === "done").length;
  const left = j.targets.length - done;
  if (!left) return "yakunlanmoqda";
  const t0 = new Date(String(j.created_at || "").replace(" ", "T"));
  if (isNaN(t0) || !done) return `${left} obyekt qoldi`;
  const perOne = (Date.now() - t0.getTime()) / done / 60000;   // daqiqa
  const min = Math.max(1, Math.round(perOne * left));
  return min > 90 ? `~${Math.round(min / 60)} soat qoldi` : `~${min} daq qoldi`;
}

// ------------------------------------------------------------- Statistika
function pageStats() {
  const d = S.data.stats;
  if (!d) return "";
  const t = d.totals, max = Math.max(1, ...d.daily.map((x) => x.n));
  const sync = d.sync || {};
  const src = d.by_source || {};
  // Real vaqt: oxirgi 5 daqiqada hodisa bo'lgan qurilmalar "hozir onlayn"
  const liveCount = (d.devices || []).filter((x) => liveWithin(x.last_ts)).length;
  // Diagramma segmentlari (donut) — real ma'lumotdan
  const evSeg = (d.event_mix || []).map((x) => ({ label: clabel(EVENT_LBL, x.k), n: x.n }));
  const adSeg = (d.ads_placement || []).map((x) => ({ label: clabel(AD_PLACE_LBL, x.k), n: x.n }));
  const ctSeg = (d.content_types || []).map((x) => ({ label: (TYPES[x.k] || [])[0] || x.k, n: x.n }));
  const langSeg = (d.langs || []).map((x) => ({ label: LANGS[x.k] || x.k, n: x.n }));
  const srcSeg = [["kiosk", "Kiosk ekrani"], ["web", "Veb (telefon)"]]
    .map(([k, l]) => ({ label: l, n: (src[k] || {}).sessions || 0 }));
  const screenItems = (d.screens || []).map((x) => ({ label: clabel(SCREEN_LBL, x.k), n: x.n }));
  const siteItems = (d.sites || []).map((x) => ({ label: x.k, n: x.n }));
  const hourly = d.hourly || [];
  const hmax = Math.max(...hourly.map((x) => x.n), 1);
  const savg = d.session_avg || { avg_s: 0, n: 0 };
  const kpi = (label, v, note) => `<div class="kpi"><div class="kpi-label">${label}</div>
    <div class="kpi-value">${v}</div><div class="kpi-note">${note}</div></div>`;
  return `
  <div class="filters" style="align-items:center">
    ${[7, 14, 30, 90].map((n) => `<button class="chip ${S.statDays === n ? "on" : ""}"
      data-act="stat-days" data-days="${n}">${n} kun</button>`).join("")}
    <span style="width:10px"></span>
    ${[["", "Kiosk + veb"], ["kiosk", "Faqat kiosk ekrani"], ["web", "Faqat veb"]]
      .map(([k, l]) => `<button class="chip ${S.statSource === k ? "on" : ""}"
        data-act="stat-source" data-source="${k}">${l}</button>`).join("")}
    <span style="width:10px"></span>
    <select class="chip" data-act="stat-server" style="min-width:170px">
      <option value="">Barcha serverlar</option>
      ${(S.data.servers || []).map((s) => `<option value="${s.id}"
        ${S.statServer === s.id ? "selected" : ""}>${esc(s.name)}</option>`).join("")}
    </select>
    <div style="flex:1"></div>
    <button class="btn sm danger" data-act="stats-reset"
      title="Bulutdagi barcha statistikани 0 ga tushiradi">
      ${ic("trash", 14)} Statistikani tozalash</button>
  </div>

  ${sync.pending ? `<div class="card" style="margin-bottom:16px;border-left:4px solid var(--warn)">
      <div class="row wrap">
        <div style="flex:1;min-width:220px">
          <div class="card-title">Statistika hali to'liq ko'chirilmagan</div>
          <div class="card-sub">Serverlarda yuborilmagan <b>${sync.pending}</b> event bor —
            ular avtomatik, partiyalar bilan tortib olinadi (onlayn server bir necha
            daqiqada bo'shatadi).</div>
        </div>
        <div style="text-align:right">
          ${(sync.servers || []).map((s) => `<div class="dim">${esc(s.name)}:
            <b>${s.pending}</b> ${s.online ? "" : "· offlayn"}</div>`).join("")}
        </div>
      </div>
    </div>` : ""}

  <div class="grid k4">
    ${kpi("Sessiyalar", t.sessions, S.statDays + " kun" + srcLabel())}
    ${kpi("Noyob qurilma", t.devices, "kiosk + veb foydalanuvchi")}
    ${kpi("Kontent ochilishi", t.opens, "kino/kitob/musiqa")}
    ${kpi("Reklama", t.ads, "ko'rsatildi")}
  </div>

  <section class="card" style="margin-top:16px">
    <div class="card-head">
      <div><div class="card-title">Kunlik sessiyalar — ${S.statDays} kun</div>
        <div class="card-sub">Jami ${t.events} event bulutda saqlangan${
          max > 1 ? ` · eng ko'p kun: ${max}` : ""}</div></div>
    </div>
    ${d.daily.some((x) => x.n) ? `<div class="chart">${d.daily.map((x) => `
      <div title="${x.date}: ${x.n} sessiya">
        <div class="b ${x.n ? "" : "zero"}"
          style="height:${x.n ? Math.max(6, Math.round(100 * x.n / max)) : 2}%"></div>
        <div class="cn">${x.n || ""}</div>
        <div class="d">${x.date.slice(8)}</div>
      </div>`).join("")}</div>`
      : `<div class="empty">Bu davrda sessiya bo'lmagan</div>`}
  </section>

  <!-- Serverlar sinxroni: har bir server oxirgi aloqasi + yuborilmagan
       (oflaynда yig'ilgan) statistika. 10 kun oflayn → 11-kuni onlayn bo'lganda
       "yuborilmagan" tortib olinadi va 0 ga tushadi. -->
  <section class="card" style="margin-top:16px">
    <div class="card-head"><div>
      <div class="card-title">Serverlar sinxroni</div>
      <div class="card-sub">Har server oxirgi aloqasi va bulutga hali
        yuborilmagan (oflaynда yig'ilган) statistika</div></div></div>
    <div class="tbl-wrap ${(S.data.servers || []).length > 8 ? "scroll-tall" : ""}">
      <table class="tbl">
      <thead><tr><th style="padding-left:14px">Server</th><th>Holat</th>
        <th>Oxirgi aloqa</th><th class="num">Yuborilmagan</th>
        <th class="num col-hide">Jami event</th><th>Sinx</th></tr></thead>
      <tbody>${(S.data.servers || []).length ? (S.data.servers || []).map((s) => `<tr>
        <td style="padding-left:14px" class="strong">${esc(s.name)}
          <div class="dim">${esc(s.route || s.id)}</div></td>
        <td>${s.online ? `<span class="pill ok"><span class="dot live"
            style="width:6px;height:6px"></span> onlayn</span>`
          : `<span class="pill mut">offlayn</span>`}</td>
        <td class="dim">${ago(s.last_seen)}</td>
        <td class="num">${(s.stats_pending || 0) > 0
          ? `<span class="pill warn">${s.stats_pending}</span>`
          : `<span class="dim">0</span>`}</td>
        <td class="num col-hide dim">${s.stats_total || 0}</td>
        <td>${s.synced ? `<span class="pill ok">sinxron</span>`
          : `<span class="pill warn">rev ${s.applied_rev}→${s.desired_rev}</span>`}</td>
      </tr>`).join("") : `<tr><td colspan="6"><div class="empty">Server yo'q</div></td></tr>`}
      </tbody></table></div>
  </section>

  <!-- Boyitilган analitika: donutlar -->
  <div class="grid k3" style="margin-top:16px">
    ${statCard("Faoliyat turlari", donut(evSeg, "harakat"),
      "Yo'lovchilar nima qilgani")}
    ${statCard("Reklama joylashuvi", donut(adSeg, "ko'rildi"),
      "Banner / popup / kino ichida")}
    ${statCard("Kontent turlari", donut(ctSeg, "ochildi"),
      "Kino / multfilm / musiqa / kitob")}
  </div>

  <div class="grid k3" style="margin-top:16px">
    ${statCard("Manba bo'yicha", donut(srcSeg, "sessiya"),
      "Kiosk ekrani va telefon/brauzer")}
    ${statCard("Til bo'yicha", donut(langSeg, "sessiya"))}
    ${statCard("O'rtacha sessiya",
      `<div style="text-align:center;padding:14px 0">
        <div style="font:600 40px Unbounded,sans-serif">${dur(savg.avg_s) || "—"}</div>
        <div class="dim" style="margin-top:6px">${savg.n} tugagan sessiya bo'yicha</div>
        <div class="dim" style="margin-top:2px">o'rtacha ${Math.round(savg.avg_s / 60)} daqiqa</div>
      </div>`)}
  </div>

  <div class="grid k2" style="margin-top:16px">
    ${statCard("Eng ko'p ochilган ekranlar", hbars(screenItems),
      "Qaysi bo'limlar ko'proq ochilgan")}
    ${statCard("Soatlik faollik",
      `<div class="hours">${hourly.map((x) => `<div title="${x.h}:00 — ${x.n}">
        <div class="hb ${x.n ? "" : "q"}" style="height:${
          x.n ? Math.max(4, Math.round(100 * x.n / hmax)) : 2}%"></div>
        <div class="hh">${x.h % 3 === 0 ? x.h : ""}</div></div>`).join("")}</div>`,
      "Kun davomida (0–23 soat)")}
  </div>

  ${siteItems.length ? `<div class="grid k2" style="margin-top:16px">
    ${statCard("QR bilan ochilган saytlar", hbars(siteItems))}
    <div></div></div>` : ""}

  <div class="grid k2" style="margin-top:16px">
    <section class="card">
      <div class="card-head"><div class="card-title">Manba tafsiloti</div></div>
      ${["kiosk", "web"].map((k) => {
        const v = src[k] || { sessions: 0, devices: 0, events: 0 };
        const label = k === "kiosk" ? "Kiosk ekrani (vagonda)" : "Veb (telefon/brauzer)";
        return `<div class="list-row" style="border:0;padding:9px 0">
          ${ic(k === "kiosk" ? "monitor" : "globe", 18, "#475569")}
          <div style="flex:1"><div class="strong">${label}</div>
            <div class="dim">${v.devices} qurilma · ${v.events} event</div></div>
          <div class="strong mono">${v.sessions}</div>
        </div>`;
      }).join("")}
    </section>
    <section class="card">
      <div class="card-head"><div class="card-title">Eng ko'p ko'rilgan</div></div>
      ${d.top_content.length ? d.top_content.map((x) => `<div class="row" style="padding:7px 0">
        <div style="flex:1">${esc(x.title)}</div><div class="strong mono">${x.n}</div></div>`).join("")
        : `<div class="empty">Ma'lumot yo'q</div>`}
    </section>
    <section class="card">
      <div class="card-head"><div class="card-title">Eng ko'p ko'rsatilgan reklamalar</div>
        <span class="dim card-link">jami ${t.ads} ko'rsatildi</span></div>
      ${(d.top_ads || []).length ? d.top_ads.map((x) => `<div class="row" style="padding:7px 0">
        <div style="flex:1">${ic("megaphone", 15, "#B45309")} ${esc(x.title)}</div>
        <div class="strong mono">${x.n}</div></div>`).join("")
        : `<div class="empty">Reklama ko'rsatilmagan</div>`}
    </section>
  </div>

  <div class="grid k2" style="margin-top:16px">
    <section class="card">
      <div class="card-head"><div class="card-title">Serverlar bo'yicha</div></div>
      ${d.top_servers.length ? d.top_servers.map((x) => `<div class="row" style="padding:7px 0">
        <div style="flex:1">${esc(x.name)}</div><div class="strong mono">${x.n}</div></div>`).join("")
        : `<div class="empty">Ma'lumot yo'q</div>`}
    </section>
    <section class="card">
      <div class="card-head"><div class="card-title">Faol qurilmalar</div>
        <span class="dim card-link">${liveCount} hozir onlayn · ${
          (d.devices || []).length} ta</span></div>
      ${(d.devices || []).length ? `<div class="tbl-wrap scroll-y"><table class="tbl">
        <thead><tr><th>Qurilma</th><th>Manba</th><th>Holat</th><th>Sessiya</th>
          <th class="col-hide">Oxirgi</th></tr></thead>
        <tbody>${d.devices.map((x) => {
          const live = liveWithin(x.last_ts);
          return `<tr>
          <td><div class="strong">${esc(x.device_id || "—")}</div>
            <div class="dim">${esc(x.server_name || x.server_id || "")}</div></td>
          <td><span class="pill ${x.source === "web" ? "acc" : "mut"}">${
            x.source === "web" ? "veb" : "kiosk"}</span></td>
          <td>${live ? `<span class="pill ok"><span class="dot live"
            style="width:6px;height:6px"></span> onlayn</span>`
            : `<span class="dim">offlayn</span>`}</td>
          <td class="num strong">${x.sessions}</td>
          <td class="col-hide dim">${ago(x.last_ts)}</td>
        </tr>`; }).join("")}</tbody></table></div>`
        : `<div class="empty">Ma'lumot yo'q</div>`}
    </section>
  </div>`;
}

function srcLabel() {
  return S.statSource === "kiosk" ? " · faqat kiosk"
    : S.statSource === "web" ? " · faqat veb" : "";
}

// ------------------------------------------------------------------ Loglar
function pageLogs() {
  return `<div class="filters">
      ${[["", "Barchasi"], ["INFO", "INFO"], ["WARN", "WARN"], ["ERROR", "ERROR"]]
        .map(([k, l]) => `<button class="chip ${S.logFilter.level === k ? "on" : ""}"
          data-act="log-level" data-level="${k}">${l}</button>`).join("")}
      <select class="chip" data-act="log-server" style="min-width:170px">
        <option value="">Barcha serverlar</option>
        ${(S.data.servers || []).map((s) => `<option value="${s.id}"
          ${S.logFilter.server_id === s.id ? "selected" : ""}>${esc(s.name)}</option>`).join("")}
      </select>
    </div>
    ${logTable(S.data.logs || [], true)}`;
}

function logTable(rows, showServer) {
  return `<div class="card" style="padding:14px 4px"><div class="tbl-wrap${
    rows.length > 14 ? " scroll-tall" : ""}"><table class="tbl">
    <thead><tr><th style="padding-left:14px">Vaqt</th><th>Daraja</th>
      ${showServer ? "<th>Server</th>" : ""}<th>Manba</th><th>Xabar</th></tr></thead>
    <tbody>${rows.length ? rows.map((l) => `<tr>
      <td style="padding-left:14px" class="dim mono">${esc(clock(l.ts))}</td>
      <td><span class="pill ${l.level === "ERROR" ? "err" : l.level === "WARN" ? "warn" : "mut"}">
        ${esc(l.level)}</span></td>
      ${showServer ? `<td class="dim">${esc(l.server_name || l.server_id || "—")}</td>` : ""}
      <td class="dim">${esc(l.source || "—")}</td>
      <td>${esc(l.msg)}</td></tr>`).join("")
      : `<tr><td colspan="5"><div class="empty">Log yo'q</div></td></tr>`}
    </tbody></table></div></div>`;
}

// --------------------------------------------------------------- Reklama
const AD_CHANNELS = [["popup", "Qalqib chiquvchi"], ["banner", "Banner"],
                     ["media", "Kino ichida"]];
/** placement matnini kanallar to'plamiga (moslik: both→popup+banner). */
function adChannels(placement) {
  const s = String(placement || "").trim().toLowerCase();
  if (!s) return new Set(["popup"]);
  if (s === "both") return new Set(["popup", "banner"]);
  const parts = s.split(",").map((x) => x.trim()).filter(Boolean)
    .filter((p) => ["popup", "banner", "media"].includes(p));
  return new Set(parts.length ? parts : ["popup"]);
}
/** Kanallar to'plamини chiroyli yorliq qatoriга. */
function adChannelLabel(placement) {
  const ch = adChannels(placement);
  return AD_CHANNELS.filter(([k]) => ch.has(k)).map(([, v]) => v).join(" + ")
    || "Qalqib chiquvchi";
}

function pageAds() {
  const list = S.data.ads || [];
  if (!list.length) {
    return `<div class="card empty">Reklama yo'q — yuqoridagi
      <b>Yangi reklama</b> tugmasi bilan qo'shing.<br>
      Rasm yoki video yuklanadi, keyin qaysi serverlarga ketishini belgilaysiz.</div>`;
  }
  return `<div class="lib">${list.map((a) => {
    const vid = /\.(mp4|webm|mkv|mov)$/i.test(a.media_name || "");
    return `<article class="lib-card" style="cursor:default">
      <div class="lib-cover">
        ${vid ? `<video src="/api/admin/ads/${a.id}/media" muted loop
                   playsinline style="width:100%;height:100%;object-fit:cover"
                   onmouseover="this.play()" onmouseout="this.pause()"></video>`
              : `<img src="/api/admin/ads/${a.id}/media" alt=""
                   onerror="this.remove()">`}
        ${a.is_active ? "" : `<span class="lib-dur" style="left:8px;right:auto;
          background:rgba(185,28,28,.9)">o'chirilgan</span>`}
        ${vid ? `<span class="lib-dur">video</span>` : ""}
      </div>
      <div class="lib-body">
        <div class="lib-title">${esc(a.title || "(nomsiz)")}</div>
        <div class="dim" style="margin-bottom:7px">${esc(a.subtitle || "")}</div>
        <div class="lib-meta">
          <span class="pill acc">${adChannelLabel(a.placement)}</span>
          ${a.interval_min ? `<span class="dim">har ${a.interval_min} daq</span>` : ""}
          ${a.start_time ? `<span class="dim">${esc(a.start_time)}–${esc(a.end_time || "")}</span>` : ""}
        </div>
        <div style="margin-top:10px">
          ${a.deployed
            ? `<div class="ad-srv">${(a.servers || []).slice(0, 3).map((id) => {
                const s2 = (S.data.servers || []).find((x) => x.id === id) || {};
                return `<span class="pill mut">${esc(s2.name || id)}</span>`;
              }).join("")}${a.deployed > 3
                ? `<span class="pill mut">+${a.deployed - 3}</span>` : ""}</div>`
            : `<div class="pill warn">hech qaysi serverda yo'q</div>`}
        </div>
        <div class="row" style="margin-top:10px">
          <button class="btn sm ghost" data-act="ad-servers" data-id="${a.id}"
            style="flex:1">${ic("server", 13)} Serverlar</button>
          <button class="btn sm ghost" data-act="ad-edit" data-id="${a.id}"
            title="Tahrirlash">${ic("pencil", 13)}</button>
          <button class="btn sm ghost" data-act="ad-del" data-id="${a.id}"
            title="O'chirish">${ic("trash", 13)}</button>
        </div>
      </div>
    </article>`;
  }).join("")}</div>`;
}

// --------------------------------------------------------------- Saytlar
function pageSites() {
  const list = S.data.sites || [];
  return `<div class="card" style="margin-bottom:16px">
      <div class="card-sub">Bu ro'yxat <b>barcha serverlarga bir xil</b> ketadi —
        kiosklardagi «Saytlar» bo'limida QR kod bilan ochiladi.</div>
    </div>
    <div class="card" style="padding:14px 4px"><div class="tbl-wrap"><table class="tbl">
      <thead><tr><th style="padding-left:14px">Nom</th><th>URL</th>
        <th class="col-hide">Tavsif</th><th>Tartib</th><th></th></tr></thead>
      <tbody>${list.length ? list.map((s) => `<tr>
        <td style="padding-left:14px" class="strong">${esc(s.name)}</td>
        <td class="dim">${esc(s.url)}</td>
        <td class="col-hide dim">${esc((s.description || "").slice(0, 60))}</td>
        <td class="num">${s.sort_order}</td>
        <td><div class="row" style="gap:6px">
          <button class="btn sm ghost" data-act="site-edit" data-id="${s.id}">
            ${ic("pencil", 13)}</button>
          <button class="btn sm ghost" data-act="site-del" data-id="${s.id}">
            ${ic("trash", 13)}</button>
        </div></td></tr>`).join("")
        : `<tr><td colspan="5"><div class="empty">Sayt yo'q</div></td></tr>`}
      </tbody></table></div></div>`;
}

// --------------------------------------------------------------- Bekatlar
function pageStops() {
  const list = S.data.stops || [];
  const srv = (S.data.server || {}).server || {};
  const rows = S.stopsDraft !== null ? S.stopsDraft : list;
  // Serverning O'ZIDAGI joriy yo'nalishi (lokal katalogdan) — bulutда bekat
  // yo'q bo'lса ham operator serverdagисини ko'radi va import qiladi.
  const srvRoute = ((S.data.server || {}).local_catalog || {}).route || {};
  const srvStops = [...(srvRoute["0"] || []).map((x) => ({ ...x, direction: 0 })),
                    ...(srvRoute["1"] || []).map((x) => ({ ...x, direction: 1 }))];
  const canImport = !list.length && S.stopsDraft === null && srvStops.length;
  return `<button class="btn sm ghost" data-act="go" data-page="server"
      data-id="${S.serverId}" style="margin-bottom:14px">
      ${ic("chevronLeft", 14)} ${esc(srv.name || "Server")}</button>
    <datalist id="uz-stations">${(S.stations || []).map((st) =>
      `<option value="${esc(st.name)}"></option>`).join("")}</datalist>
    <div class="card" style="margin-bottom:16px">
      <div class="card-sub">Jadvalni to'liq kiritib «Saqlash»ni bosing —
        server yo'nalishni almashtiradi va kiosklarda darhol ko'rinadi.
        <b>Yo'nalish:</b> 0 = borish, 1 = qaytish.
        <br>Bekat nomini ro'yxatдан tanlasangiz — <b>koordinata (xarita) va
        masofa avtomatik to'ladi</b> (${(S.stations || []).length} ta bekat).</div>
    </div>
    ${canImport ? `<div class="card" style="margin-bottom:16px;background:#EFF6FF;
      box-shadow:none"><div class="row wrap" style="gap:12px">
      <div style="flex:1;min-width:240px;line-height:1.6;color:#334155">
        Bulutда bu server uchun bekat yo'q, lekin <b>serverning o'zida
        ${srvStops.length} ta bekat</b> bor (poyezdда kiritilган). Import qilib
        shu yerдан boshqarishни boshlashingiz mumkin.</div>
      <button class="btn sm pri" data-act="stops-import">${ic("download", 14, "#fff")}
        Serverdagi yo'nalishни import qilish</button>
    </div></div>` : ""}
    <div class="card" style="padding:14px 4px">
      <div class="tbl-wrap"><table class="tbl">
        <thead><tr><th style="padding-left:14px">#</th><th>Bekat nomi</th>
          <th>Kelish</th><th>Jo'nash</th><th class="col-hide">Masofa (km)</th>
          <th class="col-hide">Koordinata</th>
          <th>Yo'nalish</th><th></th></tr></thead>
        <tbody>${rows.map((s, i) => `<tr>
          <td style="padding-left:14px" class="dim">${i + 1}</td>
          <td><input data-stop="${i}.name" list="uz-stations" value="${esc(s.name || "")}"
            style="border:1px solid var(--border);border-radius:8px;padding:7px 9px;width:100%"></td>
          <td><input data-stop="${i}.arrival_time" value="${esc(s.arrival_time || "")}"
            placeholder="08:30" style="border:1px solid var(--border);border-radius:8px;padding:7px 9px;width:78px"></td>
          <td><input data-stop="${i}.departure_time" value="${esc(s.departure_time || "")}"
            placeholder="08:35" style="border:1px solid var(--border);border-radius:8px;padding:7px 9px;width:78px"></td>
          <td class="col-hide"><input data-stop="${i}.distance_km" value="${esc(s.distance_km ?? "")}"
            style="border:1px solid var(--border);border-radius:8px;padding:7px 9px;width:70px"></td>
          <td class="col-hide dim" data-coord="${i}" style="white-space:nowrap">${
            s.latitude != null && s.longitude != null
              ? `📍 ${(+s.latitude).toFixed(3)}, ${(+s.longitude).toFixed(3)}`
              : `<span style="color:var(--warn-dark)">koordinata yo'q</span>`}</td>
          <td><input data-stop="${i}.direction" value="${esc(s.direction ?? 0)}"
            style="border:1px solid var(--border);border-radius:8px;padding:7px 9px;width:48px"></td>
          <td><button class="btn sm ghost" data-act="stop-del" data-i="${i}">
            ${ic("x", 13)}</button></td>
        </tr>`).join("") || `<tr><td colspan="8"><div class="empty">
          Bekat yo'q — «Qator qo'shish» bilan boshlang</div></td></tr>`}
        </tbody></table></div>
      <div class="row" style="margin-top:14px">
        <button class="btn sm ghost" data-act="stop-add">${ic("plus", 14)} Qator qo'shish</button>
        <div style="flex:1"></div>
        ${S.stopsDraft !== null ? `<button class="btn sm ghost" data-act="stops-reset">
          Bekor qilish</button>` : ""}
        <button class="btn sm pri" data-act="stops-save"
          ${S.stopsDraft === null ? "disabled" : ""}>
          ${ic("save", 14, "#fff")} Saqlash va yuborish</button>
      </div>
    </div>`;
}

// -------------------------------------------------------- Ulash kalitlari
function pageTokens() {
  const list = S.data.tokens || [];
  const host = location.host;
  return `<div class="card" style="margin-bottom:16px">
      <div class="card-title">Poyezd serverini ulash — eng oddiy yo'l</div>
      <div class="card-sub" style="margin:8px 0 12px">Token KERAK EMAS. Poyezd
        serveriga faqat bulut domenini yozasiz, u o'zi ulanadi va shu yerda
        «Tasdiqlash» tugmasi bilan ishga kirishadi.</div>
      <ol class="dim" style="line-height:1.9;margin:0;padding-left:20px">
        <li>Poyezd serverida admin oynasi → <b>Sozlamalar → Markaziy bulut</b> →
            domenni yozing: <code>${esc(host)}</code> → <b>Saqlash</b>.
            <br>(Yoki <code>server/cloud.txt</code> ichiga:
            <code>url=${esc(host)}</code>)</li>
        <li>Serverni qayta ishga tushiring.</li>
        <li>Shu panelning <b>Boshqaruv</b> yoki <b>Serverlar</b> bo'limida
            «Yangi server ulanmoqchi» bloki chiqadi → <b>Tasdiqlash</b>.</li>
      </ol>
      <div class="dim" style="margin-top:12px;line-height:1.7">
        Tasdiqlanmagan serverga kontent, sozlama va e'lon <b>yuborilmaydi</b> —
        domenni bilgan begona qurilma hech narsa olmaydi.
        <br>Domen ishlatgani uchun bulutni keyinchalik boshqa serverga
        ko'chirsangiz, poyezdlarda hech narsa o'zgartirmaysiz (DNS'ni
        yangi IP'ga qaratasiz, <code>cloud_signing_key.pem</code> va
        <code>cloud.db</code>+<code>storage/</code> ni ko'chirasiz).
      </div>
    </div>

    <div class="card" style="margin-bottom:16px">
      <div class="card-title">Ulash kalitlari (ixtiyoriy)</div>
      <div class="card-sub" style="margin-top:6px">Ko'p serverni bir yo'la
        o'rnatayotgan bo'lsangiz — kalit bilan kelgan server <b>darhol
        tasdiqlangan</b> bo'ladi, qo'lда bosish kerak emas. Serverga:
        <code>KIOSK_CLOUD_ENROLL=&lt;token&gt;</code></div>
    </div>
    <div class="card" style="padding:14px 4px"><div class="tbl-wrap"><table class="tbl">
      <thead><tr><th style="padding-left:14px">Nom</th><th>Yo'nalish</th>
        <th>Yaratilgan</th><th>Holat</th><th></th></tr></thead>
      <tbody>${list.length ? list.map((t) => `<tr>
        <td style="padding-left:14px" class="strong">${esc(t.label)}</td>
        <td class="dim">${esc(t.route || "—")}</td>
        <td class="dim">${esc(String(t.created_at || "").slice(0, 16))}</td>
        <td>${t.used_at ? `<span class="pill ok">ishlatilgan · ${esc(t.server_id)}</span>`
                        : `<span class="pill warn">kutilmoqda</span>`}</td>
        <td>${t.used_at ? "" : `<button class="btn sm ghost" data-act="token-del"
              data-id="${t.id}">${ic("trash", 13)}</button>`}</td></tr>`).join("")
        : `<tr><td colspan="5"><div class="empty">Kalit yo'q</div></td></tr>`}
      </tbody></table></div></div>`;
}

// =========================================================== 7) Modallar
function modalView() {
  const m = S.modal;
  const inner = m.kind === "upload" ? mUpload()
    : m.kind === "deploy" ? mDeploy()
    : m.kind === "remove" ? mRemove()
    : m.kind === "announce" ? mAnnounce()
    : m.kind === "token" ? mToken()
    : m.kind === "ad" ? mAd()
    : m.kind === "site" ? mSite()
    : m.kind === "rename" ? mRename()
    : m.kind === "klabel" ? mKioskLabel()
    : "";
  const cls = m.kind === "upload" ? "xwide" : m.kind === "deploy" ? "wide" : "";
  return `<div class="overlay" data-act="modal-bg"><div class="modal ${cls}">${
    inner}</div></div>`;
}

function head(title, sub) {
  return `<div class="modal-head"><div><div class="modal-title">${title}</div>
    ${sub ? `<div class="modal-sub">${sub}</div>` : ""}</div>
    <button class="x" data-act="modal-close">${ic("x", 16)}</button></div>`;
}

const F = (k, dflt) => (S.form[k] !== undefined ? S.form[k] : dflt);

function mUpload() {
  const t = F("type", "movie");
  const [titleLbl, authorLbl, coverLbl] = UT[t] || UT.movie;
  const isBook = t === "book";
  const hasText = t === "book" || t === "audiobook";
  const cv = S.up.cover, md = S.up.media, tx = S.up.text;
  const edit = S.modal.id || null;          // tahrirlash rejimi (mavjud kontent)
  const onServers = edit ? (S.modal.deployed || 0) : 0;

  // Pastdagi izoh — dizayndagi uch holat (tahrirlashda sinxronizatsiya izohi)
  const note = !S.flags.visible
    ? "«Kiosklarda ko'rsatilsin» o'chirilgan — tarqatilsa ham kioskda ko'rinmaydi"
    : edit && onServers
      ? `${onServers} serverda bor — saqlansa ular avtomatik yangilanadi`
      : cv ? "Muqova kiosk kartochkasi va tafsilot ekranida ishlatiladi"
           : "Muqova tanlanmagan — kioskda bo'sh kartochka bo'lib ko'rinadi";

  return `${edit
    ? head("Kontentni tahrirlash",
        "O'zgarishlar shu kontent bor serverlarga avtomatik yetkaziladi "
        + "(fayl almashtirilsa qaytadan yuklab olinadi).")
    : head("Kontent yuklash",
        "Har bir kontent — media fayl + muqova + ma'lumotlari. Avval bulut kutubxonasiga tushadi.")}
  <input type="file" multiple class="u-hide" data-act="file-input">

  <div class="up-grid">
    <div class="up-form">
      <div class="field full"><label>Turi</label>
        <div class="tchips">${Object.entries(TYPES).map(([k, v]) =>
          `<button class="tchip ${t === k ? "on" : ""}" data-act="utype"
             data-type="${k}">${v[0]}</button>`).join("")}</div></div>

      <div class="field full"><label>Tili</label>
        <select data-bind="lang">
          <option value="">Barcha tillarda</option>
          ${Object.entries(LANGS).map(([k, v]) => `<option value="${k}"
            ${F("lang", "uz") === k ? "selected" : ""}>${v}</option>`).join("")}
        </select>
        <div class="hint">yoki «Barcha tillarda» — til ahamiyatsiz</div></div>

      <div class="field full"><label>${titleLbl}</label>
        <input data-bind="title" value="${esc(F("title", ""))}"
          placeholder="masalan: ${t === "music" ? "Yurak"
            : hasText ? "O'tkan kunlar" : "Ilon vodiysi"}"></div>

      <div class="field full"><label>${authorLbl}</label>
        <input data-bind="author" value="${esc(F("author", ""))}"
          placeholder="${authorLbl} ismini yozing"></div>

      <div class="field"><label>Janr</label>
        <input data-bind="genre" list="dl-genre" value="${esc(F("genre", ""))}"
          placeholder="Drama">
        <datalist id="dl-genre">${GENRES.map((g) => `<option>${g}</option>`).join("")}</datalist></div>

      ${isBook ? `<div class="field"><label>Sahifa soni</label>
          <input data-bind="pages" value="${esc(F("pages", ""))}" placeholder="320"></div>`
        : `<div class="field"><label>Tab (kategoriya)</label>
          <input data-bind="category_tab" list="dl-tab"
            value="${esc(F("category_tab", ""))}" placeholder="Kinolar">
          <datalist id="dl-tab">${TABS.map((x) => `<option>${x}</option>`).join("")}</datalist></div>`}

      ${isBook ? `<div class="field"><label>Tab (kategoriya)</label>
          <input data-bind="category_tab" list="dl-tab"
            value="${esc(F("category_tab", ""))}" placeholder="Kitoblar">
          <datalist id="dl-tab">${TABS.map((x) => `<option>${x}</option>`).join("")}</datalist></div>`
        : `<div class="field"><label>Davomiylik</label>
          <input data-bind="duration" value="${esc(F("duration", ""))}"
            placeholder="1:42:00 yoki soniya"></div>`}

      <div class="field full"><label>Tavsif</label>
        <textarea data-bind="description"
          placeholder="Kiosk kartochkasi va tafsilot ekranida ko'rinadi…"
          >${esc(F("description", ""))}</textarea></div>
    </div>

    <div>
      <label class="up-label" style="display:block;margin-bottom:6px">${coverLbl}</label>
      <div class="cover-box ${cv ? "on" : ""}" data-act="pick-cover">
        ${cv ? `<button class="x cover-x" data-act="up-del" data-slot="cover"
                  title="Muqovani olib tashlash">${ic("x", 13)}</button>` : ""}
        ${cv && cv.preview ? `<img src="${cv.preview}" alt="">`
          : cv && cv.state === "have" && edit
            ? `<img src="/api/admin/cover/${edit}?v=${cv.sha256.slice(0, 8)}"
                 alt="" onerror="this.remove()">`
            : ic("image", 26, cv ? "#2563EB" : "#94A3B8", 1.7)}
        <div class="cover-state">${cv ? esc(cv.name) : "Muqova yo'q"}</div>
        <div class="cover-hint">${cv
          ? (cv.state === "up" ? cv.pct + "% yuklanmoqda…" : bytes(cv.size))
          : "bosing yoki tashlang"}</div>
      </div>
      <div class="cover-note">jpg · png · webp. Muqovasiz kontent kioskda
        «Muqova yo'q» kartochka bo'lib chiqadi.</div>
    </div>
  </div>

  <div class="up-file" data-slot="media">
    <div class="up-file-top">
      ${ic(isBook ? "headphones" : (TYPES[t] || [])[3] || "clapperboard", 19, "#475569")}
      <div style="flex:1;min-width:0">
        <div class="up-label">${isBook ? "Audio fayl (ixtiyoriy)" : "Media fayl"}</div>
        <div class="up-name">${md ? esc(md.name) : "Tanlanmagan — bosing yoki tashlang"}</div>
      </div>
      ${md ? `<div class="up-state">${
          md.state === "have" ? bytes(md.size)
          : md.state === "done" ? "Tayyor · " + bytes(md.size)
          : md.state === "err" ? "Xato"
          : md.pct + "% · " + bytes(md.loaded || 0) + " / " + bytes(md.total || 0)}</div>
        <button class="btn sm ghost" data-act="pick-media">Almashtirish</button>
        <button class="btn sm ghost" data-act="up-del" data-slot="media"
          title="Olib tashlash">${ic("x", 13)}</button>`
        : `<button class="btn sm ghost" data-act="pick-media">Tanlash</button>`}
    </div>
    ${md && md.state !== "have" ? `<div class="bar ${md.state === "done" ? "ok"
        : md.state === "err" ? "err" : "flow"}"
        style="margin-top:10px"><i style="width:${md.pct}%"></i></div>` : ""}
    ${md ? `<div class="up-meta">
        <span>${esc((md.name.split(".").pop() || "").toUpperCase())}</span>
        <span>${bytes(md.size || md.total)}</span>
        ${md.state === "done" ? "<span>sha256 ✓</span>" : ""}
        ${md.state === "have" ? "<span>o'zgarmagan</span>" : ""}
        ${md.dedup ? "<span>omborda bor edi — qayta yuklanmadi</span>" : ""}
      </div>` : ""}
  </div>

  ${hasText ? `<div class="up-file plain" data-slot="text">
    <div class="up-file-top">
      ${ic("fileText", 18, "#94A3B8")}
      <div style="flex:1;min-width:0">
        <div class="up-label">Kitob matni</div>
        <div class="up-name">${tx ? esc(tx.name) : "Tanlanmagan — .json yoki .txt"}</div>
      </div>
      ${tx ? `<div class="up-state">${tx.state === "have" ? bytes(tx.size)
        : tx.state === "done" ? "Tayyor · " + bytes(tx.size) : tx.pct + "%"}</div>
        <button class="btn sm ghost" data-act="pick-text">Almashtirish</button>
        <button class="btn sm ghost" data-act="up-del" data-slot="text"
          title="Olib tashlash">${ic("x", 13)}</button>`
        : `<button class="btn sm ghost" data-act="pick-text">Tanlash</button>`}
    </div>
  </div>` : ""}

  <div class="flags">
    ${[["visible", "Kiosklarda ko'rsatilsin",
        "Belgi olib tashlansa server bu kontentni kioskka umuman bermaydi"],
       ["rec", "Tavsiya blokida ko'rsatilsin",
        "Bosh sahifadagi «Tavsiya etamiz» qatorida chiqadi"],
       ["cache", "Kiosklarga yuklab qo'yilsin (lokal kesh)",
        "Belgilanmasa — faqat serverdan striming, oflaynda ochilmaydi"]]
      .map(([k, title, sub]) => `<div class="flag" data-act="flag" data-key="${k}">
        <span class="tgl ${S.flags[k] ? "on" : ""}"><i></i></span>
        <div><div class="flag-title">${title}</div>
          <div class="flag-sub">${sub}</div></div>
      </div>`).join("")}
  </div>

  <div class="drop-thin" data-act="drop">
    ${ic("plus", 15, "#94A3B8", 2.4)}
    <b>Fayllarni shu oynaga tortib tashlang</b>
    <span>turi kengaytmadan aniqlanadi — media, rasm yoki matn</span>
  </div>

  <div class="modal-foot">
    <div class="foot-note">${note}</div>
    ${edit ? `
      <button class="btn ghost" data-act="modal-close">Bekor qilish</button>
      <button class="btn pri" data-act="save-edit">Saqlash</button>`
    : `
      <button class="btn" data-act="save-content" data-then="stay">Kutubxonaga saqlash</button>
      <button class="btn pri" data-act="save-content" data-then="deploy">Saqlash va tarqatish</button>`}
  </div>`;
}

function mDeploy() {
  const servers = S.data.servers || [];
  const items = (S.data.library || []).filter((c) => S.sel.has(c.id));
  const picked = servers.filter((s) => !S.pickOff[s.id]);
  const total = items.reduce((a, c) => a + (c.media_size || 0) + (c.cover_size || 0)
                                        + (c.text_size || 0), 0);
  const sub = S.dstep === 1 ? "1-qadam: nimani yuborish"
    : S.dstep === 2 ? "2-qadam: qaysi serverlarga" : "3-qadam: tasdiqlash";
  return `${head("Kontentni tarqatish", sub)}
  <div class="steps">${[[1, "Kontent"], [2, "Manzil"], [3, "Tasdiq"]].map(([n, l]) =>
    `<div class="step ${S.dstep >= n ? "on" : ""}"><div class="step-n">${n}</div>
      <div class="step-l">${l}</div></div>`).join("")}</div>

  ${S.dstep === 1 ? (items.length ? items.map((c) => `<div class="list-row">
      ${ic((TYPES[c.type] || [])[3] || "clapperboard", 19, (TYPES[c.type] || [])[1])}
      <div style="flex:1;min-width:0"><div class="strong">${esc(c.title)}</div>
        <div class="dim">${bytes(c.media_size || c.text_size)} ${c.duration ? "· " + dur(c.duration) : ""}</div></div>
      ${typePill(c.type)}</div>`).join("")
    : `<div class="empty">Kontent tanlanmagan</div>`) : ""}

  ${S.dstep === 2 ? `<div class="row" style="margin-bottom:10px">
      <div class="dim" style="flex:1">${picked.length} ta server tanlandi</div>
      <button class="btn sm ghost" data-act="pick-all">Barchasini belgilash</button>
      <button class="btn sm ghost" data-act="pick-none">Tozalash</button>
    </div>
    ${servers.map((s) => `<div class="pickrow ${!S.pickOff[s.id] ? "on" : ""}"
        data-act="pick" data-id="${s.id}">
      <div class="box">${!S.pickOff[s.id] ? ic("check", 12, "#fff", 3.2) : ""}</div>
      <div style="flex:1;min-width:0"><div class="strong">${esc(s.name)}</div>
        <div class="dim">${esc(s.route || "—")} · ${s.kiosks_total} kiosk</div></div>
      <span class="pill ${s.online ? "ok" : "mut"}">${s.online ? "Onlayn" : "Offlayn"}</span>
    </div>`).join("")}` : ""}

  ${S.dstep === 3 ? `<div class="grid k4" style="margin-bottom:16px">
      ${[["Kontent", items.length + " fayl"], ["Hajm", bytes(total)],
         ["Serverlar", picked.length + " ta"],
         ["Kiosklar", picked.reduce((a, s) => a + s.kiosks_total, 0) + " ta"]]
        .map(([l, v]) => `<div class="kpi"><div class="kpi-label">${l}</div>
          <div class="kpi-value" style="font-size:19px">${v}</div></div>`).join("")}
    </div>
    <div class="list-row"><div style="flex:1">
      <div class="strong">sha256 mos kelsa qayta yubormaslik</div>
      <div class="dim">Serverda allaqachon bor fayl SIM-trafikni behuda sarflamaydi</div></div>
      <button class="tgl ${S.opts.skip_existing ? "on" : ""}" data-act="opt"
        data-key="skip_existing"><i></i></button>
    </div>
    ${schedPicker("deploy", "Tunda yuborish — SIM-trafik arzon va yo'lovchi yo'q")}
    ${schedValue("deploy") ? `<div class="dim" style="margin-top:10px">
      Kontent belgilangan vaqtgacha serverlarga <b>yuborilmaydi</b> — reja
      vaqti kelganда tayinlanadi va yuklab olish boshlanadi.</div>` : ""}
    ${picked.some((s) => !s.online) ? `<div class="dim" style="margin-top:14px">
      Tanlanganlardan ${picked.filter((s) => !s.online).length} tasi hozir offlayn.
      Ular navbatga qo'shiladi va onlayn bo'lishi bilan avtomatik yuklab oladi —
      qayta bosish shart emas.</div>` : ""}` : ""}

  <div class="modal-foot">
    <button class="btn ghost" data-act="modal-close">Bekor qilish</button>
    ${S.dstep > 1 ? `<button class="btn ghost" data-act="dstep" data-n="${S.dstep - 1}">
      ${ic("chevronLeft", 14)} Orqaga</button>` : ""}
    ${S.dstep < 3
      ? `<button class="btn pri" data-act="dstep" data-n="${S.dstep + 1}"
           ${S.dstep === 1 && !items.length ? "disabled" : ""}>Davom etish →</button>`
      : `<button class="btn pri" data-act="deploy-go" ${!picked.length ? "disabled" : ""}>
           ${schedValue("deploy") ? "Rejaga qo'yish" : "Tarqatishni boshlash"}</button>`}
  </div>`;
}

function mRemove() {
  const items = (S.data.library || []).filter((c) => S.sel.has(c.id));
  return `${head("Kiosklardan o'chirish",
    "Fayl bulut kutubxonasida qoladi, faqat serverlardan olib tashlanadi")}
  ${items.map((c) => `<div class="list-row"><div style="flex:1">${esc(c.title)}</div>
    <span class="dim">${c.deployed} serverda</span></div>`).join("")}
  <div class="dim" style="margin-top:14px">
    Serverlar keyingi manifestда bu fayllarni o'chiradi (offlayn bo'lsa —
    ulanganda). Kiosklardagi lokal kesh ham tozalanadi.</div>
  <div class="modal-foot">
    <button class="btn ghost" data-act="modal-close">Bekor qilish</button>
    <button class="btn danger" data-act="remove-go">O'chirishni boshlash</button>
  </div>`;
}

function mAnnounce() {
  const at = schedValue("announce");
  return `${head("E'lon yuborish", "Matn shu serverning barcha kiosklarida ko'rinadi")}
  <div class="field"><label>Matn</label>
    <textarea data-bind="text" placeholder="Masalan: Buxoro bekatiga 20 daqiqa"
      >${esc(F("text", ""))}</textarea></div>
  ${schedPicker("announce", "Masalan bekatga yetishdan 20 daqiqa oldin")}
  <div class="modal-foot">
    <button class="btn ghost" data-act="modal-close">Bekor qilish</button>
    <button class="btn pri" data-act="announce-go">${at
      ? "Rejaga qo'yish" : "Hozir yuborish"}</button>
  </div>`;
}

function mToken() {
  if (S.modal.token) {
    return `${head("Kalit yaratildi", "Bu token FAQAT SHU MARTA ko'rsatiladi — ko'chirib oling")}
    <div class="field"><label>Enrollment token</label>
      <input value="${esc(S.modal.token)}" readonly id="tok"></div>
    <div class="field"><label>Poyezd serverida sozlash</label>
      <textarea readonly rows="3">KIOSK_CLOUD_URL=${esc(location.origin)}
KIOSK_CLOUD_ENROLL=${esc(S.modal.token)}</textarea></div>
    <div class="modal-foot">
      <button class="btn" data-act="copy-token">${ic("copy", 15)} Ko'chirish</button>
      <button class="btn pri" data-act="modal-close">Tayyor</button>
    </div>`;
  }
  return `${head("Yangi ulash kaliti", "Bir martalik token — bitta poyezd serveri uchun")}
  <div class="field"><label>Server nomi</label>
    <input data-bind="label" value="${esc(F("label", ""))}" placeholder="Poyezd 076Ф"></div>
  <div class="field"><label>Yo'nalish (ixtiyoriy)</label>
    <input data-bind="route" value="${esc(F("route", ""))}" placeholder="Toshkent → Xiva"></div>
  <div class="modal-foot">
    <button class="btn ghost" data-act="modal-close">Bekor qilish</button>
    <button class="btn pri" data-act="token-go">Yaratish</button>
  </div>`;
}

/** Reklama rasmi o'lchamini tavsiya bilan solishtiradi (16:9 eng chiroyli). */
function adAspectHint(w, h) {
  if (!w || !h) return "";
  const ar = w / h;
  const near = (a, b) => Math.abs(a - b) / b < 0.06;   // ~6% dopusk
  if (near(ar, 16 / 9)) return `<span class="pill ok">${w}×${h} · 16:9 ✓</span>`;
  const ratio = ar > 1 ? (Math.round(ar * 10) / 10) + ":1" : "1:" + (Math.round((1 / ar) * 10) / 10);
  return `<span class="pill warn">${w}×${h} · ${ar > 1.2 ? "keng" : ar < 0.9 ? "tik" : "kvadratга yaqin"} `
    + `— 16:9 emas, chetlari kesilishi mumkin</span>`;
}

function mAd() {
  const edit = S.modal.id;
  const md = S.up.media;
  const vid = md && /\.(mp4|webm|mkv|mov)$/i.test(md.name || "");
  const placement = F("placement", "popup");
  return `${head(edit ? "Reklamani tahrirlash" : "Yangi reklama",
    "Rasm yoki video + ko'rsatish shartlari. Keyin qaysi serverlarga "
    + "ketishini belgilaysiz.")}
  <input type="file" multiple class="u-hide" data-act="file-input">
  <div class="up-grid">
    <div class="up-form">
      <div class="field full"><label>Sarlavha</label>
        <input data-bind="title" value="${esc(F("title", ""))}"
          placeholder="Reklama sarlavhasi"></div>
      <div class="field full"><label>Qo'shimcha matn</label>
        <input data-bind="subtitle" value="${esc(F("subtitle", ""))}"></div>
      <div class="field full"><label>Havola (QR uchun, ixtiyoriy)</label>
        <input data-bind="link_url" value="${esc(F("link_url", ""))}"
          placeholder="https://..."></div>
      <div class="field full"><label>Joylashuv (bir nechtasini tanlash mumkin)</label>
        <div class="tchips">${AD_CHANNELS.map(([k, v]) => {
          const on = adChannels(F("placement", "popup")).has(k);
          return `<button type="button" class="tchip ${on ? "on" : ""}"
            data-act="ad-chan" data-chan="${k}">${v}</button>`;
        }).join("")}</div>
        <div class="hint">Bitta reklama bir vaqtda popup, banner va kino ichида
          chiqishi mumkin. Banner faqat rasm.</div></div>
      <div class="field"><label>Ko'rsatish (soniya)</label>
        <input data-bind="duration" value="${esc(F("duration", "10"))}"
          placeholder="10 · video uchun 0 = oxirigacha"></div>
      <div class="field"><label>Har necha daqiqada</label>
        <input data-bind="interval_min" value="${esc(F("interval_min", ""))}"
          placeholder="bo'sh = umumiy sozlama"></div>
      <div class="field"><label>Vaqt oralig'i</label>
        <div class="row" style="gap:8px">
          <input data-bind="start_time" value="${esc(F("start_time", ""))}"
            placeholder="09:00" style="width:50%">
          <input data-bind="end_time" value="${esc(F("end_time", ""))}"
            placeholder="21:00" style="width:50%"></div></div>
      <div class="field full">
        <div class="row" style="gap:10px">
          <button class="tgl ${F("is_active", true) ? "on" : ""}" data-act="ad-active"
            type="button"><i></i></button>
          <span style="font-size:12.5px;font-weight:700">Faol (kiosklarda ko'rsatiladi)</span>
        </div></div>
    </div>
    <div>
      <label class="up-label" style="display:block;margin-bottom:6px">Reklama fayli</label>
      <div class="cover-box ${md ? "on" : ""}" data-act="pick-media">
        ${md && md.preview && !vid ? `<img src="${md.preview}" alt="">`
          : md && md.state === "have" && edit
            ? `<img src="/api/admin/ads/${edit}/media" alt="" onerror="this.remove()">`
            : ic(vid ? "clapperboard" : "image", 26, md ? "#2563EB" : "#94A3B8", 1.7)}
        <div class="cover-state">${md ? esc(md.name) : "Fayl tanlanmagan"}</div>
        <div class="cover-hint">${md
          ? (md.state === "up" ? md.pct + "% yuklanmoqda…" : bytes(md.size))
          : "bosing yoki tashlang"}</div>
      </div>
      ${md && md.w && !vid
        ? `<div style="margin-top:8px;text-align:center">${adAspectHint(md.w, md.h)}</div>`
        : ""}
      <div class="cover-note">
        <b>Tavsiya etilgan o'lcham</b> — chiroyli chiqishi uchun:<br>
        • Qalqib chiquvchi / kino ichi: <b>16:9</b> — <b>1920×1080</b> yoki
          1280×720. Kioskда to'liq ekранда kesilmasдan ko'rinadi.
        ${adChannels(placement).has("banner")
          ? `<br>• Banner: keng landshaft rasm (~16:9), muhim qismini markazда
             tuting, chetга matn qo'ymang. Banner faqat rasm (video emas).`
          : ""}
        <br>Format: jpg · png · mp4 · webm. Video ovozsiz, to'liq o'ynatiladi.
      </div>
    </div>
  </div>

  ${adServerPicker()}

  <div class="modal-foot">
    <div class="foot-note">${(S.adPick || new Set()).size
      ? `Saqlashda ${(S.adPick).size} serverga yuboriladi`
      : "Hech qanday server tanlanmagan — reklama faqat kutubxonada qoladi"}</div>
    <button class="btn ghost" data-act="modal-close">Bekor qilish</button>
    <button class="btn pri" data-act="ad-save">${edit ? "Saqlash"
      : "Saqlash va tarqatish"}</button>
  </div>`;
}

/** Reklama formasining ichidagi server tanlash bloki.
 *  Avval bu alohida ikonka ortida edi va ko'rinmasdi — endi formaning o'zida. */
function adServerPicker() {
  const servers = S.data.servers || [];
  const pick = S.adPick || new Set();
  if (!servers.length) {
    return `<div class="card" style="margin-top:16px;background:var(--warn-bg);
      box-shadow:none"><div class="dim" style="color:var(--warn-dark)">
      Hali birorta server ulanmagan — reklama kutubxonada saqlanadi va server
      qo'shilgach tarqatasiz.</div></div>`;
  }
  return `<div class="flags" style="margin-top:16px">
    <div class="row" style="margin-bottom:12px">
      <div style="flex:1">
        <div class="strong" style="font-size:13px">Qaysi serverlarda ko'rinadi</div>
        <div class="dim">Belgilanganlarga yuboriladi, belgisi olinganlardan
          o'chiriladi</div>
      </div>
      <span class="pill acc">${pick.size} / ${servers.length}</span>
      <button class="btn sm ghost" data-act="adpick-all" type="button">Barchasi</button>
      <button class="btn sm ghost" data-act="adpick-none" type="button">Tozalash</button>
    </div>
    <div class="kgrid" style="grid-template-columns:repeat(auto-fill,minmax(220px,1fr))">
      ${servers.map((s) => `<div class="pickrow ${pick.has(s.id) ? "on" : ""}"
          data-act="adpick" data-id="${s.id}" style="margin:0">
        <div class="box">${pick.has(s.id) ? ic("check", 12, "#fff", 3.2) : ""}</div>
        <div style="flex:1;min-width:0">
          <div class="strong" style="font-size:12.5px">${esc(s.name)}</div>
          <div class="dim">${esc(s.route || "—")}</div>
        </div>
        <span class="dot ${s.online ? "live" : "off"}" style="animation:none"></span>
      </div>`).join("")}
    </div>
  </div>`;
}

function mSite() {
  return `${head(S.modal.id ? "Saytni tahrirlash" : "Yangi sayt",
    "Barcha serverlarga bir xil ketadi")}
  <div class="field"><label>Nom</label>
    <input data-bind="name" value="${esc(F("name", ""))}" placeholder="Poyezd.uz"></div>
  <div class="field"><label>URL</label>
    <input data-bind="url" value="${esc(F("url", ""))}" placeholder="https://..."></div>
  <div class="field"><label>Tavsif</label>
    <textarea data-bind="description">${esc(F("description", ""))}</textarea></div>
  <div class="f2">
    <div class="field"><label>Imkoniyatlar (matn)</label>
      <input data-bind="features" value="${esc(F("features", ""))}"></div>
    <div class="field"><label>Tartib raqami</label>
      <input data-bind="sort_order" value="${esc(F("sort_order", "0"))}"></div>
  </div>
  <div class="modal-foot">
    <button class="btn ghost" data-act="modal-close">Bekor qilish</button>
    <button class="btn pri" data-act="site-save">Saqlash</button>
  </div>`;
}

function mRename() {
  return `${head("Serverga nom berish",
    "Bu nom butun panelда ko'rinadi. Server hostnameни (masalan «GPUPC») "
    + "endi ustiga yozmaydi.")}
  <div class="field"><label>Nom</label>
    <input data-bind="name" value="${esc(F("name", ""))}"
      placeholder="Poyezd 076Ф — 3-vagon"></div>
  <div class="field"><label>Yo'nalish</label>
    <input data-bind="route" value="${esc(F("route", ""))}"
      placeholder="Toshkent → Xiva"></div>
  <div class="field"><label>Izoh (ixtiyoriy)</label>
    <textarea data-bind="note">${esc(F("note", ""))}</textarea></div>
  <div class="modal-foot">
    <button class="btn ghost" data-act="modal-close">Bekor qilish</button>
    <button class="btn pri" data-act="rename-save">Saqlash</button>
  </div>`;
}

function mKioskLabel() {
  return `${head("Kioskка nom berish",
    `Qurilma: ${esc(S.modal.dev)} — nom faqat shu panelда ko'rinadi`)}
  <div class="field"><label>Nom</label>
    <input data-bind="label" value="${esc(F("label", ""))}"
      placeholder="1-vagon, o'ng tomon"></div>
  <div class="modal-foot">
    <button class="btn ghost" data-act="modal-close">Bekor qilish</button>
    <button class="btn pri" data-act="klabel-save">Saqlash</button>
  </div>`;
}

// ========================================================= 8) Hodisalar
function openModal(kind, extra) {
  S.modal = { kind, ...(extra || {}) };
  if (kind === "upload") {
    S.up = { media: null, cover: null, text: null };
    S.pickKind = "";
    S.flags = { visible: true, rec: true, cache: true };
    S.form = { type: "movie", lang: "uz" };
  }
  if (kind === "deploy") { S.dstep = 1; S.pickOff = {}; }
  if (kind === "announce" || kind === "token") S.form = {};
  render();
}
function closeModal() {
  Object.values(S.up).forEach((u) => u && u.preview && URL.revokeObjectURL(u.preview));
  S.modal = null;
  S.form = {};
  render();
}

/** Mavjud kontentni tahrirlash — xuddi shu forma, lekin to'ldirilgan holda.
 *  Fayl slotlari `state:"have"` bilan boshlanadi: saqlashda ular YUBORILMAYDI
 *  (ya'ni tegilmaydi), faqat almashtirilgan yoki olib tashlangani ketadi. */
function openEdit(c) {
  S.modal = { kind: "upload", id: c.id, deployed: c.deployed || 0 };
  S.form = {
    type: c.type, title: c.title || "", author: c.author || "",
    genre: c.genre || "", description: c.description || "",
    category_tab: c.category_tab || "", lang: c.lang || "",
    duration: c.duration ? dur(c.duration) : "",
    pages: c.pages || "",
  };
  S.flags = {
    visible: c.visible !== 0,
    rec: c.is_recommended === 1,
    cache: c.cache_enabled !== 0,
  };
  const have = (sha, name, size) => (sha
    ? { name: name || "fayl", size: size || 0, sha256: sha, state: "have", pct: 100 }
    : null);
  S.up = {
    media: have(c.media_sha, c.media_name, c.media_size),
    cover: have(c.cover_sha, c.cover_name, c.cover_size),
    text: have(c.text_sha, c.text_name, c.text_size),
  };
  S.pickKind = "";
  render();
}

document.addEventListener("click", async (e) => {
  const el = e.target.closest("[data-act]");
  if (!el) return;
  const act = el.dataset.act;

  // ---- navigatsiya
  if (act === "go") { e.preventDefault(); go(el.dataset.page, el.dataset.id); return; }
  if (act === "burger") { document.body.classList.toggle("nav-open"); return; }
  if (act === "logout") { await api.post("/api/admin/logout"); S.auth = false; S.data = {}; render(); return; }
  if (act === "modal-bg" && e.target === el) { closeModal(); return; }
  if (act === "modal-close") { closeModal(); return; }

  // ---- filtrlar
  if (act === "lib-type") { S.libType = el.dataset.type; load(); return; }
  if (act === "stat-days") { S.statDays = +el.dataset.days; load(); return; }
  if (act === "stat-source") { S.statSource = el.dataset.source; load(); return; }
  if (act === "stats-reset") {
    if (!confirm("Bulutdagi BARCHA statistika 0 ga tushirilsinmi?\n\n"
      + "Serverlardagi lokal statistika tegilmaydi, lekin bulut panelida "
      + "hisoblar 0 dan boshlanadi (0 dan test qilish uchun).")) return;
    try {
      const r = await api.post("/api/admin/stats/reset");
      toast(`Statistika tozalandi — ${r.deleted} event o'chirildi`, "ok");
      load();
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "log-level") { S.logFilter.level = el.dataset.level; load(); return; }

  // ---- kutubxona tanlash
  if (act === "sel") {
    const id = +el.dataset.id;
    S.sel.has(id) ? S.sel.delete(id) : S.sel.add(id);
    render(); return;
  }
  if (act === "sel-clear") { S.sel.clear(); render(); return; }
  if (act === "sel-all") {
    // Joriy ro'yxat (filtr/qidiruv bo'yicha) — hammasi tanlangan bo'lsa olib
    // tashlaydi, aks holda hammasini tanlaydi (toggle).
    const list = S.data.library || [];
    const allOn = list.length > 0 && list.every((c) => S.sel.has(c.id));
    if (allOn) list.forEach((c) => S.sel.delete(c.id));
    else list.forEach((c) => S.sel.add(c.id));
    render(); return;
  }
  if (act === "update-push") {
    const u = S.data.update || {};
    if (!confirm(`v${u.version} yangilanishini barcha tasdiqlangan qurilmalarga yuborilsinmi?`)) return;
    try {
      const r = await api.post("/api/admin/update/push", {});
      toast(`Yangilanish ${r.sent} qurilmaga yuborildi`);
    } catch (err) { toast("Xato: " + err.message, "err"); }
    return;
  }

  // ---- serverlar
  if (act === "sync-all") {
    try { const r = await api.post("/api/admin/sync-all");
      toast(`${r.sent} serverga manifest yuborildi`, "ok"); load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "cmd") {
    try {
      await api.post(`/api/admin/servers/${S.serverId}/command`, { kind: el.dataset.kind });
      toast("Buyruq yuborildi", "ok"); load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "srv-del") {
    if (!confirm("Server ro'yxatdan o'chirilsinmi? Poyezddagi kontent joyida qoladi.")) return;
    try { await api.del("/api/admin/servers/" + S.serverId); go("servers"); }
    catch (err) { toast(err.message, "err"); }
    return;
  }
  // ---- server sozlamalari (masofadan)
  if (act === "srv-bool") {
    S.srvForm[el.dataset.key] = el.dataset.val;
    render(); return;
  }
  if (act === "srv-reset") {
    const g = el.dataset.group;
    if (g) dirtyKeys(g).forEach((k) => delete S.srvForm[k]);
    else S.srvForm = {};
    if (S.schedule.group === g) S.schedule = { on: false, date: "", time: "", group: "" };
    render(); return;
  }
  if (act === "algo-toggle") {
    // BITTA tanlov (radio) — kiosk baribir faqat bittasini ishlatadi. Avval
    // multi-select edi va "qaysi biri tanlangan" tushunarsiz bo'lardi.
    S.srvForm.ad_algorithm = el.dataset.key || "weighted";
    render(); return;
  }
  if (act === "copy-hw") {
    const i = document.getElementById("hwid");
    i.select(); navigator.clipboard?.writeText(i.value);
    toast("Qurilma ID ko'chirildi", "ok"); return;
  }
  if (act === "lic-send") {
    const text = (S.form.lictext || "").trim();
    if (!text) { toast("license.key mazmunini qo'ying", "err"); return; }
    try {
      const r = await api.post(`/api/admin/servers/${S.serverId}/license`,
                               { text, apply_at: schedValue("lic2") });
      toast(r.apply_at ? `Rejaga qo'yildi: ${r.apply_at.slice(0, 16)}`
            : r.queued ? "Navbatga qo'yildi — server ulanganda o'rnatiladi"
                       : "Yuborildi — server imzoni tekshiradi", "ok");
      S.form.lictext = "";
      setTimeout(() => load(true), 2500);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "lic-block") {
    const want = el.dataset.val === "1";
    if (want && !confirm("Bu serverning BARCHA kiosklari bloklanadimi?\n\n"
        + "Ekranlarda qulf chiqadi va yo'lovchilar hech narsa ko'rmaydi.")) return;
    try {
      const r = await api.post(`/api/admin/servers/${S.serverId}/license`,
                               { blocked: want, apply_at: schedValue("lic2") });
      toast(r.apply_at ? `Rejaga qo'yildi: ${r.apply_at.slice(0, 16)}`
            : r.queued ? "Navbatga qo'yildi"
                       : (want ? "Bloklandi" : "Blok ochildi"), "ok");
      setTimeout(() => load(true), 1500);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "sched-toggle") {
    const g = el.dataset.group || "main";
    S.schedule.on = !(S.schedule.on && S.schedule.group === g);
    S.schedule.group = g;
    if (S.schedule.on && !S.schedule.date) {
      // Standart: ertaga tunda 03:00 (SIM-trafik arzon va yo'lovchi yo'q payt)
      const t = new Date(Date.now() + 864e5);
      S.schedule.date = t.toISOString().slice(0, 10);
      S.schedule.time = "03:00";
    }
    render(); return;
  }
  if (act === "op-cancel") {
    try { await api.del("/api/admin/ops/" + el.dataset.id); load(true); }
    catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "srv-save") {
    const g = el.dataset.group || "main";
    const keys = dirtyKeys(g);
    if (!keys.length) return;
    const values = {};
    keys.forEach((k) => { values[k] = S.srvForm[k]; });
    const body = { values };
    if (S.schedule.on && S.schedule.group === g) {
      if (!S.schedule.date) { toast("Sanani tanlang", "err"); return; }
      body.apply_at = `${S.schedule.date} ${S.schedule.time || "00:00"}`;
    }
    try {
      const r = await api.post(`/api/admin/servers/${S.serverId}/settings`, body);
      toast(r.apply_at
        ? `Rejaga qo'yildi: ${r.apply_at.slice(0, 16)} (${r.sent.length} sozlama)`
        : r.queued
          ? `Navbatga qo'yildi — server ulanganda qo'llanadi (${r.sent.length} sozlama)`
          : `Yuborildi: ${r.sent.length} sozlama`, "ok");
      S.srvForm = {};
      S.schedule = { on: false, date: "", time: "" };
      setTimeout(() => load(true), 1200);   // server qo'llagach qaytib o'qiymiz
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  // ---- veb ilova
  if (act === "web-cmd") {
    const at = schedValue("web");
    try {
      const r = await api.post(`/api/admin/servers/${S.serverId}/web`,
                               { action: el.dataset.kind, apply_at: at });
      toast(r.apply_at ? `Rejaga qo'yildi: ${r.apply_at.slice(0, 16)}`
            : el.dataset.kind === "start" ? "Veb yoqilmoqda…" : "Veb o'chirilmoqda…", "ok");
      if (at) S.schedule = { on: false, date: "", time: "", group: "" };
      setTimeout(() => load(true), 2500);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "maint-cmd") {
    const at = schedValue("maint");
    const onv = el.dataset.on;
    try {
      const r = await api.post(`/api/admin/servers/${S.serverId}/settings`,
        { values: { maintenance: onv }, apply_at: at });
      toast(r.apply_at ? `Rejaga qo'yildi: ${r.apply_at.slice(0, 16)}`
        : onv === "1" ? "Texnik rejim yoqildi — kiosklar qulflanadi"
        : "Texnik rejim o'chirildi — kiosklar ochildi", "ok");
      if (at) S.schedule = { on: false, date: "", time: "", group: "" };
      setTimeout(() => load(true), 1500);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  // ---- kiosk buyruqlari
  if (act === "kiosk-cmd" || act === "kiosk-forget") {
    const dev = el.dataset.dev;
    const kind = act === "kiosk-forget" ? "forget" : el.dataset.kind;
    if (kind === "forget" && !confirm(
        `${dev} ro'yxatdan olib tashlansinmi?\n\nKiosk qayta ulanganda yana `
        + "paydo bo'ladi — bu faqat ro'yxatni tozalash.")) return;
    if (kind === "cache_clear" && !confirm(
        `${dev} dagi lokal kesh tozalansinmi?\n\nMedia qaytadan yuklab olinadi.`))
      return;
    try {
      await api.post(`/api/admin/servers/${S.serverId}/kiosk`,
                     { device_id: dev, action: kind });
      toast("Buyruq yuborildi: " + kind, "ok");
      setTimeout(() => load(true), 1500);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  // ---- serverni tasdiqlash / rad etish
  if (act === "srv-approve") {
    const vert = el.dataset.vertical || "train";
    try {
      await api.post(`/api/admin/servers/${el.dataset.id}/approve`, { vertical: vert });
      toast(`Tasdiqlandi (${vert === "bus" ? "Avtobus" : "Poyezd"}) — endi kontent tarqatish mumkin`, "ok");
      load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "srv-vertical") {
    const vert = el.dataset.vertical || "train";
    try {
      await api.patch(`/api/admin/servers/${el.dataset.id}`, { vertical: vert });
      toast(`Qurilma turi: ${vert === "bus" ? "Avtobus" : "Poyezd"}`, "ok");
      load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "srv-reject") {
    if (!confirm("Bu server rad etilsinmi? Ro'yxatdan o'chiriladi.\n\n"
                 + "Agar u haqiqatan sizning serveringiz bo'lsa, qayta ulanганда "
                 + "yana ro'yxatda paydo bo'ladi.")) return;
    try {
      await api.del("/api/admin/servers/" + el.dataset.id);
      toast("Rad etildi", "ok");
      load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "srv-remove-content") {
    try {
      await api.post("/api/admin/remove",
        { content_ids: [+el.dataset.id], server_ids: [S.serverId] });
      toast("O'chirish buyrug'i yuborildi", "ok"); load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }

  // ---- kontent
  if (act === "content-edit") {
    e.stopPropagation();
    const c = (S.data.library || []).find((x) => x.id === +el.dataset.id);
    if (c) openEdit(c);
    return;
  }
  if (act === "save-edit") { await saveEdit(); return; }
  if (act === "content-del") {
    e.stopPropagation();
    if (!confirm("Kutubxonadan butunlay o'chirilsinmi? Barcha serverlardan ham olib tashlanadi.")) return;
    try { const r = await api.del("/api/admin/content/" + el.dataset.id);
      S.sel.delete(+el.dataset.id);
      toast(r.servers ? `O'chirildi · ${r.servers} serverga buyruq ketdi` : "O'chirildi", "ok");
      load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }

  // ---- modallar
  if (act === "upload-open") { openModal("upload"); return; }
  if (act === "deploy-open") { openModal("deploy"); return; }
  if (act === "remove-open") { openModal("remove"); return; }
  if (act === "announce-open") { openModal("announce"); return; }
  if (act === "token-open") { openModal("token"); return; }

  // ---- kontent yuklash modali
  if (act === "utype") { S.form.type = el.dataset.type; render(); return; }
  if (act === "flag") {
    S.flags[el.dataset.key] = !S.flags[el.dataset.key];
    render(); return;
  }
  if (act === "hero-save") {
    const u = S.up.hero;
    if (!u || u.state !== "done") { toast("Rasm yuklanishini kuting", "err"); return; }
    try {
      await api.put(`/api/admin/servers/${S.serverId}/branding`,
                    { kind: "hero", media: { sha256: u.sha256, name: u.name } });
      toast("Banner kutubxonaga qo'shildi va shu serverga qo'yildi", "ok");
      if (u.preview) URL.revokeObjectURL(u.preview);
      S.up.hero = null;
      setTimeout(() => load(true), 1500);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "hero-pick") {
    try {
      await api.put(`/api/admin/servers/${S.serverId}/branding`,
                    { kind: "hero", library_id: +el.dataset.id });
      toast("Banner almashtirildi — serverga yetkaziladi", "ok");
      setTimeout(() => load(true), 1200);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "hero-del") {
    e.stopPropagation();
    if (!confirm("Bu banner kutubxonadan o'chirilsinmi? Uni ishlatayotgan "
                 + "serverlar standart rasmga qaytadi.")) return;
    try {
      const r = await api.del("/api/admin/branding/library/" + el.dataset.id);
      toast(r.servers ? `O'chirildi · ${r.servers} server standartga qaytdi`
                      : "O'chirildi", "ok");
      load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "hero-clear") {
    // Standart rasmga qaytish — buzg'unchi emas (yuklangan rasmlar
    // kutubxonada qoladi), shuning uchun tasdiq so'ramaymiz: bosish = tanlash
    // (custom rasmni tanlash kabi darhol).
    try {
      await api.put(`/api/admin/servers/${S.serverId}/branding`,
                    { kind: "hero", media: null });
      toast("Standart rasm tanlandi", "ok");
      setTimeout(() => load(true), 900);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "drop" || act === "pick-cover" || act === "pick-media"
      || act === "pick-text" || act === "pick-hero") {
    // Qaysi slotga tushishi: tugmadan aniq, "drop"da esa kengaytmadan
    S.pickKind = act === "drop" ? "" : act.replace("pick-", "");
    const inp = document.querySelector('[data-act="file-input"]');
    if (inp) {
      inp.accept = (S.pickKind === "cover" || S.pickKind === "hero") ? "image/*"
        : S.pickKind === "text" ? ".json,.txt,.epub" : "";
      inp.click();
    }
    return;
  }
  if (act === "file-input") return;                 // input bosilishi — o'tkazamiz
  if (act === "up-del") {
    const slot = el.dataset.slot;
    if (S.up[slot] && S.up[slot].preview) URL.revokeObjectURL(S.up[slot].preview);
    S.up[slot] = null;
    render(); return;
  }
  if (act === "opt") { S.opts[el.dataset.key] = !S.opts[el.dataset.key]; render(); return; }
  if (act === "dstep") { S.dstep = +el.dataset.n; render(); return; }
  if (act === "pick") {
    const id = el.dataset.id;
    S.pickOff[id] = !S.pickOff[id];
    render(); return;
  }
  if (act === "pick-all") { S.pickOff = {}; render(); return; }
  if (act === "pick-none") {
    (S.data.servers || []).forEach((s) => { S.pickOff[s.id] = true; });
    render(); return;
  }

  // ---- reklama
  if (act === "ad-new") {
    openModal("ad");
    S.up = { media: null, cover: null, text: null, hero: null };
    S.form = { duration: "10", placement: "popup", is_active: true };
    // Reklama odatda BARCHA poyezdlarga ketadi — standart holatда hammasi
    // belgilangan bo'ladi, kerak bo'lsa olib tashlanadi.
    S.adPick = new Set((S.data.servers || []).map((x) => x.id));
    render(); return;
  }
  if (act === "ad-edit") {
    const a = (S.data.ads || []).find((x) => x.id === +el.dataset.id);
    if (!a) return;
    S.modal = { kind: "ad", id: a.id };
    S.form = { title: a.title || "", subtitle: a.subtitle || "",
               link_url: a.link_url || "", placement: a.placement || "popup",
               duration: String(a.duration ?? 10),
               interval_min: a.interval_min ? String(a.interval_min) : "",
               start_time: a.start_time || "", end_time: a.end_time || "",
               is_active: a.is_active === 1 };
    S.up = { media: a.media_sha ? { name: a.media_name || "fayl",
      size: a.media_size, sha256: a.media_sha, state: "have", pct: 100 } : null,
      cover: null, text: null, hero: null };
    S.adPick = new Set(a.servers || []);
    render(); return;
  }
  if (act === "ad-active") { S.form.is_active = !F("is_active", true); render(); return; }
  if (act === "ad-chan") {
    // Joylashuv kanalини almashtirish (multi-select). Kamida bittasi qolsin.
    const ch = adChannels(F("placement", "popup"));
    const k = el.dataset.chan;
    if (ch.has(k)) ch.delete(k); else ch.add(k);
    if (!ch.size) ch.add("popup");
    S.form.placement = ["popup", "banner", "media"].filter((x) => ch.has(x)).join(",");
    render(); return;
  }
  if (act === "adpick") {
    const id = el.dataset.id;
    S.adPick = S.adPick || new Set();
    S.adPick.has(id) ? S.adPick.delete(id) : S.adPick.add(id);
    render(); return;
  }
  if (act === "adpick-all") {
    S.adPick = new Set((S.data.servers || []).map((x) => x.id)); render(); return;
  }
  if (act === "adpick-none") { S.adPick = new Set(); render(); return; }
  if (act === "ad-save") { await saveAd(); return; }
  if (act === "ad-del") {
    if (!confirm("Reklama o'chirilsinmi? Barcha serverlardan ham olib tashlanadi.")) return;
    try { const r = await api.del("/api/admin/ads/" + el.dataset.id);
      toast(r.servers ? `O'chirildi · ${r.servers} server yangilanadi` : "O'chirildi", "ok");
      load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "ad-servers") {
    // Alohida modal emas — reklamaning o'z formasini ochamiz (server tanlash
    // shu yerда, forma ichida). Bitta joyda bo'lgani chalkashlikni yo'qotadi.
    const a = (S.data.ads || []).find((x) => x.id === +el.dataset.id);
    if (!a) return;
    S.modal = { kind: "ad", id: a.id, focusServers: true };
    S.form = { title: a.title || "", subtitle: a.subtitle || "",
               link_url: a.link_url || "", placement: a.placement || "popup",
               duration: String(a.duration ?? 10),
               interval_min: a.interval_min ? String(a.interval_min) : "",
               start_time: a.start_time || "", end_time: a.end_time || "",
               is_active: a.is_active === 1 };
    S.up = { media: a.media_sha ? { name: a.media_name || "fayl",
      size: a.media_size, sha256: a.media_sha, state: "have", pct: 100 } : null,
      cover: null, text: null, hero: null };
    S.adPick = new Set(a.servers || []);
    render(); return;
  }
  // ---- saytlar
  if (act === "site-new") { openModal("site"); S.form = { sort_order: "0" }; render(); return; }
  if (act === "site-edit") {
    const s2 = (S.data.sites || []).find((x) => x.id === +el.dataset.id);
    if (!s2) return;
    S.modal = { kind: "site", id: s2.id };
    S.form = { name: s2.name || "", url: s2.url || "",
               description: s2.description || "", features: s2.features || "",
               sort_order: String(s2.sort_order ?? 0) };
    render(); return;
  }
  if (act === "site-save") {
    const body = { name: (F("name", "") || "").trim(), url: (F("url", "") || "").trim(),
      description: F("description", ""), features: F("features", ""),
      sort_order: parseInt(F("sort_order", "0"), 10) || 0 };
    if (!body.name || !body.url) { toast("Nom va URL kerak", "err"); return; }
    try {
      if (S.modal.id) await api.patch("/api/admin/sites/" + S.modal.id, body);
      else await api.post("/api/admin/sites", body);
      toast("Saqlandi — barcha serverlarga yuborildi", "ok");
      closeModal(); load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "site-del") {
    if (!confirm("Sayt o'chirilsinmi? Barcha kiosklardan ketadi.")) return;
    try { await api.del("/api/admin/sites/" + el.dataset.id); load(true); }
    catch (err) { toast(err.message, "err"); }
    return;
  }
  // ---- bekatlar
  if (act === "stops-open") { go("stops", S.serverId || el.dataset.id); return; }
  if (act === "stop-add") {
    S.stopsDraft = [...(S.stopsDraft || S.data.stops || []),
                    { name: "", arrival_time: "", departure_time: "",
                      distance_km: "", direction: 0 }];
    render(); return;
  }
  if (act === "stop-del") {
    const rows = [...(S.stopsDraft || S.data.stops || [])];
    rows.splice(+el.dataset.i, 1);
    S.stopsDraft = rows; render(); return;
  }
  if (act === "stops-reset") { S.stopsDraft = null; render(); return; }
  if (act === "stops-import") {
    // Serverning o'zidagi joriy yo'nalishни tahrirlash nusxasiga olamiz
    const route = ((S.data.server || {}).local_catalog || {}).route || {};
    S.stopsDraft = [
      ...(route["0"] || []).map((x) => ({ ...x, direction: 0 })),
      ...(route["1"] || []).map((x) => ({ ...x, direction: 1 })),
    ];
    toast(`${S.stopsDraft.length} bekat import qilindi — «Saqlash»ni bosing`, "ok");
    render(); return;
  }
  if (act === "stops-save") {
    const rows = (S.stopsDraft || []).filter((r) => (r.name || "").trim());
    try {
      const r = await api.put(`/api/admin/servers/${S.serverId}/stops`,
                              { stops: rows });
      toast(`${r.n} bekat saqlandi va yuborildi`, "ok");
      S.stopsDraft = null; load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  // ---- nom berish
  if (act === "rename-open") {
    const s2 = ((S.data.server || {}).server) || {};
    S.modal = { kind: "rename" };
    S.form = { name: s2.name || "", route: s2.route || "", note: s2.note || "" };
    render(); return;
  }
  if (act === "rename-save") {
    const name = (F("name", "") || "").trim();
    if (!name) { toast("Nom kerak", "err"); return; }
    try {
      await api.patch("/api/admin/servers/" + S.serverId,
                      { name, route: F("route", ""), note: F("note", "") });
      toast("Nom saqlandi", "ok"); closeModal(); load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "klabel-open") {
    S.modal = { kind: "klabel", dev: el.dataset.dev };
    S.form = { label: el.dataset.label || "" };
    render(); return;
  }
  if (act === "klabel-save") {
    try {
      await api.patch(`/api/admin/servers/${S.serverId}/kiosk-label`,
                      { device_id: S.modal.dev, label: F("label", "") });
      toast("Kiosk nomi saqlandi", "ok"); closeModal(); load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "save-content") { await saveContent(el.dataset.then); return; }
  if (act === "deploy-go") { await deployGo(); return; }
  if (act === "remove-go") {
    try {
      const r = await api.post("/api/admin/remove", { content_ids: [...S.sel] });
      toast(`${r.servers} serverdan o'chirilmoqda`, "ok");
      S.sel.clear(); closeModal(); load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "announce-go") {
    const text = (S.form.text || "").trim();
    if (!text) { toast("Matn kiriting", "err"); return; }
    const at = schedValue("announce");
    try {
      const r = await api.post(`/api/admin/servers/${S.serverId}/command`,
                               { kind: "announce", text, apply_at: at });
      toast(r.apply_at ? `Rejaga qo'yildi: ${r.apply_at.slice(0, 16)}`
            : r.queued ? "Navbatga qo'yildi — server ulanganda ko'rinadi"
                       : "E'lon yuborildi", "ok");
      S.schedule = { on: false, date: "", time: "", group: "" };
      closeModal(); load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "token-go") {
    const label = (S.form.label || "").trim();
    if (!label) { toast("Server nomini kiriting", "err"); return; }
    try {
      const r = await api.post("/api/admin/enroll-tokens",
        { label, route: (S.form.route || "").trim() });
      S.modal = { kind: "token", token: r.token };
      render(); load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "copy-token") {
    const i = document.getElementById("tok");
    i.select(); navigator.clipboard?.writeText(i.value);
    toast("Ko'chirildi", "ok"); return;
  }
  if (act === "token-del") {
    try { await api.del("/api/admin/enroll-tokens/" + el.dataset.id); load(true); }
    catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "job-retry") {
    try {
      const r = await api.post(`/api/admin/jobs/${el.dataset.id}/retry`);
      toast(`Qayta urinilmoqda — ${r.servers} obyekt`, "ok");
      load(true);
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  if (act === "job-cancel") {
    try { await api.post(`/api/admin/jobs/${el.dataset.id}/cancel`); load(true); }
    catch (err) { toast(err.message, "err"); }
    return;
  }
});

// forma qiymatlari (render'да yo'qolmasin — S.form da turadi)
document.addEventListener("input", (e) => {
  const b = e.target.dataset.bind;
  if (b) { S.form[b] = e.target.value; return; }
  // Bekatlar jadvali: data-stop="<index>.<maydon>"
  const st = e.target.dataset.stop;
  if (st) {
    const [i, field] = st.split(".");
    const idx = +i;
    const rows = [...(S.stopsDraft || S.data.stops || [])];
    rows[idx] = { ...(rows[idx] || {}), [field]: e.target.value };
    // Nom ro'yxatдagi bekatga to'g'ri kelsa — koordinata avtomatik to'ladi,
    // masofa (km) shu yo'nalishдagi 1-bekatдан haversine bilan hisoblanadi.
    if (field === "name") {
      const stn = stationByName(e.target.value);
      if (stn) {
        rows[idx].latitude = stn.lat;
        rows[idx].longitude = stn.lng;
        const dir = rows[idx].direction ?? 0;
        const first = rows.find((r) => (r.direction ?? 0) == dir
          && r.latitude != null);
        const km = first ? haversineKm(
          { lat: +first.latitude, lng: +first.longitude },
          { lat: stn.lat, lng: stn.lng }) : 0;
        if (km != null) rows[idx].distance_km = km;
        // DOM'ni to'g'ridan-to'g'ri yangilaymiz (butun jadval qayta chizilmasin)
        const cc = document.querySelector(`[data-coord="${idx}"]`);
        if (cc) cc.textContent = `📍 ${stn.lat.toFixed(3)}, ${stn.lng.toFixed(3)}`;
        const dk = document.querySelector(`[data-stop="${idx}.distance_km"]`);
        if (dk && km != null) dk.value = km;
      }
    }
    S.stopsDraft = rows;
    const btn = document.querySelector('[data-act="stops-save"]');
    if (btn) btn.disabled = false;
    return;
  }
  const sv = e.target.dataset.srv;
  if (sv) {
    S.srvForm[sv] = e.target.value;
    // Butun sahifani qayta chizmaymiz (fokus yo'qolmasin) — faqat
    // "N maydon o'zgardi" hisoblagichi va tugmalar yangilanishi kerak,
    // ular keyingi render'da o'zi to'g'rilanadi.
    const btn = document.querySelector('[data-act="srv-save"]');
    if (btn) btn.disabled = false;
    const rb = document.querySelector('[data-act="srv-reset"]');
    if (rb) rb.disabled = false;
    return;
  }
  if (e.target.dataset.act === "q") {
    S.q = e.target.value;
    clearTimeout(S._qt);
    S._qt = setTimeout(() => load(true), 350);
  }
});
document.addEventListener("change", (e) => {
  if (e.target.dataset.act === "log-server") { S.logFilter.server_id = e.target.value; load(); }
  if (e.target.dataset.act === "stat-server") { S.statServer = e.target.value; load(); }
  if (e.target.dataset.act === "file-input") pickFiles([...e.target.files]);
  if (e.target.dataset.act === "update-file") {
    const file = e.target.files[0];
    if (!file) return;
    const ver = (document.getElementById("upd-ver")?.value || "").trim();
    const prog = document.getElementById("upd-prog");
    if (!ver) { if (prog) prog.textContent = "Avval versiya raqamini kiriting (masalan 1.0.1)."; return; }
    putUpdate(file, ver, (p) => { if (prog) prog.textContent = `Yuklanmoqda… ${p}%`; })
      .then(() => { if (prog) prog.textContent = "✓ Yuklandi."; load(true); })
      .catch((err) => { if (prog) prog.textContent = "Xato: " + err.message; });
  }
  const sc = e.target.dataset.sched;
  if (sc) { S.schedule[sc] = e.target.value; }
});
document.addEventListener("submit", async (e) => {
  if (e.target.dataset.act !== "login") return;
  e.preventDefault();
  const f = new FormData(e.target);
  const username = String(f.get("username") || "").trim();
  S.loginUser = username;                       // xato bo'lsa qayta yozmasin
  try {
    const r = await api.post("/api/admin/login", {
      username, password: f.get("password"), remember: !!f.get("remember") });
    S.auth = true; S.err = ""; S.user = { username: r.username, role: r.role };
    load();
  } catch (err) { S.err = err.message; render(); }
});
// Fayl tashlash: butun modal ustiga tashlasa ham ishlaydi (dizaynda "shu
// OYNAGA tortib tashlang" deyilgan), muqova ramkasi esa aniq slotga tushadi.
["dragover", "dragleave", "drop"].forEach((ev) =>
  document.addEventListener(ev, (e) => {
    if (!S.modal || S.modal.kind !== "upload") return;
    const zone = e.target.closest(".cover-box, .drop-thin, .modal");
    if (!zone) return;
    e.preventDefault();
    const hot = e.target.closest(".cover-box") || e.target.closest(".drop-thin");
    document.querySelectorAll(".cover-box, .drop-thin")
      .forEach((n) => n.classList.remove("hot"));
    if (ev === "dragover" && hot) hot.classList.add("hot");
    if (ev === "drop") {
      S.pickKind = e.target.closest(".cover-box") ? "cover" : "";
      pickFiles([...(e.dataTransfer?.files || [])]);
    }
  }));

// ========================================================== 9) Yuklashlar
const EXT_KIND = (name) => {
  const e = (name.split(".").pop() || "").toLowerCase();
  if (["jpg", "jpeg", "png", "webp", "gif"].includes(e)) return "cover";
  if (["json", "txt", "epub"].includes(e)) return "text";
  return "media";
};

async function pickFiles(files) {
  for (const f of files) {
    // Slot: tugma orqali majburiy berilgan bo'lsa shu, aks holda kengaytmadan
    const slot = S.pickKind || EXT_KIND(f.name);
    // hero — modal ichida emas, server tafsiloti sahifasida turadi
    const old = S.up[slot];
    if (old && old.preview) URL.revokeObjectURL(old.preview);
    const u = {
      name: f.name, pct: 0, loaded: 0, total: f.size, size: f.size, state: "up",
      // Har qanday rasm uchun preview (reklama media rasmini ham ko'rsatadi)
      preview: f.type.startsWith("image/") ? URL.createObjectURL(f) : null,
    };
    S.up[slot] = u;
    // Rasm o'lchamini o'lchaymiz — reklama/muqova uchun tavsiya bilan solishtirish
    if (u.preview) {
      const im = new Image();
      im.onload = () => { u.w = im.naturalWidth; u.h = im.naturalHeight; render(); };
      im.src = u.preview;
    }
    // Sarlavha bo'sh bo'lsa media fayl nomidan taklif qilamiz
    if (!S.form.title && slot === "media") {
      S.form.title = f.name.replace(/\.[^.]+$/, "").replace(/[-_.]+/g, " ").trim();
    }
    render();
    try {
      const r = await putBlob(f, (pct, loaded) => {
        u.pct = pct; u.loaded = loaded;
        // Butun modalni qayta chizmaymiz (forma fokusini yo'qotmaslik uchun) —
        // faqat shu slotning progressi va yozuvini yangilaymiz.
        const box = document.querySelector(`[data-slot="${slot}"]`)
          || (slot === "cover" ? document.querySelector(".cover-box") : null);
        if (!box) return;
        const bar = box.querySelector(".bar > i");
        if (bar) bar.style.width = pct + "%";
        const st = box.querySelector(".up-state") || box.querySelector(".cover-hint");
        if (st) {
          st.textContent = slot === "cover" ? pct + "% yuklanmoqda…"
            : `${pct}% · ${bytes(loaded)} / ${bytes(u.total)}`;
        }
      });
      u.state = "done"; u.pct = 100; u.sha256 = r.sha256;
      u.dedup = r.dedup === true;
      u.size = r.size;
    } catch (err) {
      u.state = "err";
      toast(f.name + ": " + err.message, "err");
    }
    render();
  }
  S.pickKind = "";
}

function partOf(slot) {
  const u = S.up[slot];
  return u && u.state === "done" ? { sha256: u.sha256, name: u.name } : undefined;
}

async function saveContent(then) {
  const type = F("type", "movie");
  const body = {
    type,
    title: (F("title", "") || "").trim(),
    author: F("author", ""), genre: F("genre", ""),
    description: F("description", ""), category_tab: F("category_tab", ""),
    lang: F("lang", "uz"),
    duration: parseDur(F("duration", "")),
    pages: parseInt(F("pages", "0"), 10) || 0,
    is_recommended: !!S.flags.rec,
    cache_enabled: !!S.flags.cache,
    visible: !!S.flags.visible,
    media: partOf("media"), cover: partOf("cover"), text: partOf("text"),
  };
  if (!body.title) { toast("Sarlavha kerak", "err"); return; }
  if (!body.media && !body.text) {
    toast("Media yoki matn fayli kerak", "err"); return;
  }
  if (Object.values(S.up).some((u) => u && u.state === "up")) {
    toast("Yuklash tugashini kuting", "err"); return;
  }
  try {
    const r = await api.post("/api/admin/content", body);
    toast("Kutubxonaga saqlandi", "ok");
    Object.values(S.up).forEach((u) => u && u.preview && URL.revokeObjectURL(u.preview));
    S.up = { media: null, cover: null, text: null };
    S.form = { type, lang: body.lang };
    await load(true);
    if (then === "deploy") { S.sel = new Set([r.id]); openModal("deploy"); }
    else render();
  } catch (err) { toast(err.message, "err"); }
}

async function saveEdit() {
  const id = S.modal.id;
  const type = F("type", "movie");
  const body = {
    type,
    title: (F("title", "") || "").trim(),
    author: F("author", ""), genre: F("genre", ""),
    description: F("description", ""), category_tab: F("category_tab", ""),
    lang: F("lang", ""),
    duration: parseDur(F("duration", "")),
    pages: parseInt(F("pages", "0"), 10) || 0,
    is_recommended: S.flags.rec ? 1 : 0,
    cache_enabled: S.flags.cache ? 1 : 0,
    visible: S.flags.visible ? 1 : 0,
  };
  if (!body.title) { toast("Sarlavha kerak", "err"); return; }
  if (Object.values(S.up).some((u) => u && u.state === "up")) {
    toast("Yuklash tugashini kuting", "err"); return;
  }
  // Fayllar: "have" — tegilmaydi (yuborilmaydi), yangi — almashtiriladi,
  // yo'q — null bilan olib tashlanadi.
  for (const slot of ["media", "cover", "text"]) {
    const u = S.up[slot];
    if (!u) body[slot] = null;
    else if (u.state === "done") body[slot] = { sha256: u.sha256, name: u.name };
  }
  if (!body.media && !body.text && !S.up.media && !S.up.text) {
    toast("Media yoki matn fayli qolishi kerak", "err"); return;
  }
  try {
    const r = await api.patch("/api/admin/content/" + id, body);
    toast(r.servers_to_sync
      ? `Saqlandi · ${r.servers_to_sync} server yangilanadi`
      : "Saqlandi", "ok");
    closeModal();
    load(true);
  } catch (err) { toast(err.message, "err"); }
}

async function saveAd() {
  const md = S.up.media;
  if (!md || md.state === "up") { toast("Fayl yuklanishini kuting", "err"); return; }
  const body = {
    title: F("title", ""), subtitle: F("subtitle", ""),
    link_url: F("link_url", ""), placement: F("placement", "popup"),
    duration: parseInt(F("duration", "10"), 10) || 0,
    interval_min: parseInt(F("interval_min", "0"), 10) || 0,
    start_time: F("start_time", ""), end_time: F("end_time", ""),
    is_active: !!F("is_active", true),
  };
  if (md.state === "done") body.media = { sha256: md.sha256, name: md.name };
  const picked = [...(S.adPick || new Set())];
  try {
    let id = S.modal.id;
    if (id) {
      await api.patch("/api/admin/ads/" + id, body);
    } else {
      if (!body.media) { toast("Rasm yoki video kerak", "err"); return; }
      id = (await api.post("/api/admin/ads", body)).id;
    }
    // Tayinlovni HAR SAFAR yuboramiz — backend farqni o'zi hisoblab, faqat
    // o'zgargan serverlarga manifest yuboradi.
    const r = await api.post(`/api/admin/ads/${id}/servers`,
                             { server_ids: picked });
    toast(picked.length
      ? `Saqlandi · ${picked.length} serverda ko'rinadi`
        + (r.added || r.removed ? ` (+${r.added} / −${r.removed})` : "")
      : "Saqlandi — hech qanday serverga yuborilmadi", "ok");
    closeModal(); load(true);
  } catch (err) { toast(err.message, "err"); }
}

async function deployGo() {
  const server_ids = (S.data.servers || []).filter((s) => !S.pickOff[s.id]).map((s) => s.id);
  try {
    const at = schedValue("deploy");
    const r = await api.post("/api/admin/deploy", {
      content_ids: [...S.sel], server_ids,
      skip_existing: S.opts.skip_existing, apply_at: at,
    });
    toast(r.apply_at
      ? `Rejaga qo'yildi: ${r.apply_at.slice(0, 16)} — ${r.servers} server`
      : `Tarqatish boshlandi — ${r.servers} server`
        + (r.queued ? `, ${r.queued} tasi navbatda` : ""), "ok");
    S.schedule = { on: false, date: "", time: "", group: "" };
    S.sel.clear(); closeModal(); go("queue");
  } catch (err) { toast(err.message, "err"); }
}

// ============================================================= 10) Boshla
(async function boot() {
  // Backend versiyasini tekshiramiz (eski jarayon "Not Found" bermasin)
  try {
    const h = await api.get("/api/health");
    S.build = h.build || "?";
    if (S.build !== UI_BUILD) S.staleBackend = true;
  } catch { /* health ham yo'q — quyida ko'rinadi */ }
  try {
    const me = await api.get("/api/admin/me");
    S.auth = !!me.auth;
  } catch { S.auth = false; }
  // Refresh qilinganда oxirgi bo'limда qolish uchun URL hashдан tiklaymiz
  restoreFromHash();
  if (S.auth) load(); else render();
  // Jonli yangilanish: faqat holat ko'rinadigan sahifalarда va modal yopiq bo'lsa.
  // Foydalanuvchi biror maydonni yozayotgan yoki saqlanmagan o'zgarishi bo'lsa
  // ham to'xtatamiz — qayta chizish ish ustida xalaqit bermasin.
  setInterval(() => {
    if (!S.auth || S.modal) return;
    if (!["dash", "servers", "queue", "server", "stats"].includes(S.page)) return;
    if (Object.keys(S.srvForm).length) return;        // yuborilmagan sozlama bor
    const ae = document.activeElement;
    if (ae && /^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName || "")) return;
    load(true);
  }, 5000);
})();
