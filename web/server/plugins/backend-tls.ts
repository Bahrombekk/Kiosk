/**
 * Python (FastAPI) serveri o'zi imzolagan (self-signed) TLS sertifikat bilan
 * ishlaydi. Nitro shu serverga HTTPS orqali ulanishi uchun sertifikatga
 * ISHONISH kerak — lekin butun jarayon uchun TLS tekshiruvini o'chirish
 * (NODE_TLS_REJECT_UNAUTHORIZED=0) EMAS: u har qanday chiquvchi HTTPS
 * so'rovni ham MITM'ga ochib qo'yadi.
 *
 * To'g'ri yo'l: launcher (server/ui/web_server.py) Node jarayoniga
 * NODE_EXTRA_CA_CERTS=<server_cert.pem> beradi — Node backend sertifikatini
 * ishonchli deb biladi, TLS tekshiruvi to'liq yoqiq qoladi (sertifikat
 * SAN'ida 127.0.0.1/localhost bor). Qo'lda ishga tushirishda ham xuddi shu
 * o'zgaruvchini bering.
 *
 * Faqat vaqtinchalik dev-ehtiyoj uchun KIOSK_TLS_INSECURE=1 bilan eski
 * (global o'chirish) rejimni ochish mumkin — ogohlantirish bilan.
 *
 * HTTP (server KIOSK_TLS=0) rejimida bu hech narsaga ta'sir qilmaydi.
 */
export default defineNitroPlugin(() => {
  if (process.env.KIOSK_TLS_INSECURE === "1") {
    console.warn(
      "[kiosk] DIQQAT: KIOSK_TLS_INSECURE=1 — TLS tekshiruvi butun jarayon " +
        "uchun o'chirildi (faqat dev uchun!). Prod'da NODE_EXTRA_CA_CERTS ishlating.",
    );
    process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";
    return;
  }
  const backend = process.env.NUXT_KIOSK_SERVER || "";
  if (backend.startsWith("https://") && !process.env.NODE_EXTRA_CA_CERTS) {
    console.warn(
      "[kiosk] Backend HTTPS, lekin NODE_EXTRA_CA_CERTS berilmagan — " +
        "self-signed sertifikat rad etiladi. Launcher orqali ishga tushiring " +
        "yoki NODE_EXTRA_CA_CERTS=<server_cert.pem> bering.",
    );
  }
});
