"""Geocode each camp's address1 → lat/lon via OSM Nominatim (free, no key).

Storage:
    data/geocode.json — cache of {id: {lat, lon, source, query}} so reruns skip
    Camp.lat / Camp.lon properties updated in FalkorDB.
    camp:{id} row in RocksDB updated with lat/lon.

Nominatim ToS: max 1 req/sec, must include UA. We respect both.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import httpx
from falkordb import FalkorDB


HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"
DETAILS_DIR = DATA / "details"
CACHE_PATH = DATA / "geocode.json"

ROCKS_BASE = "http://localhost:8071"
FALKOR_HOST, FALKOR_PORT, FALKOR_GRAPH = "localhost", 6379, "camfit"

UA = "camfit-puller/0.1 (research; contact via repo whyjp/cf)"
KR_LAT = (33.0, 39.0)
KR_LON = (124.0, 132.0)


def _clean_address(addr: str) -> str:
    """Drop suffix like '원주두리캠핑장' camp-name part — keeps geocode focused on real address."""
    if not addr:
        return ""
    # Drop trailing camp-name (heuristic: take everything up to last numeric token + 길/로/리/면 word)
    # Simplest: take first 3-4 tokens — admin levels.
    parts = addr.split()
    return " ".join(parts[:6])  # cap at first 6 tokens


def geocode_one(client: httpx.Client, query: str) -> tuple[float | None, float | None]:
    try:
        r = client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "kr", "accept-language": "ko"},
            headers={"User-Agent": UA, "Accept": "application/json"},
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            return None, None
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        # Sanity-check Korean bbox
        if not (KR_LAT[0] <= lat <= KR_LAT[1] and KR_LON[0] <= lon <= KR_LON[1]):
            return None, None
        return lat, lon
    except Exception:
        return None, None


def main() -> int:
    cache: dict[str, dict] = {}
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    detail_files = sorted(DETAILS_DIR.glob("*.json"))
    print(f"[geocode] {len(detail_files)} camps; cache hits: {sum(1 for f in detail_files if f.stem in cache and cache[f.stem].get('lat') is not None)}")

    client = httpx.Client(timeout=20.0, follow_redirects=True)
    g = FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(FALKOR_GRAPH)
    rocks = httpx.Client(timeout=10.0)

    success = sum(1 for c in cache.values() if c.get("lat") is not None)
    queried = 0
    for i, df in enumerate(detail_files, 1):
        cid = df.stem
        if cid in cache and cache[cid].get("lat") is not None:
            # Already cached — still ensure KG/rocks have it.
            lat, lon = cache[cid]["lat"], cache[cid]["lon"]
        else:
            try:
                detail = json.loads(df.read_text(encoding="utf-8"))
            except Exception:
                continue
            addr1 = (detail.get("address1") or "").strip()
            addr_short = _clean_address(addr1)
            name = detail.get("name") or ""
            queries = []
            if addr_short:
                queries.append(addr_short)
            # Fallback: city + major + name
            sido_major = " ".join(filter(None, [detail.get("city"), detail.get("major")]))
            if name and sido_major:
                queries.append(f"{sido_major} {name}")
            if sido_major:
                queries.append(sido_major)

            lat, lon, used = None, None, None
            for q in queries:
                lat, lon = geocode_one(client, q)
                queried += 1
                # Nominatim 1 req/sec ToS
                time.sleep(1.05)
                if lat is not None:
                    used = q
                    break
            cache[cid] = {"lat": lat, "lon": lon, "query": used, "source": "nominatim"}
            CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  [{i:3d}/{len(detail_files)}]  {cid}  {lat},{lon}  ← {used!r}")

        if lat is None:
            continue
        success += 1 if cid in cache and cache[cid].get("source") else 0  # avoid double-count

        # FalkorDB
        try:
            g.query(
                "MATCH (c:Camp {id: $id}) SET c.lat = $lat, c.lon = $lon",
                params={"id": cid, "lat": float(lat), "lon": float(lon)},
            )
        except Exception as e:
            print(f"    KG set fail: {e}")

        # RocksDB camp:{id} — refresh lat/lon
        try:
            rr = rocks.get(f"{ROCKS_BASE}/kv/camp:{cid}")
            if rr.status_code == 200:
                row = rr.json()
                row["lat"] = float(lat)
                row["lon"] = float(lon)
                rocks.put(f"{ROCKS_BASE}/kv/camp:{cid}", json=row)
        except Exception as e:
            print(f"    rocks update fail: {e}")

    # Final stats
    have = sum(1 for c in cache.values() if c.get("lat") is not None)
    print(f"[done] {have}/{len(detail_files)} have lat/lon (queried this run: {queried})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
