/**
 * Veb foydalanish statistikasi — brauzerdan kelgan event to'plamini Python
 * backend'ning `POST /api/stats` ga uzatadi. `source: "web"` qo'shiladi, shunda
 * admin panelda veb statistikasi kiosk'nikidan ajratiladi (Manba filtri).
 *
 * Brauzer bevosita backend'ga ulanmaydi (API kalit server tomonda) — shu
 * proksi orqali. device_id brauzer localStorage'idagi barqaror `web-<uuid>`
 * (noyob foydalanuvchi / unique visitor o'lchovi uchun).
 */
export default defineEventHandler(async (event) => {
  const body = await readBody<{
    device_id?: string;
    events?: unknown[];
  }>(event);
  if (!body || !Array.isArray(body.events) || !body.events.length) {
    return { saved: 0 };
  }
  try {
    return await backendFetch("/api/stats", {
      method: "POST",
      body: {
        device_id: String(body.device_id || "").slice(0, 64),
        events: body.events.slice(0, 500),
        source: "web",
      },
    });
  } catch {
    // Statistika ikkilamchi — backend o'chiq bo'lsa jim yutamiz (frontend
    // navbatni saqlab, keyin qayta yuboradi).
    return { saved: 0 };
  }
});
