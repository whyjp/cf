"""Run with: python tests/smoke_etago_geo.py — fast import + unit smoke.

Lives outside tests/unit so it doesn't run under the default pytest collection,
but is the canonical way to verify the etago-geocode wiring without a live
Naver/Kakao network call. The end-to-end check requires the etago binary
to clear Device Guard / WDAC; running this script is the fast prelude.
"""
from __future__ import annotations
import sys
sys.stdout.reconfigure(encoding="utf-8")

from camfit_crawl.adapters.geocode.etago_subprocess import (
    EtagoGeocoderSubprocess, _record_to_point, _parse_ndjson,
)
from camfit_crawl.settings import Settings
from camfit_crawl.domain.models import GeoPoint


def main() -> int:
    # _parse_ndjson preserves order and tolerates blanks.
    blob = (
        b'{"query":"a","lat":1.0,"lon":2.0,"source":"naver"}\n'
        b'\n'
        b'{"query":"b","error":"no result"}\n'
    )
    recs = _parse_ndjson(blob, expected=2)
    assert len(recs) == 2
    assert recs[0]["lat"] == 1.0
    assert recs[1]["error"] == "no result"

    # _record_to_point keeps GeoPoint validation honest.
    p = _record_to_point({"lat": 37.5, "lon": 127.0})
    assert isinstance(p, GeoPoint) and p.lat == 37.5
    assert _record_to_point({"query": "x", "error": "y"}) is None
    assert _record_to_point(None) is None
    # Out-of-bbox → None (KR validator on GeoPoint rejects it).
    assert _record_to_point({"lat": 1.0, "lon": 2.0}) is None

    # Settings now defaults to etago.
    s = Settings()
    assert s.geocoder == "etago", f"expected etago, got {s.geocoder}"

    # Adapter import — instance creation still requires the binary to exist.
    # We don't try to call it here (the binary may be Device-Guard-blocked).
    try:
        a = EtagoGeocoderSubprocess()
        print(f"binary resolved: {a.bin_path}")
    except Exception as e:
        print(f"binary not resolvable (acceptable in CI): {e}")

    print("OK — etago geocode wiring smoke pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
