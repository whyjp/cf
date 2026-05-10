"""Print camp count and sample rows from a saved camfit HTML snapshot (e.g. cf_home.html).

No Scrapling dependency — uses installed ``camfit-puller`` parser only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    from camfit_crawl.parser import parse_list_html

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "html_path",
        nargs="?",
        default="data/cf_home.html",
        type=Path,
        help="Path to saved HTML (default: data/cf_home.html)",
    )
    p.add_argument("--limit", type=int, default=15, help="How many rows to print as JSON")
    p.add_argument("--export-json", type=Path, default=None, help="Write all rows as JSON array")
    args = p.parse_args()

    if not args.html_path.is_file():
        print(f"Missing file: {args.html_path}", file=sys.stderr)
        sys.exit(2)

    html = args.html_path.read_text(encoding="utf-8", errors="replace")
    rows = parse_list_html(html)
    print(f"Parsed camp links: {len(rows)} (dedup by id)")
    for r in rows[: args.limit]:
        print(json.dumps({"id": r.id, "name": r.name, "url": r.url}, ensure_ascii=False))
    if args.export_json:
        payload = [
            {
                "id": r.id,
                "name": r.name,
                "url": r.url,
                "region_sido": r.region_sido,
                "region_sigungu": r.region_sigungu,
            }
            for r in rows
        ]
        args.export_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Exported {len(rows)} rows → {args.export_json}")


if __name__ == "__main__":
    main()
