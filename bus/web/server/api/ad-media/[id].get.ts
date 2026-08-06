/** Reklama fayli — Python `/api/ads/{id}/media` ni brauzerga proksi qiladi. */
export default defineEventHandler(async (event) => {
  const id = Number(getRouterParam(event, "id"));
  if (!Number.isInteger(id) || id <= 0) {
    throw createError({ statusCode: 400, statusMessage: "Noto'g'ri id" });
  }
  return proxyMedia(event, `/api/ads/${id}/media`);
});
