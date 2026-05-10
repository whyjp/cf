# SP-D D-0: ONNX PoC — GATE Result

## Status

**GATE: PASS**

Date: 2026-05-10
Branch: `sprint/d0-onnx-poc`

## Configuration

| Component | Value |
|---|---|
| Model | `jhgan/ko-sroberta-multitask` |
| Architecture | RoBERTa (BERT-style WordPiece tokenizer) |
| Hidden dim | 768 |
| Max seq length | 128 (sentence-transformers default) |
| ONNX opset | 14 |
| ONNX exporter | `torch.onnx.export` (legacy TorchScript, `dynamo=False`) |
| Python deps | `transformers==4.45.2`, `torch==2.5.1`, `sentence-transformers==3.2.1`, `onnx`, `tokenizers` |
| Python | 3.12 (uv-managed, ephemeral env) |
| Tokenizer (Go) | `github.com/sugarme/tokenizer v0.2.2` (HF `tokenizer.json` fast format) |
| ONNX runtime (Go) | `github.com/yalue/onnxruntime_go v1.13.0` (CGo) |
| Native ORT lib | `onnxruntime.dll` v1.20.1 (Microsoft official Win64 release) |
| C compiler | mingw-w64 gcc 15.2.0 (MSYS2) |
| Go | 1.26.3 windows/amd64 |
| OS | Windows 11 Pro 26200 |

## Metrics

| Metric | Value | Threshold | Verdict |
|---|---|---|---|
| Cosine avg (n=50) | **1.000000** | ≥ 0.99 | PASS |
| Cosine min (n=50) | **1.000000** | ≥ 0.95 | PASS |

All 50 samples produced cosine similarity = 1.0 (rounded to 6 decimals) when
comparing Go ONNX-runtime mean-pooled embeddings against the Python
`SentenceTransformer.encode(..., normalize_embeddings=False)` reference.

Spot-check of raw float values (sample 0, "감악산 출렁다리 캠핑장", first 4 dims):

```
got [0.24985, -0.56629, -0.04542, -0.11380]   (Go + ONNX runtime)
want[0.24985, -0.56629, -0.04542, -0.11380]   (Python sentence-transformers)
```

Embeddings match to 5+ decimals — not a degenerate-zero coincidence.

## Decisions

### Tokenizer library: `github.com/sugarme/tokenizer v0.2.2`

**Why**: Pure Go (no cgo), loads HuggingFace fast `tokenizer.json` directly via
`pretrained.FromFile`. Matches the Python tokenizer output bit-for-bit when
combined with the special-tokens flag (`addSpecialTokens=true` → `[CLS] … [SEP]`).

**Caveat / fix path**: The library has a known panic in
`pretrained/padding.go:16` when `tokenizer.json` declares
`padding.strategy == "BatchLongest"` because it unconditionally casts a
non-existent `size` field to `float64`. We work around this by stripping the
`padding` and `truncation` sections from `tokenizer.json` at export time
(`scripts/export-ko-sroberta-onnx.py`) and applying our own truncation policy
(`MaxLength=128, LongestFirst`) via `tk.WithTruncation(...)` in Go. Padding is
unnecessary because we run sample-by-sample (batch=1) and the mean-pool is
mask-weighted regardless of padded tokens.

If we ever need batched inference in production, we'll either fork the lib for
the one-line fix or switch to `daulet/tokenizers` (Rust binding via cgo).

### ONNX runtime library: `github.com/yalue/onnxruntime_go v1.13.0`

**Why**: Cleanest Go binding for ONNX runtime, supports dynamic-shape sessions
(`NewDynamicAdvancedSession`), exposes typed `Tensor[T]` with direct access to
the underlying `[]float32` slice (zero-copy), and handles the Win64 runtime
loading via `SetSharedLibraryPath` + `InitializeEnvironment`.

Native ORT v1.20.1 DLL (downloaded from Microsoft's official release) is
loaded explicitly from the binary's working directory. Build requires CGO with
mingw-w64 (gcc) on Windows — confirmed working with MSYS2's gcc 15.2.0.

## D-1+ go/no-go

**GO**. The PoC demonstrates that Go can replicate Python sentence-transformers
embeddings to within numerical noise (cosine = 1.0). SP-D may proceed to D-1
(Go skeleton + chi + healthz + falkor smoke). The ML sidecar fallback spec is
**not** required.

## Reproduction

```bash
# 1) Export ONNX model + tokenizer (one time, ~423 MB onnx not committed)
cd D:/github/cf-go
$env:PYTHONIOENCODING="utf-8"
uv run --no-project --python 3.12 \
  --with "transformers==4.45.2" --with "torch==2.5.1" \
  --with onnx --with tokenizers \
  python scripts/export-ko-sroberta-onnx.py

# 2) Capture Python expected embeddings (committed: ~792 KB JSON)
uv run --no-project --python 3.12 \
  --with "sentence-transformers==3.2.1" --with "transformers==4.45.2" \
  --with "torch==2.5.1" \
  python scripts/capture-expected.py

# 3) Download ONNX runtime native lib (one time)
#    https://github.com/microsoft/onnxruntime/releases/download/v1.20.1/onnxruntime-win-x64-1.20.1.zip
#    Extract onnxruntime.dll into poc/d0-onnx/

# 4) Build + run gate
$env:PATH = "C:\Program Files\Go\bin;C:\msys64\mingw64\bin;$env:PATH"
$env:CGO_ENABLED = "1"
cd poc/d0-onnx
go build -o d0-poc.exe ./
./d0-poc.exe
```

## Files

- `scripts/export-ko-sroberta-onnx.py` — model + tokenizer export
- `scripts/capture-expected.py` — Python ground-truth embedding capture
- `poc/d0-onnx/main.go` — gate binary entry point
- `poc/d0-onnx/inference.go` — `runMeanPool(session, ids, mask) []float32`
- `poc/d0-onnx/go.mod`
- `poc/d0-onnx/samples/korean_50.json` — 50 hand-authored Korean test samples
- `poc/d0-onnx/expected.json` — Python reference embeddings (50×768 floats)
- `poc/d0-onnx/onnx_model/` — exported model (gitignored; ~423 MB)
- `poc/d0-onnx/tokenizer/` — exported tokenizer files (gitignored)
- `poc/d0-onnx/onnxruntime.dll` — native ORT lib (gitignored)
- `poc/d0-onnx/RESULT.md` — this file
- `poc/d0-onnx/RESULT.txt` — raw stdout from the gate run
