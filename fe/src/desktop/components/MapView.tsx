import { useEffect, useRef } from "react";
import type { FeaturedAxis, Site, EtaResult, UserCoords, UserLocStatus } from "../../shared/types";

/**
 * Leaflet + markercluster wrapper. Korea-bounded, single re-render pin
 * pass per `rows`/`etaMap` change, focused fly-to per `focused`, and a
 * separate user-location marker layer that never clusters.
 *
 * Origin: fe/index.legacy.html:430-566.
 *
 * Leaflet & MarkerClusterGroup come from CDN globals (`window.L` + the
 * markercluster plugin). The `<head>` of fe/index.html keeps the same
 * CDN <link>/<script> tags as legacy — markercluster's CSS resolves its
 * pin background-image relative to the CDN, so swapping to npm here
 * would silently break those images. Plan B5 cleanup may revisit.
 */

// Leaflet is loaded via CDN (see index.html / m.html <head>) instead of npm
// import. The leaflet.markercluster plugin's CSS uses background-image: url(...)
// paths relative to the CDN base; switching to npm import breaks these paths.
// `declare const L: any` is the intentional, well-considered tradeoff.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare const L: any;

export interface MapViewProps {
  rows: Site[];
  onPick: (id: string) => void;
  focused?: Site | null;
  etaMap?: Record<string, EtaResult> | null;
  axes: FeaturedAxis[];
  userLoc?: { coords: UserCoords | null; status: UserLocStatus };
}

export function MapView({ rows, onPick, focused, etaMap, axes, userLoc }: MapViewProps) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const userMarkerRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const layerRef = useRef<any>(null);
  const mapEl = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (mapRef.current) return;
    // Korea-only bounds: SW (Marado / 제주 남쪽) → NE (북한 최북단). Pan/zoom
    // is clamped here so users can't drift to China/Japan tiles. Viscosity=1
    // hard-locks the bounds (no rubber-band).
    const KR_BOUNDS = L.latLngBounds([32.8, 124.0], [38.9, 132.0]);
    const map = L.map(mapEl.current, {
      center: [36.5, 127.8],
      zoom: 7,
      zoomControl: true,
      attributionControl: true,
      preferCanvas: true,
      minZoom: 6,
      maxZoom: 18,
      maxBounds: KR_BOUNDS,
      maxBoundsViscosity: 1.0,
      worldCopyJump: false,
    });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap contributors",
      maxZoom: 18,
      bounds: KR_BOUNDS,
      noWrap: true,
    }).addTo(map);
    mapRef.current = map;
    layerRef.current = L.markerClusterGroup({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      iconCreateFunction: (cluster: any) => {
        const c = cluster.getChildCount();
        const cls = c >= 50 ? "pin-cluster lg" : "pin-cluster";
        return L.divIcon({ html: `<div class="${cls}">${c}</div>`, className: "", iconSize: null });
      },
      showCoverageOnHover: false,
      spiderfyOnMaxZoom: true,
      // Tighter merge — default 80px clumps neighbouring camps too eagerly.
      // 35px keeps only true overlaps merged so individual pins stay visible.
      maxClusterRadius: 18,
      // Past zoom 12 (city-level), drop clustering entirely. Each camp gets
      // its own pin — useful when zooming into a popular sigungu.
      disableClusteringAtZoom: 12,
    });
    map.addLayer(layerRef.current);

    // Tile-gap fix — Leaflet leaves blank rows when its container resizes
    // without it knowing (header/filter bar height changes after first paint,
    // window resizes, etc.). ResizeObserver + a few delayed invalidations
    // catch every regrow path. The "stripe" rendering bug in the user's
    // screenshot was this: outer card got its final height after Leaflet's
    // initial sizing, so half the tile pane was still measured at 0.
    const invalidate = () => {
      try {
        map.invalidateSize({ animate: false, pan: false });
      } catch {
        /* no-op */
      }
    };
    [80, 240, 600, 1500].forEach((t) => setTimeout(invalidate, t));
    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined" && mapEl.current) {
      ro = new ResizeObserver(() => invalidate());
      ro.observe(mapEl.current);
    }
    window.addEventListener("resize", invalidate);
    map.__cleanup = () => {
      window.removeEventListener("resize", invalidate);
      if (ro) ro.disconnect();
    };
  }, []);

  useEffect(() => {
    if (!layerRef.current) return;
    layerRef.current.clearLayers();
    const valid = rows.filter((r) => r.lat != null && r.lon != null);
    valid.forEach((r) => {
      // Pin tone = first matching featured-axis id (rendered as `pin-pin <id>`).
      // Falls back to "" (default moss-green pin) when no axis matches.
      const tone = (axes || []).find((a) => r[`has_${a.id}`])?.id || "";
      const m = L.marker([r.lat, r.lon], {
        icon: L.divIcon({
          className: "",
          html: `<div class="pin-pin ${tone}" style="width:20px;height:20px;"></div>`,
          iconSize: [20, 20],
          iconAnchor: [10, 10],
        }),
        title: r.name,
      });
      m.on("click", () => onPick(r.id));
      const eta = etaMap?.[r.id];
      const etaLabel =
        eta && eta.minutes != null
          ? `<br/><span style="opacity:.85;color:#c8553d">🚗 ${Math.floor(eta.minutes / 60)}시 ${eta.minutes % 60}분</span>`
          : "";
      const addrLabel = r.address
        ? `<br/><span style="opacity:.6;font-size:10px">${r.address}</span>`
        : "";
      m.bindTooltip(
        `<b>${r.name}</b><br/><span style="opacity:.7">${r.sido || ""} ${r.sigungu || ""}</span>${addrLabel}${etaLabel}`,
        { direction: "top", offset: [0, -8] },
      );
      layerRef.current.addLayer(m);
    });
    if (valid.length && !focused) {
      const bounds = L.latLngBounds(valid.map((r) => [r.lat, r.lon]));
      mapRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 11 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, etaMap]);

  useEffect(() => {
    if (focused && focused.lat != null && focused.lon != null) {
      mapRef.current.setView([focused.lat, focused.lon], 13, { animate: true });
    }
  }, [focused]);

  // User-location pin — sky-blue dot, separate from the marker cluster
  // layer so it never gets clustered. Re-positions when coords update.
  useEffect(() => {
    if (!mapRef.current) return;
    const coords = userLoc && userLoc.coords;
    if (!coords) {
      if (userMarkerRef.current) {
        mapRef.current.removeLayer(userMarkerRef.current);
        userMarkerRef.current = null;
      }
      return;
    }
    const icon = L.divIcon({
      html: `<div style="width:18px;height:18px;border-radius:999px;
              background:#2563eb;border:3px solid #f7f4e8;
              box-shadow:0 0 0 6px rgba(37,99,235,0.18),0 1px 4px rgba(26,26,23,0.4);"></div>`,
      iconSize: [18, 18],
      iconAnchor: [9, 9],
      className: "",
    });
    if (userMarkerRef.current) {
      userMarkerRef.current.setLatLng([coords.lat, coords.lon]);
      userMarkerRef.current.setIcon(icon);
    } else {
      userMarkerRef.current = L.marker([coords.lat, coords.lon], {
        icon,
        zIndexOffset: 9999,
        interactive: true,
        title: "내 위치",
      }).addTo(mapRef.current);
      userMarkerRef.current.bindTooltip("내 위치", { direction: "top", offset: [0, -10] });
    }
  }, [
    userLoc?.coords?.lat,
    userLoc?.coords?.lon,
  ]);

  return <div ref={mapEl} className="w-full h-full" />;
}
