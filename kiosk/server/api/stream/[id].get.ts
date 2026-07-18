/**
 * Video/audio striming — Python `/api/stream/{id}` ni proksi qiladi.
 * Range (seek) va 206/416 status kodlari shaffof o'tadi.
 */
export default defineEventHandler(async (event) => {
  const id = Number(getRouterParam(event, "id"));
  if (!Number.isInteger(id) || id <= 0) {
    throw createError({ statusCode: 400, statusMessage: "Noto'g'ri id" });
  }
  return proxyMedia(event, `/api/stream/${id}`);
});
