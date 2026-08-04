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
  if (!r.ok) throw new Error((data && (data.detail || data.error)) || `Xato ${r.status}`);
  return data;
}
const api = {
  get: (u) => req("GET", u),
  post: (u, b) => req("POST", u, b || {}),
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
  srvForm: {},           // server sozlamalari formasidagi O'ZGARISHLAR
  sel: new Set(),        // kutubxonada belgilangan id'lar
  modal: null,           // {kind:'upload'|'deploy'|'announce'|'token', ...}
  form: {},              // modal formasi qiymatlari
  // Yuklangan fayllar SLOT bo'yicha (dizaynda ham shunday: o'ngda muqova,
  // pastda media kartasi, kitob uchun matn qatori). Bir slotga yangi fayl
  // tashlansa eskisini almashtiradi.
  up: { media: null, cover: null, text: null },
  pickKind: "",          // "" = kengaytmadan aniqlanadi, aks holda majburiy slot
  flags: { visible: true, rec: true, cache: true },
  pickAll: true,
  pickOff: {},           // deploy: o'chirilgan serverlar
  opts: { skip_existing: true, night_only: false },
  dstep: 1,
};

const NAV = [
  ["dash", "Boshqaruv", "layoutDashboard"],
  ["servers", "Serverlar", "server"],
  ["library", "Kutubxona", "clapperboard"],
  ["queue", "Navbat", "send"],
  ["stats", "Statistika", "barChart"],
  ["logs", "Loglar", "fileText"],
  ["tokens", "Ulash kalitlari", "lock"],
];
const TITLES = {
  dash: ["Boshqaruv", "Barcha poyezd serverlari va kiosklar bir ekranda"],
  servers: ["Serverlar", "Har bir poyezd serveri va uning kiosklari"],
  library: ["Kontent kutubxonasi", "Bulutdagi manba katalog — shundan serverlarga tarqatiladi"],
  queue: ["Tarqatish navbati", "Faol va tugagan ishlar, jonli jarayon"],
  stats: ["Statistika", "Barcha kiosklardan yig'ilgan foydalanish ma'lumoti"],
  logs: ["Loglar", "Serverlardan kelgan hodisalar"],
  tokens: ["Ulash kalitlari", "Yangi poyezd serverini bulutga ulash uchun bir martalik token"],
  server: ["Server tafsiloti", "Kiosklar, sinxronizatsiya, sessiyalar"],
};

