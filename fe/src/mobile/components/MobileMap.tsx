import { useEffect, useRef } from "react";
import type { Site } from "../../shared/types";

/**
 * MobileMap — Leaflet + markercluster, 모바일 전용 minimal wrapper.
 *
 * Desktop MapView 와의 차이:
 *   - 줌 컨트롤 우하단 (BottomSheet 핸들 / 좌하단 LocationChip 과 안 겹치게).
 *     기본 좌상단은 모바일에서 TopBar 와 시각적으로 충돌.
 *   - axes / featured-pin tone / focused / userLoc 등은 C3+ 에서 추가.
 *     C2 first cut 은 marker plot + onPick 만.
 *   - cleanup 은 unmount 시 map.remove() — 모바일은 라우팅 시 컨테이너가
 *     사라질 수 있으므로 명시적 cleanup 필요.
 *
 * Leaflet 은 m.html 의 CDN <script> 로 window.L 에 붙어 있다 (desktop
 * MapView 와 동일 정책). 그래서 npm import 가 아니라 `declare const L: any`.
 * markercluster 도 같은 CDN 을 통해 L.markerClusterGroup 으로 제공.
 */

// Leaflet is loaded via CDN (see index.html / m.html <head>) instead of npm
// import. The leaflet.markercluster plugin's CSS uses background-image: url(...)
// paths relative to the CDN base; switching to npm import breaks these paths.
// `declare const L: any` is the intentional, well-considered tradeoff.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare const L: any;

interface Props {
  rows: Site[];
  onPick?: (id: string) => void;
}

export function MobileMap({ rows, onPick }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const clusterRef = useRef<any>(null);
  // onPick 을 ref 로 잡아서, 핸들러 갱신만으로 마커 layer 를 다시 생성하지
  // 않게 한다 (C3 에서 setPicked 가 매번 다른 ref 일 수 있음).
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const map = L.map(ref.current, {
      center: [36.5, 127.8],
      zoom: 7,
      zoomControl: false, // 기본 좌상단 끄고
      attributionControl: true,
      preferCanvas: true,
    });
    // 우하단 커스텀 위치
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "© OpenStreetMap contributors",
    }).addTo(map);
    mapRef.current = map;

    const cluster = L.markerClusterGroup({
      showCoverageOnHover: false,
      // 모바일은 손가락 터치 영역이 크므로 cluster 반경을 더 타이트하게.
      // desktop 18 vs mobile 20 — 살짝 여유.
      maxClusterRadius: 20,
      disableClusteringAtZoom: 12,
    });
    map.addLayer(cluster);
    clusterRef.current = cluster;

    // Tile-gap fix — desktop MapView 와 동일. BottomSheet 가 시트 높이를
    // 바꾸면 map container 가 resize 되므로 invalidateSize 가 필수.
    const invalidate = () => {
      try {
        map.invalidateSize({ animate: false, pan: false });
      } catch {
        /* no-op */
      }
    };
    [80, 240, 600, 1500].forEach((t) => setTimeout(invalidate, t));
    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined" && ref.current) {
      ro = new ResizeObserver(() => invalidate());
      ro.observe(ref.current);
    }
    window.addEventListener("resize", invalidate);

    return () => {
      window.removeEventListener("resize", invalidate);
      if (ro) ro.disconnect();
      map.remove();
      mapRef.current = null;
      clusterRef.current = null;
    };
  }, []);

  // rows 갱신 시 마커 다시 그리기.
  useEffect(() => {
    const cluster = clusterRef.current;
    if (!cluster) return;
    cluster.clearLayers();
    for (const r of rows) {
      if (typeof r.lat !== "number" || typeof r.lon !== "number") continue;
      const m = L.marker([r.lat, r.lon], { title: r.name });
      m.on("click", () => onPickRef.current?.(r.id));
      cluster.addLayer(m);
    }
  }, [rows]);

  return <div ref={ref} className="absolute inset-0" />;
}
