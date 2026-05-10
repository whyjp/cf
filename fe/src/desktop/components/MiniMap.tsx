import { useEffect, useRef } from "react";

/**
 * Read-only mini-map for the DetailPanel — no controls, no zoom, no
 * drag. Same tile-gap workaround as the main map (parent's measured
 * height changes after first paint when the panel slides in).
 *
 * Origin: fe/index.legacy.html:568-588.
 */

// Leaflet is loaded via CDN (see index.html / m.html <head>) instead of npm
// import. The leaflet.markercluster plugin's CSS uses background-image: url(...)
// paths relative to the CDN base; switching to npm import breaks these paths.
// `declare const L: any` is the intentional, well-considered tradeoff.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare const L: any;

export interface MiniMapProps {
  lat?: number | null;
  lon?: number | null;
  name?: string;
}

export function MiniMap({ lat, lon, name }: MiniMapProps) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current || lat == null || lon == null) return;
    const map = L.map(ref.current, {
      zoomControl: false,
      attributionControl: false,
      dragging: false,
      scrollWheelZoom: false,
      doubleClickZoom: false,
    });
    map.setView([lat, lon], 13);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 16 }).addTo(map);
    L.marker([lat, lon], {
      icon: L.divIcon({
        html: `<div class="pin-pin" style="width:18px;height:18px;"></div>`,
        iconSize: [18, 18],
        iconAnchor: [9, 9],
        className: "",
      }),
    }).addTo(map);
    [80, 240, 600].forEach((t) =>
      setTimeout(() => {
        try {
          map.invalidateSize({ animate: false });
        } catch {
          /* no-op */
        }
      }, t),
    );
    return () => map.remove();
  }, [lat, lon]);
  if (lat == null || lon == null) {
    return (
      <div className="text-xs text-stone-500 italic px-3 py-6 bg-stone-200/50 rounded-lg">
        좌표 정보가 없는 캠프입니다.
      </div>
    );
  }
  return (
    <div
      ref={ref}
      className="w-full h-44 rounded-lg overflow-hidden border hairline"
      title={name}
    />
  );
}
