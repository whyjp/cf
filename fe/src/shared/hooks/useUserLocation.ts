import { useCallback, useEffect, useState } from "react";
import type { UserCoords, UserLocStatus } from "../types";

/**
 * navigator.geolocation.getCurrentPosition wrapper. Accurate via GPS or
 * wifi triangulation (~10-50m).
 *
 * Status:
 *   "idle"        not asked yet (initial render frame)
 *   "asking"      permission prompt visible
 *   "ok"          coords populated
 *   "denied"      user blocked
 *   "error"       timeout / unavailable
 *   "unsupported" browser has no geolocation API
 *
 * Origin: fe/index.legacy.html:230-261.
 */
export function useUserLocation(): {
  coords: UserCoords | null;
  status: UserLocStatus;
  refresh: () => void;
} {
  const [state, setState] = useState<{
    coords: UserCoords | null;
    status: UserLocStatus;
  }>({ coords: null, status: "idle" });

  const refresh = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setState({ coords: null, status: "unsupported" });
      return;
    }
    setState((s) => ({ coords: s.coords, status: "asking" }));
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        setState({
          coords: { lat: pos.coords.latitude, lon: pos.coords.longitude },
          status: "ok",
        }),
      (err) =>
        setState({
          coords: null,
          status: err.code === err.PERMISSION_DENIED ? "denied" : "error",
        }),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 5 * 60 * 1000 },
    );
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { ...state, refresh };
}