// ============================================================ 5) Yuklash
async function load(silent) {
  if (!silent) { S.loading = true; render(); }
  try {
    if (S.page === "dash") S.data.dash = await api.get("/api/admin/overview");
    else if (S.page === "servers") S.data.servers = await api.get("/api/admin/servers");
    else if (S.page === "server") S.data.server = await api.get("/api/admin/servers/" + S.serverId);
    else if (S.page === "library") {
      const p = new URLSearchParams();
      if (S.libType) p.set("type", S.libType);
      if (S.q) p.set("q", S.q);
      S.data.library = await api.get("/api/admin/content?" + p);
      S.data.servers = await api.get("/api/admin/servers");
    } else if (S.page === "queue") S.data.jobs = await api.get("/api/admin/jobs");
    else if (S.page === "stats") {
      const p = new URLSearchParams({ days: String(S.statDays) });
      if (S.statSource) p.set("source", S.statSource);
      S.data.stats = await api.get("/api/admin/stats?" + p);
    }
    else if (S.page === "logs") {
      const p = new URLSearchParams({ limit: "200" });
      if (S.logFilter.level) p.set("level", S.logFilter.level);
      if (S.logFilter.server_id) p.set("server_id", S.logFilter.server_id);
      if (S.q) p.set("q", S.q);
      S.data.logs = await api.get("/api/admin/logs?" + p);
      S.data.servers = await api.get("/api/admin/servers");
    } else if (S.page === "tokens") S.data.tokens = await api.get("/api/admin/enroll-tokens");
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
  load();
}

// ============================================================= 6) Render
function render() {
  const app = document.getElementById("app");
  app.className = "";
  if (S.auth === null) { app.className = "boot"; app.textContent = "Yuklanmoqda…"; return; }
  if (!S.auth) { app.innerHTML = viewLogin(); return; }
  app.innerHTML = viewShell();
}

function viewLogin() {
  return `<div class="login-wrap"><form class="login" data-act="login">
    <div class="side-mark">K</div>
    <h1>KioskCloud</h1>
    <p>Markaziy boshqaruv paneli. Davom etish uchun admin parolini kiriting.</p>
    ${S.err ? `<div class="err-box">${esc(S.err)}</div>` : ""}
    <div class="field"><label>Parol</label>
      <input type="password" name="password" autofocus autocomplete="current-password"></div>
    <button class="btn pri" style="width:100%;justify-content:center" type="submit">Kirish</button>
  </form></div>`;
}

function viewShell() {
  const d = S.data.dash || {};
  const k = d.kpis || {};
  const jobs = (S.data.jobs || d.jobs || []).filter((j) => j.state === "running");
  const badges = {
    servers: k.servers_total ? (k.servers_total - k.servers_online) || "" : "",
    queue: jobs.length || "",
  };
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
      <div class="side-status">
        <div class="side-status-top">
          <span class="dot ${k.servers_online ? "live" : "off"}"></span>
          <span class="side-status-title">${k.servers_online ? "Bulut ishlayapti" : "Server ulanmagan"}</span>
        </div>
        <div class="side-status-note">
          ${k.servers_online || 0} / ${k.servers_total || 0} server onlayn<br>
          ${k.kiosks_online || 0} / ${k.kiosks_total || 0} kiosk
        </div>
        <div class="side-hr"></div>
        <div class="side-user">
          <div class="avatar">A</div>
          <div style="flex:1;min-width:0">
            <div class="side-user-name">Admin</div>
            <div class="side-user-role">Super admin</div>
          </div>
          <button class="side-out" data-act="logout">Chiqish</button>
        </div>
      </div>
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
      </header>
      <main class="page">
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

function pageBody() {
  switch (S.page) {
    case "dash": return pageDash();
    case "servers": return pageServers();
    case "server": return pageServer();
    case "library": return pageLibrary();
    case "queue": return pageQueue();
    case "stats": return pageStats();
    case "logs": return pageLogs();
    case "tokens": return pageTokens();
    default: return "";
  }
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
    ${pend.map((s) => `<div class="list-row">
      <span class="dot ${s.online ? "live" : "off"}"></span>
      <div style="flex:1;min-width:0">
        <div class="strong">${esc(s.name)}</div>
        <div class="dim">${esc(s.id)} · ${s.kiosks_total} kiosk ·
          versiya ${esc(s.version || "?")} · ${ago(s.last_seen)}</div>
      </div>
      <button class="btn sm ghost" data-act="srv-reject" data-id="${s.id}">Rad etish</button>
      <button class="btn sm pri" data-act="srv-approve" data-id="${s.id}">
        ${ic("check", 14, "#fff", 2.6)} Tasdiqlash</button>
    </div>`).join("")}
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
  return `
  <button class="btn sm ghost" data-act="go" data-page="servers" style="margin-bottom:14px">
    ${ic("chevronLeft", 14)} Serverlar ro'yxati</button>

  <div class="card">
    <div class="row wrap">
      <span class="dot ${s.online ? (s.synced ? "live" : "sync") : "off"}"></span>
      <div style="flex:1;min-width:180px">
        <div class="row"><div class="top-title">${esc(s.name)}</div>
          ${s.online ? `<span class="pill ok">Onlayn</span>` : `<span class="pill mut">Offlayn</span>`}
          ${s.approved ? "" : `<span class="pill warn">tasdiqlanmagan</span>`}
          ${licPill(s)}</div>
        <div class="dim" style="margin-top:4px">
          ${esc(s.route || "—")} · ${esc(s.id)} · versiya ${esc(s.version || "?")}
          · oxirgi aloqa ${ago(s.last_seen)}</div>
      </div>
      ${s.approved ? "" : `<button class="btn sm pri" data-act="srv-approve"
        data-id="${s.id}">${ic("check", 14, "#fff", 2.6)} Tasdiqlash</button>`}
      <button class="btn sm" data-act="cmd" data-kind="sync_now">${ic("refresh", 14)} Hoziroq sinxronla</button>
      <button class="btn sm" data-act="announce-open">${ic("megaphone", 14)} E'lon</button>
      <button class="btn sm" data-act="cmd" data-kind="cache_clear">${ic("trash", 14)} Kesh tozalash</button>
      <button class="btn sm danger" data-act="srv-del">${ic("x", 14)} Ro'yxatdan o'chirish</button>
    </div>
  </div>

  <div class="grid k4" style="margin-top:16px">
    ${stat("Kiosklar", `${s.kiosks_online}/${s.kiosks_total}`)}
    ${stat("Kontent", s.assigned)}
    ${stat("Bugungi sessiyalar", d.sessions_today)}
    ${stat("Statistika", `${d.stats.events || 0}`,
      s.stats_pending ? `serverda ${s.stats_pending} event navbatda`
        : (s.stats_total ? "hammasi ko'chirilgan" : "bulutda saqlangan"))}
  </div>

  ${srvWebCard(s)}
  ${srvSettingsCard(s)}

  <h3 class="sec-title">Kiosklar (${d.kiosks.length})</h3>
  <div class="card" style="padding:14px 4px"><div class="tbl-wrap"><table class="tbl">
    <thead><tr><th style="padding-left:14px">Kiosk</th><th>Xona</th>
      <th class="col-hide">IP</th><th>Kesh</th><th class="col-hide">Disk</th>
      <th>Oxirgi</th><th>Boshqarish</th></tr></thead>
    <tbody>${d.kiosks.length ? d.kiosks.map((k) => `<tr>
      <td style="padding-left:14px"><div class="row">
        <span class="dot ${k.online ? "live" : "off"}"></span>
        <div><div class="strong">${esc(k.kiosk_no ? "KIOSK-" + k.kiosk_no : k.device_id)}</div>
          <div class="dim">${esc(k.device_id)}</div></div></div></td>
      <td>${esc(k.room || "—")}</td>
      <td class="col-hide dim">${esc(k.ip || "—")}</td>
      <td class="num">${k.cached_n} fayl</td>
      <td class="col-hide dim">${bytes(k.disk_free)} bo'sh</td>
      <td class="dim">${ago(k.last_seen)}</td>
      <td><div class="row" style="gap:6px">
        <button class="btn sm ghost" data-act="kiosk-cmd" data-dev="${esc(k.device_id)}"
          data-kind="sync" title="Media keshni hoziroq yuklash">${ic("refresh", 13)}</button>
        <button class="btn sm ghost" data-act="kiosk-cmd" data-dev="${esc(k.device_id)}"
          data-kind="cache_clear" title="Lokal keshni tozalash">${ic("trash", 13)}</button>
        <button class="btn sm ghost" data-act="kiosk-cmd" data-dev="${esc(k.device_id)}"
          data-kind="cache_off" title="Keshni o'chirish (faqat striming)">${ic("power", 13)}</button>
        <button class="btn sm ghost" data-act="kiosk-forget" data-dev="${esc(k.device_id)}"
          title="Ro'yxatdan olib tashlash">${ic("x", 13)}</button>
      </div></td></tr>`).join("")
      : `<tr><td colspan="7"><div class="empty">Kiosk ma'lumoti yo'q</div></td></tr>`}
    </tbody></table></div></div>

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

  <h3 class="sec-title">Foydalanuvchi sessiyalari</h3>
  <div class="card" style="padding:14px 4px"><div class="tbl-wrap"><table class="tbl">
    <thead><tr><th style="padding-left:14px">Kiosk</th><th>Boshlangan</th>
      <th>Hodisa</th><th>Ko'rilgan kontent</th><th>Til</th></tr></thead>
    <tbody>${d.sessions.length ? d.sessions.map((u) => `<tr>
      <td style="padding-left:14px" class="dim">${esc(u.device_id || "—")}</td>
      <td class="dim">${esc(String(u.started || "").slice(5, 16))}</td>
      <td class="num">${u.events}</td>
      <td>${esc(u.content)}</td><td class="dim">${esc((u.lang || "uz").toUpperCase())}</td>
      </tr>`).join("") : `<tr><td colspan="5"><div class="empty">Sessiya yo'q</div></td></tr>`}
    </tbody></table></div></div>

  <h3 class="sec-title">Shu serverning loglari</h3>
  ${logTable(d.logs, false)}`;
}

/** Veb ilova (poyezd.uz) kartasi — holat + masofadan yoqish/o'chirish. */
function srvWebCard(s) {
  const on = !!s.web_running;
  const wanted = String((s.settings || {}).web_enabled ?? "1") !== "0";
  return `<h3 class="sec-title">Veb ilova (poyezd.uz)</h3>
  <div class="card"><div class="row wrap">
    <span class="dot ${on ? "live" : "off"}"></span>
    <div style="flex:1;min-width:200px">
      <div class="strong">${on ? "Ishlayapti" : "Ishlamayapti"}
        ${!on && wanted ? `<span class="pill warn">yoqilgan, lekin ko'tarilmagan</span>` : ""}
        ${on && !wanted ? `<span class="pill warn">sozlamada o'chiq</span>` : ""}</div>
      <div class="dim">Yo'lovchilar vagon Wi-Fi'idan brauzer bilan kiradi.
        Node.js topilmasa ko'tarilmaydi.</div>
    </div>
    <button class="btn sm" data-act="web-cmd" data-kind="start"
      ${on ? "disabled" : ""}>${ic("globe", 14)} Yoqish</button>
    <button class="btn sm ghost" data-act="web-cmd" data-kind="stop"
      ${on ? "" : "disabled"}>O'chirish</button>
  </div></div>`;
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
  ["ad_interval_min", "Reklama oralig'i (daq)", "num", "10"],
  ["media_cache", "Kiosk lokal keshi", "bool", ""],
  ["cache_limit_gb", "Kesh chegarasi (GB)", "num", "50"],
  ["sos_enabled", "SOS tugmasi", "bool", ""],
  ["default_theme", "Standart mavzu (light/dark)", "text", "light"],
];

function srvSettingsCard(s) {
  const cur = s.settings || {};
  const v = (k) => (S.srvForm[k] !== undefined ? S.srvForm[k] : (cur[k] ?? ""));
  const dirty = Object.keys(S.srvForm).length;
  return `<h3 class="sec-title">Server sozlamalari</h3>
  <div class="card">
    <div class="card-sub" style="margin-bottom:14px">Bu qiymatlar poyezd
      serveridan o'qildi. O'zgartirib «Yuborish»ni bosing — server ularni
      darhol qo'llaydi va kiosklarga yetkazadi.</div>
    <div class="grid k3">
      ${SRV_FIELDS.map(([k, label, kind, ph]) => {
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
    <div class="row" style="margin-top:14px">
      <div class="dim" style="flex:1">${dirty
        ? `${dirty} maydon o'zgardi — hali yuborilmadi`
        : "O'zgarish yo'q"}</div>
      <button class="btn ghost sm" data-act="srv-reset" ${dirty ? "" : "disabled"}>
        Bekor qilish</button>
      <button class="btn pri sm" data-act="srv-save" ${dirty ? "" : "disabled"}>
        ${ic("send", 14, "#fff")} Yuborish</button>
    </div>
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
  return `
  <div class="filters">
    ${tabs.map(([k, label]) => `<button class="chip ${S.libType === k ? "on" : ""}"
        data-act="lib-type" data-type="${k}">${label}</button>`).join("")}
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
function pageQueue() {
  const jobs = S.data.jobs || [];
  if (!jobs.length) return `<div class="card empty">Hali tarqatish bo'lmagan</div>`;
  return jobs.map((j) => {
    const pct = jobPct(j);
    const stateP = { running: ["acc", "ketmoqda"], done: ["ok", "tugadi"],
                     error: ["err", "xato"], cancelled: ["mut", "bekor"] }[j.state]
                   || ["mut", j.state];
    return `<section class="card" style="margin-bottom:14px">
      <div class="row wrap">
        <div style="flex:1;min-width:200px">
          <div class="row"><div class="card-title">${esc(j.title || j.kind)}</div>
            <span class="pill ${stateP[0]}">${stateP[1]}</span></div>
          <div class="card-sub">${esc(String(j.created_at || "").slice(5, 16))} ·
            ${j.n_items} fayl · ${j.n_targets} server · ${j.kind === "remove" ? "o'chirish" : "yuklash"}</div>
        </div>
        <div class="mono strong">${pct}%</div>
        ${j.state === "running"
          ? `<button class="btn sm ghost" data-act="job-cancel" data-id="${j.id}">Bekor qilish</button>` : ""}
      </div>
      <div class="bar ${j.state === "running" ? "flow" : j.state === "error" ? "err" : "ok"}"
           style="margin:12px 0 14px"><i style="width:${pct}%"></i></div>
      <div class="grid k2">
        ${j.targets.map((t) => {
          const p = { pending: ["mut", "kutilmoqda"], queued: ["warn", "navbatda (offlayn)"],
                      running: ["acc", "yuklanmoqda"], done: ["ok", "tugadi"],
                      error: ["err", t.error || "xato"] }[t.state] || ["mut", t.state];
          return `<div class="list-row">
            <div style="flex:1;min-width:0">
              <div class="strong">${esc(t.name || t.server_id)}</div>
              <div class="dim">${t.bytes_total ? bytes(t.bytes_done) + " / " + bytes(t.bytes_total) : "—"}</div>
            </div>
            <div style="width:70px"><div class="bar"><i style="width:${t.state === "done" ? 100 : t.pct}%"></i></div></div>
            <span class="pill ${p[0]}">${esc(p[1])}</span>
          </div>`;
        }).join("")}
      </div>
      ${j.targets.some((t) => t.state === "queued") ? `<div class="dim" style="margin-top:12px">
        Offlayn serverlar navbatda saqlanadi — internet tiklanishi bilan yuklash
        avtomatik davom etadi. Uzilgan fayl boshidan emas, to'xtagan joyidan (Range) yuklanadi.
      </div>` : ""}
    </section>`;
  }).join("");
}

// ------------------------------------------------------------- Statistika
function pageStats() {
  const d = S.data.stats;
  if (!d) return "";
  const t = d.totals, max = Math.max(1, ...d.daily.map((x) => x.n));
  const sync = d.sync || {};
  const src = d.by_source || {};
  const kpi = (label, v, note) => `<div class="kpi"><div class="kpi-label">${label}</div>
    <div class="kpi-value">${v}</div><div class="kpi-note">${note}</div></div>`;
  return `
  <div class="filters">
    ${[7, 14, 30, 90].map((n) => `<button class="chip ${S.statDays === n ? "on" : ""}"
      data-act="stat-days" data-days="${n}">${n} kun</button>`).join("")}
    <span style="width:10px"></span>
    ${[["", "Kiosk + veb"], ["kiosk", "Faqat kiosk ekrani"], ["web", "Faqat veb"]]
      .map(([k, l]) => `<button class="chip ${S.statSource === k ? "on" : ""}"
        data-act="stat-source" data-source="${k}">${l}</button>`).join("")}
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
        <div class="card-sub">Jami ${t.events} event bulutda saqlangan</div></div>
    </div>
    <div class="chart">${d.daily.map((x) => `<div title="${x.date}: ${x.n} sessiya">
      <div class="b" style="height:${Math.round(100 * x.n / max)}%"></div>
      <div class="d">${x.date.slice(8)}</div></div>`).join("")}</div>
  </section>

  <div class="grid k2" style="margin-top:16px">
    <section class="card">
      <div class="card-head"><div class="card-title">Manba bo'yicha</div></div>
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
        <span class="dim card-link">sessiya bo'yicha</span></div>
      ${(d.devices || []).length ? `<div class="tbl-wrap"><table class="tbl">
        <thead><tr><th>Qurilma</th><th>Manba</th><th>Sessiya</th>
          <th class="col-hide">Oxirgi</th></tr></thead>
        <tbody>${d.devices.map((x) => `<tr>
          <td><div class="strong">${esc(x.device_id || "—")}</div>
            <div class="dim">${esc(x.server_name || x.server_id || "")}</div></td>
          <td><span class="pill ${x.source === "web" ? "acc" : "mut"}">${
            x.source === "web" ? "veb" : "kiosk"}</span></td>
          <td class="num strong">${x.sessions}</td>
          <td class="col-hide dim">${esc(String(x.last_ts || "").slice(5, 16))}</td>
        </tr>`).join("")}</tbody></table></div>`
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
  return `<div class="card" style="padding:14px 4px"><div class="tbl-wrap"><table class="tbl">
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
    ${[["skip_existing", "sha256 mos kelsa qayta yubormaslik",
        "Serverda allaqachon bor fayl SIM-trafikni behuda sarflamaydi"],
       ["night_only", "Tungi soatlarda yuborish (00:00 – 06:00)",
        "SIM-trafikni tejash uchun"]].map(([k, t2, s2]) => `
      <div class="list-row"><div style="flex:1"><div class="strong">${t2}</div>
        <div class="dim">${s2}</div></div>
        <button class="tgl ${S.opts[k] ? "on" : ""}" data-act="opt" data-key="${k}"><i></i></button>
      </div>`).join("")}
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
           Tarqatishni boshlash</button>`}
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
  return `${head("E'lon yuborish", "Matn shu serverning barcha kiosklarida ko'rinadi")}
  <div class="field"><label>Matn</label>
    <textarea data-bind="text" placeholder="Masalan: Buxoro bekatiga 20 daqiqa"
      >${esc(F("text", ""))}</textarea></div>
  <div class="modal-foot">
    <button class="btn ghost" data-act="modal-close">Bekor qilish</button>
    <button class="btn pri" data-act="announce-go">Yuborish</button>
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
  if (act === "log-level") { S.logFilter.level = el.dataset.level; load(); return; }

  // ---- kutubxona tanlash
  if (act === "sel") {
    const id = +el.dataset.id;
    S.sel.has(id) ? S.sel.delete(id) : S.sel.add(id);
    render(); return;
  }
  if (act === "sel-clear") { S.sel.clear(); render(); return; }

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
  if (act === "srv-reset") { S.srvForm = {}; render(); return; }
  if (act === "srv-save") {
    const values = { ...S.srvForm };
    if (!Object.keys(values).length) return;
    try {
      const r = await api.post(`/api/admin/servers/${S.serverId}/settings`,
                               { values });
      toast(`Yuborildi: ${r.sent.length} sozlama`, "ok");
      S.srvForm = {};
      setTimeout(() => load(true), 1200);   // server qo'llagach qaytib o'qiymiz
    } catch (err) { toast(err.message, "err"); }
    return;
  }
  // ---- veb ilova
  if (act === "web-cmd") {
    try {
      await api.post(`/api/admin/servers/${S.serverId}/web`,
                     { action: el.dataset.kind });
      toast(el.dataset.kind === "start" ? "Veb yoqilmoqda…" : "Veb o'chirilmoqda…", "ok");
      setTimeout(() => load(true), 2500);
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
    try {
      await api.post(`/api/admin/servers/${el.dataset.id}/approve`);
      toast("Server tasdiqlandi — endi kontent tarqatish mumkin", "ok");
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
  if (act === "drop" || act === "pick-cover" || act === "pick-media"
      || act === "pick-text") {
    // Qaysi slotga tushishi: tugmadan aniq, "drop"da esa kengaytmadan
    S.pickKind = act === "drop" ? "" : act.replace("pick-", "");
    const inp = document.querySelector('[data-act="file-input"]');
    if (inp) {
      inp.accept = S.pickKind === "cover" ? "image/*"
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
    try {
      await api.post(`/api/admin/servers/${S.serverId}/command`, { kind: "announce", text });
      toast("E'lon yuborildi", "ok"); closeModal();
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
  if (e.target.dataset.act === "file-input") pickFiles([...e.target.files]);
});
document.addEventListener("submit", async (e) => {
  if (e.target.dataset.act !== "login") return;
  e.preventDefault();
  const pass = new FormData(e.target).get("password");
  try {
    await api.post("/api/admin/login", { password: pass });
    S.auth = true; S.err = ""; load();
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
    const old = S.up[slot];
    if (old && old.preview) URL.revokeObjectURL(old.preview);
    const u = {
      name: f.name, pct: 0, loaded: 0, total: f.size, size: f.size, state: "up",
      preview: slot === "cover" && f.type.startsWith("image/")
        ? URL.createObjectURL(f) : null,
    };
    S.up[slot] = u;
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

async function deployGo() {
  const server_ids = (S.data.servers || []).filter((s) => !S.pickOff[s.id]).map((s) => s.id);
  try {
    const r = await api.post("/api/admin/deploy", {
      content_ids: [...S.sel], server_ids,
      skip_existing: S.opts.skip_existing, night_only: S.opts.night_only,
    });
    toast(`Tarqatish boshlandi — ${r.servers} server` +
          (r.queued ? `, ${r.queued} tasi navbatda` : ""), "ok");
    S.sel.clear(); closeModal(); go("queue");
  } catch (err) { toast(err.message, "err"); }
}

// ============================================================= 10) Boshla
(async function boot() {
  try {
    const me = await api.get("/api/admin/me");
    S.auth = !!me.auth;
  } catch { S.auth = false; }
  if (S.auth) load(); else render();
  // Jonli yangilanish: faqat holat ko'rinadigan sahifalarда va modal yopiq bo'lsa
  setInterval(() => {
    if (S.auth && !S.modal && ["dash", "servers", "queue", "server"].includes(S.page)) {
      load(true);
    }
  }, 5000);
})();
