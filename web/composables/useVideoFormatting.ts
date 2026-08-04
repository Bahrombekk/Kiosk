export function useVideoFormatting() {
  const { t } = useI18n();

  function formatVideoRuntime(runtime: number) {
    const hours = Math.floor(runtime / 60);
    const minutes = runtime % 60;

    return `• ${hours} ${t("hour_short")} ${minutes} ${t("minutes_short")}`;
  }

  function formatVideoGenres(genres: string[]) {
    return genres.join(", ");
  }

  return {
    formatVideoGenres,
    formatVideoRuntime,
  };
}
