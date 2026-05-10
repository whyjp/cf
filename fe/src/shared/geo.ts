/**
 * Haversine — great-circle distance in kilometers between two
 * (lat, lon) points on Earth (R=6371km).
 *
 * Used to sort the camp list by proximity to the user's current location
 * and to render the per-card distance badge.
 *
 * Origin: fe/index.legacy.html:266-274.
 */
export function haversineKm(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const R = 6371;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

/**
 * km → display string. < 1km uses meters; < 10km one decimal; otherwise
 * integer km. null/undefined collapses to empty string so callers can
 * `{formatKm(distance)}` without conditionals.
 *
 * Origin: fe/index.legacy.html:276-281.
 */
export function formatKm(km: number | null | undefined): string {
  if (km == null) return "";
  if (km < 1) return `${Math.round(km * 1000)} m`;
  if (km < 10) return `${km.toFixed(1)} km`;
  return `${Math.round(km)} km`;
}
