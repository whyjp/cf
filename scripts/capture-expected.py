"""SP-D D-0: capture Python sentence-transformers ground-truth embeddings.

Loads poc/d0-onnx/samples/korean_50.json, runs SentenceTransformer encoding
(NOT normalized — raw float embeddings), saves to poc/d0-onnx/expected.json.

Usage:
  uv run --no-project --with sentence-transformers --with torch \
    python scripts/capture-expected.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sentence_transformers import SentenceTransformer

MODEL_NAME = "jhgan/ko-sroberta-multitask"
ROOT = Path(__file__).resolve().parent.parent
SAMPLES_PATH = ROOT / "poc" / "d0-onnx" / "samples" / "korean_50.json"
EXPECTED_PATH = ROOT / "poc" / "d0-onnx" / "expected.json"


def main() -> int:
    print(f"[capture] loading samples ← {SAMPLES_PATH}", flush=True)
    with SAMPLES_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    samples = data["samples"]
    if not samples:
        print("[capture] no samples found", file=sys.stderr)
        return 1

    print(f"[capture] loading model {MODEL_NAME}", flush=True)
    model = SentenceTransformer(MODEL_NAME)

    print(f"[capture] encoding {len(samples)} samples (normalize=False)", flush=True)
    embeddings = model.encode(
        samples,
        normalize_embeddings=False,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    out = {
        "model": MODEL_NAME,
        "normalize": False,
        "dim": int(embeddings.shape[1]),
        "samples": samples,
        "embeddings": [emb.astype(float).tolist() for emb in embeddings],
    }
    EXPECTED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EXPECTED_PATH.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    size_kb = EXPECTED_PATH.stat().st_size / 1024
    print(
        f"[capture] wrote {EXPECTED_PATH} (dim={out['dim']}, n={len(samples)}, {size_kb:.1f} KB)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
