# SP-D be-api Go Rewrite + etago Absorption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Python `cf-be-api` 전체를 Go 로 재작성하고 `etago` Go 바이너리를 흡수해서 4 프로세스 (BFF + Python be-api + etago + Python ML) → 2 프로세스 (BFF + Go be-api) 로 단순화.

**Architecture:** Big bang cutover. D-0 ONNX PoC 게이트 (cosine ≥0.99) 통과 후 D-1~D-7 에서 Go be-api 를 별도 포트(:8073) 검증 모드로 빌드하고, D-8 에서 단일 PR 로 :8071 cutover + Python 흔적 제거. 작업은 `D:/github/cf-go` 워크트리 (`feature/sp-d-go-rewrite` 브랜치) 에서. spec/plan 문서는 main.

**Tech Stack:** Go 1.22+, chi router, pgx/v5 + pgxpool + pgvector-go, falkordb-go, yalue/onnxruntime_go, sugarme/tokenizer, kelseyhightower/envconfig, log/slog, stretchr/testify.

**Spec:** `docs/superpowers/specs/2026-05-10-sp-d-go-rewrite-design.md`

**Workflow:** 작은 commit, sprint = 1 PR, base=main. D-0~D-7 은 `gh pr merge --auto --merge` (저위험). **D-8 cutover PR 은 사용자 manual approval 필수** (Big bang 큰 변경). 브랜치명: `sprint/d<N>-<topic>` (워크트리 안에서 자체 브랜치 생성 또는 `feature/sp-d-go-rewrite` 위에 sprint 별 작은 commit + 단일 long-lived PR — D-8 결정).

---

## 워크트리 부팅 (D-0 시작 전 필수)

본 plan 의 모든 sprint 는 `D:/github/cf-go` 워크트리에서 실행한다. main worktree 에는 영향 없음.

```bash
# main worktree (D:/github/cf) — 한 번만 실행
cd D:/github/cf
git checkout main && git pull
git worktree add D:/github/cf-go -b feature/sp-d-go-rewrite

# 이후 모든 sprint:
cd D:/github/cf-go
# (작업)
```

**확인:** `git worktree list` 결과에 `D:/github/cf-go [feature/sp-d-go-rewrite]` 줄이 보여야.

각 sprint 는 `feature/sp-d-go-rewrite` 위에서 `sprint/d<N>-...` 별도 브랜치를 따고, sprint 별 PR base = `main` (워크트리 브랜치 자체는 main 에 머지 안 함, sprint 브랜치만 머지).

---

## Task D-0: ONNX PoC — ko-sroberta 임베딩 검증 (GATE)

**Goal:** ko-sroberta 모델을 ONNX export → Go onnxruntime + sentencepiece tokenizer 로 inference → Python sentence-transformers 결과와 cosine ≥ 0.99 일치 검증. 통과 시 D-1+ 진입. 실패 시 SP-D 중단 + ML sidecar 별도 spec.

**Files:**
- Create: `D:/github/cf-go/scripts/export-ko-sroberta-onnx.py` — Python script to export model
- Create: `D:/github/cf-go/poc/d0-onnx/go.mod`
- Create: `D:/github/cf-go/poc/d0-onnx/main.go` — Go inference + cosine compare
- Create: `D:/github/cf-go/poc/d0-onnx/samples/korean_50.json` — 50 한글 샘플
- Create: `D:/github/cf-go/poc/d0-onnx/expected.json` — Python 임베딩 결과 (768-dim float32 × 50)
- Create: `D:/github/cf-go/poc/d0-onnx/RESULT.md` — gate 결과 보고서

- [ ] **Step 1: Branch (워크트리 안에서)**

```bash
cd D:/github/cf-go
git checkout -b sprint/d0-onnx-poc
```

- [ ] **Step 2: Python ONNX export script**

`scripts/export-ko-sroberta-onnx.py`:

```python
"""Export jhgan/ko-sroberta-multitask to ONNX format.

Output: onnx_model/ko-sroberta.onnx + tokenizer/ (vocab + spiece.model)
"""
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModel

MODEL_ID = "jhgan/ko-sroberta-multitask"
OUT_DIR = Path("poc/d0-onnx/onnx_model")
TOK_DIR = Path("poc/d0-onnx/tokenizer")

OUT_DIR.mkdir(parents=True, exist_ok=True)
TOK_DIR.mkdir(parents=True, exist_ok=True)

print(f"Loading {MODEL_ID}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModel.from_pretrained(MODEL_ID)
model.eval()

# Save tokenizer artifacts (vocab.txt + spiece.model + tokenizer_config.json)
tokenizer.save_pretrained(TOK_DIR)
print(f"Tokenizer saved to {TOK_DIR}")

# Trace + export
sample = tokenizer("샘플 텍스트", return_tensors="pt", padding=True, truncation=True, max_length=128)
torch.onnx.export(
    model,
    args=(sample["input_ids"], sample["attention_mask"]),
    f=str(OUT_DIR / "ko-sroberta.onnx"),
    input_names=["input_ids", "attention_mask"],
    output_names=["last_hidden_state", "pooler_output"],
    dynamic_axes={
        "input_ids": {0: "batch", 1: "seq"},
        "attention_mask": {0: "batch", 1: "seq"},
        "last_hidden_state": {0: "batch", 1: "seq"},
        "pooler_output": {0: "batch"},
    },
    opset_version=14,
)
print(f"ONNX exported to {OUT_DIR}/ko-sroberta.onnx")
```

- [ ] **Step 3: 50 한글 샘플 + Python expected 캡처**

`poc/d0-onnx/samples/korean_50.json` (50 줄, 다양한 캠핑장 이름·설명·태그):

```json
[
  "강원도 평창 송어캠핑장",
  "오토캠핑 전용 가족 친화 글램핑",
  "계곡 옆 키즈 풀장 운영",
  "반려견 동반 가능 펜션 + 카라반",
  "해안 오션뷰 캠핑장",
  "...50개..."
]
```

`scripts/capture-expected.py`:

```python
"""Encode 50 samples with sentence-transformers, save 768-dim float32."""
import json
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL = SentenceTransformer("jhgan/ko-sroberta-multitask")
samples = json.loads(Path("poc/d0-onnx/samples/korean_50.json").read_text(encoding="utf-8"))
embs = MODEL.encode(samples, normalize_embeddings=False)   # raw, not normalized
out = {"samples": samples, "embeddings": embs.tolist()}
Path("poc/d0-onnx/expected.json").write_text(json.dumps(out), encoding="utf-8")
print(f"Captured {len(samples)} embeddings, dim={embs.shape[1]}")
```

```bash
cd D:/github/cf-go
uv run --no-project --with sentence-transformers --with torch python scripts/capture-expected.py 2>&1 | tail -3
```

기대: `Captured 50 embeddings, dim=768`.

- [ ] **Step 4: ONNX export 실행**

```bash
uv run --no-project --with transformers --with torch --with onnx python scripts/export-ko-sroberta-onnx.py 2>&1 | tail -5
ls poc/d0-onnx/onnx_model/ poc/d0-onnx/tokenizer/
```

기대: `ko-sroberta.onnx` (수백 MB), tokenizer 파일들.

- [ ] **Step 5: Go PoC 프로젝트 셋업**

`poc/d0-onnx/go.mod`:

```
module github.com/whyjp/cf/poc/d0-onnx

go 1.22

require (
	github.com/sugarme/tokenizer v0.2.2
	github.com/yalue/onnxruntime_go v1.13.0
)
```

```bash
cd poc/d0-onnx
go mod tidy 2>&1 | tail -5
```

- [ ] **Step 6: Go inference + cosine compare**

`poc/d0-onnx/main.go`:

```go
// PoC: load ONNX model + tokenizer, encode 50 samples, compare cosine to Python.
// Pass: cosine 평균 ≥ 0.99, min ≥ 0.95.
package main

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"

	"github.com/sugarme/tokenizer/pretrained"
	ort "github.com/yalue/onnxruntime_go"
)

type Expected struct {
	Samples    []string    `json:"samples"`
	Embeddings [][]float32 `json:"embeddings"`
}

func cosine(a, b []float32) float64 {
	if len(a) != len(b) {
		return 0
	}
	var dot, na, nb float64
	for i := range a {
		dot += float64(a[i]) * float64(b[i])
		na += float64(a[i]) * float64(a[i])
		nb += float64(b[i]) * float64(b[i])
	}
	if na == 0 || nb == 0 {
		return 0
	}
	return dot / (math.Sqrt(na) * math.Sqrt(nb))
}

func main() {
	// 1) load expected
	raw, err := os.ReadFile("expected.json")
	if err != nil {
		panic(err)
	}
	var exp Expected
	if err := json.Unmarshal(raw, &exp); err != nil {
		panic(err)
	}

	// 2) load tokenizer (HuggingFace tokenizer.json or sentencepiece)
	tok, err := pretrained.FromFile(filepath.Join("tokenizer", "tokenizer.json"))
	if err != nil {
		panic(fmt.Errorf("tokenizer load: %w", err))
	}

	// 3) init ONNX runtime
	ort.SetSharedLibraryPath("./onnxruntime.dll") // or .so on linux
	if err := ort.InitializeEnvironment(); err != nil {
		panic(err)
	}
	defer ort.DestroyEnvironment()

	session, err := ort.NewSession[int64](
		filepath.Join("onnx_model", "ko-sroberta.onnx"),
		[]string{"input_ids", "attention_mask"},
		[]string{"last_hidden_state", "pooler_output"},
	)
	if err != nil {
		panic(err)
	}
	defer session.Destroy()

	// 4) encode each sample, mean-pool over tokens (sentence-transformers default)
	cosines := make([]float64, len(exp.Samples))
	for i, s := range exp.Samples {
		enc, err := tok.EncodeSingle(s, true)
		if err != nil {
			panic(err)
		}
		ids := make([]int64, len(enc.Ids))
		mask := make([]int64, len(enc.Ids))
		for j := range enc.Ids {
			ids[j] = int64(enc.Ids[j])
			mask[j] = int64(enc.AttentionMask[j])
		}
		// run inference, mean-pool last_hidden_state weighted by mask
		emb := runMeanPool(session, ids, mask) // helper below — implement inline if simple
		cosines[i] = cosine(emb, exp.Embeddings[i])
	}

	// 5) report
	var sum, mn float64 = 0, 1
	for _, c := range cosines {
		sum += c
		if c < mn {
			mn = c
		}
	}
	avg := sum / float64(len(cosines))
	fmt.Printf("samples: %d\n", len(cosines))
	fmt.Printf("cosine avg: %.4f\n", avg)
	fmt.Printf("cosine min: %.4f\n", mn)
	pass := avg >= 0.99 && mn >= 0.95
	fmt.Printf("GATE: %s\n", map[bool]string{true: "PASS", false: "FAIL"}[pass])
	if !pass {
		os.Exit(1)
	}
}

// runMeanPool: TODO implement using ort.NewTensor + session.Run + mean over seq dim weighted by mask.
// Detail in poc/d0-onnx/inference.go (split for readability — see Step 7).
func runMeanPool(s *ort.AdvancedSession, ids, mask []int64) []float32 {
	panic("unimplemented — see Step 7")
}
```

- [ ] **Step 7: inference.go — runMeanPool 구현**

`poc/d0-onnx/inference.go`:

```go
package main

import ort "github.com/yalue/onnxruntime_go"

func runMeanPool(session *ort.AdvancedSession, ids, mask []int64) []float32 {
	seq := int64(len(ids))
	idsT, _ := ort.NewTensor(ort.NewShape(1, seq), ids)
	defer idsT.Destroy()
	maskT, _ := ort.NewTensor(ort.NewShape(1, seq), mask)
	defer maskT.Destroy()

	// allocate output: last_hidden_state [1, seq, 768]
	hidden, _ := ort.NewEmptyTensor[float32](ort.NewShape(1, seq, 768))
	defer hidden.Destroy()
	// pooler_output [1, 768] — discard
	pooler, _ := ort.NewEmptyTensor[float32](ort.NewShape(1, 768))
	defer pooler.Destroy()

	if err := session.Run(
		[]ort.Value{idsT, maskT},
		[]ort.Value{hidden, pooler},
	); err != nil {
		panic(err)
	}

	// mean-pool: sum hidden[0, t, :] * mask[t], divide by sum(mask)
	h := hidden.GetData()      // flat [seq*768]
	out := make([]float32, 768)
	var totalMask float32 = 0
	for t := int64(0); t < seq; t++ {
		m := float32(mask[t])
		totalMask += m
		for d := 0; d < 768; d++ {
			out[d] += h[t*768+int64(d)] * m
		}
	}
	if totalMask > 0 {
		for d := 0; d < 768; d++ {
			out[d] /= totalMask
		}
	}
	return out
}
```

- [ ] **Step 8: 실행 + 게이트 판정**

```bash
cd poc/d0-onnx
go build -o d0-poc ./
./d0-poc 2>&1 | tee RESULT.md
```

기대: `GATE: PASS`. 실패 시:

1. tokenizer 가 `tokenizer.json` 형식이 아닐 수 있음 — `tokenizer.save_pretrained` 가 만든 `spiece.model` 만 있다면, `daulet/tokenizers` (Rust binding) 로 fallback. Step 5 의 import 변경.
2. `yalue/onnxruntime_go` 가 onnxruntime native lib 동봉 안 함 — Microsoft onnxruntime release 에서 .so/.dll 다운로드 필요. `ort.SetSharedLibraryPath` 경로 조정.
3. cosine 미달 시: tokenizer max_length 차이 (Python 128 vs Go default), normalize_embeddings 차이 검증.

게이트 통과 시 RESULT.md 에 결과 commit.

- [ ] **Step 9: RESULT.md 작성**

```markdown
# Sprint D-0 ONNX PoC Result

**Date**: <YYYY-MM-DD>
**Status**: PASS | FAIL

## Configuration
- Model: jhgan/ko-sroberta-multitask
- ONNX opset: 14
- Tokenizer lib: sugarme/tokenizer | daulet/tokenizers
- ONNX runtime lib: yalue/onnxruntime_go | wasilibs/go-onnxruntime
- Native runtime: Microsoft onnxruntime <version>

## Metrics (50 Korean samples)
- Cosine avg: <X.XXXX>
- Cosine min: <X.XXXX>
- Gate (avg ≥ 0.99 + min ≥ 0.95): PASS | FAIL

## Decisions
- Tokenizer: <chosen lib + reason>
- ONNX runtime: <chosen lib + reason>

## D-1+ go/no-go
PASS → SP-D D-1 진입. FAIL → SP-D 중단, ML sidecar 별도 spec.
```

- [ ] **Step 10: Commit + push + PR**

```bash
cd D:/github/cf-go
git add poc/d0-onnx/ scripts/export-ko-sroberta-onnx.py scripts/capture-expected.py
git commit -m "feat(sp-d): D-0 ONNX PoC — ko-sroberta cosine gate

50 Korean samples, Python sentence-transformers vs Go ONNX runtime.
Gate: cosine avg ≥ 0.99 + min ≥ 0.95.
Tokenizer: <chosen>. ONNX runtime: <chosen>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/d0-onnx-poc
gh pr create --title "SP-D D-0: ONNX PoC (gate)" --body "$(cat <<'EOF'
## Summary
SP-D sprint D-0 — ONNX 정확도 게이트.

50 한글 샘플에 대해 Python sentence-transformers vs Go ONNX runtime cosine 비교.
Gate: avg ≥ 0.99, min ≥ 0.95.

PASS 시 D-1+ 진행. FAIL 시 SP-D 중단 + ML sidecar 재설계.

## Result
RESULT.md 참조.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr merge --auto --merge || gh pr merge --merge
```

⚠️ FAIL 시 PR 도 머지하지 말고 user 에게 보고 — SP-D 중단 결정.

---

## Task D-1: Go 워크스페이스 셋업 + chi + healthz + adapters smoke

**Goal:** `backend/be-api-go/` 신규 — Go module, chi router, healthz, settings (envconfig), logging (slog). FalkorDB Go client maturity smoke.

**Files:**
- Create: `D:/github/cf-go/backend/be-api-go/go.mod`
- Create: `D:/github/cf-go/backend/be-api-go/cmd/be-api/main.go`
- Create: `D:/github/cf-go/backend/be-api-go/internal/api/router.go`
- Create: `D:/github/cf-go/backend/be-api-go/internal/api/healthz.go`
- Create: `D:/github/cf-go/backend/be-api-go/internal/settings/config.go`
- Create: `D:/github/cf-go/backend/be-api-go/internal/api/healthz_test.go`
- Create: `D:/github/cf-go/backend/be-api-go/README.md`
- Create: `D:/github/cf-go/scripts/falkor-go-smoke.sh` (별도 smoke)

- [ ] **Step 1: Branch + 디렉터리 셋업**

```bash
cd D:/github/cf-go
git checkout feature/sp-d-go-rewrite
git pull origin main --rebase   # D-0 머지된 main 동기
git checkout -b sprint/d1-go-skeleton
mkdir -p backend/be-api-go/{cmd/be-api,internal/{api,settings},tests}
```

- [ ] **Step 2: go.mod**

`backend/be-api-go/go.mod`:

```
module github.com/whyjp/cf/be-api-go

go 1.22

require (
	github.com/go-chi/chi/v5 v5.1.0
	github.com/kelseyhightower/envconfig v1.4.0
	github.com/stretchr/testify v1.9.0
)
```

```bash
cd backend/be-api-go && go mod tidy
```

- [ ] **Step 3: settings/config.go**

```go
package settings

import "github.com/kelseyhightower/envconfig"

type Config struct {
	Host         string `envconfig:"BE_API_HOST" default:"127.0.0.1"`
	Port         int    `envconfig:"BE_API_PORT" default:"8073"` // D-1~D-7 검증 모드 포트, D-8 cutover 시 8071
	DatabaseURL  string `envconfig:"DATABASE_URL" default:"postgresql://camfit:camfit@localhost:5432/camfit"`
	FalkorDBURL  string `envconfig:"FALKORDB_URL" default:"redis://localhost:6379"`
	LogLevel     string `envconfig:"LOG_LEVEL" default:"info"`
}

func Load() (*Config, error) {
	var c Config
	if err := envconfig.Process("", &c); err != nil {
		return nil, err
	}
	return &c, nil
}
```

- [ ] **Step 4: api/router.go + healthz.go**

`internal/api/router.go`:

```go
package api

import (
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

func NewRouter() *chi.Mux {
	r := chi.NewRouter()
	r.Use(middleware.Recoverer)
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Get("/healthz", Healthz)
	return r
}
```

`internal/api/healthz.go`:

```go
package api

import (
	"encoding/json"
	"net/http"
)

type HealthzResponse struct {
	Status string `json:"status"`
}

func Healthz(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(HealthzResponse{Status: "ok"})
}
```

- [ ] **Step 5: cmd/be-api/main.go**

```go
package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/whyjp/cf/be-api-go/internal/api"
	"github.com/whyjp/cf/be-api-go/internal/settings"
)

func main() {
	cfg, err := settings.Load()
	if err != nil {
		slog.Error("config load", "err", err)
		os.Exit(1)
	}
	addr := cfg.Host + ":" + itoa(cfg.Port)
	srv := &http.Server{
		Addr:         addr,
		Handler:      api.NewRouter(),
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}
	go func() {
		slog.Info("be-api listening", "addr", addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("server", "err", err)
			os.Exit(1)
		}
	}()
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	srv.Shutdown(ctx)
}

func itoa(i int) string {
	return strconvItoa(i)
}

// avoid extra import for one func — see strconv inline use later
func strconvItoa(i int) string {
	// simple wrapper to keep import scope minimal in this file
	return fmt_Sprintf(i)
}

// placeholder — replace with strconv.Itoa in actual code
```

⚠️ 위 placeholder 정리: `import "strconv"` 추가 + `addr := cfg.Host + ":" + strconv.Itoa(cfg.Port)` 직접 사용. 위 itoa wrapper 코드 제거.

수정된 main.go:

```go
package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/whyjp/cf/be-api-go/internal/api"
	"github.com/whyjp/cf/be-api-go/internal/settings"
)

func main() {
	cfg, err := settings.Load()
	if err != nil {
		slog.Error("config load", "err", err)
		os.Exit(1)
	}
	addr := cfg.Host + ":" + strconv.Itoa(cfg.Port)
	srv := &http.Server{
		Addr:         addr,
		Handler:      api.NewRouter(),
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}
	go func() {
		slog.Info("be-api listening", "addr", addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("server", "err", err)
			os.Exit(1)
		}
	}()
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	srv.Shutdown(ctx)
}
```

- [ ] **Step 6: healthz_test.go**

```go
package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestHealthz(t *testing.T) {
	r := NewRouter()
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	var body HealthzResponse
	assert.NoError(t, json.Unmarshal(w.Body.Bytes(), &body))
	assert.Equal(t, "ok", body.Status)
}
```

- [ ] **Step 7: build + test + smoke**

```bash
cd D:/github/cf-go/backend/be-api-go
go build ./... 2>&1 | tail -3
go test ./... 2>&1 | tail -5
# Smoke
go run ./cmd/be-api &
sleep 2
curl -sf http://127.0.0.1:8073/healthz
kill %1
```

기대: build PASS, 1 test PASS, healthz returns `{"status":"ok"}`.

- [ ] **Step 8: FalkorDB Go client smoke**

`scripts/falkor-go-smoke.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p smoke/falkor-go && cd smoke/falkor-go

cat > go.mod <<'EOF'
module smoke/falkor-go

go 1.22

require github.com/FalkorDB/falkordb-go v0.1.0
EOF

cat > main.go <<'EOF'
package main

import (
	"fmt"
	"os"

	falkordb "github.com/FalkorDB/falkordb-go"
)

func main() {
	addr := os.Getenv("FALKORDB_HOST")
	if addr == "" {
		addr = "localhost:6379"
	}
	db, err := falkordb.FalkorDBNew(&falkordb.ConnectionOption{Addr: addr})
	if err != nil {
		fmt.Println("FAIL connect:", err)
		os.Exit(1)
	}
	graph := db.SelectGraph("camfit")
	res, err := graph.Query("MATCH (n) RETURN count(n) LIMIT 1")
	if err != nil {
		fmt.Println("FAIL query:", err)
		os.Exit(1)
	}
	fmt.Println("OK:", res)
}
EOF

go mod tidy 2>&1 | tail -3
go run main.go
```

```bash
chmod +x scripts/falkor-go-smoke.sh
./scripts/falkor-go-smoke.sh 2>&1 | tail -10
```

기대: `OK: ...`. **FAIL 시 falkor REST API 직접 wrapper 로 fallback 결정** — D-2 의 falkor adapter 가 raw HTTP/Redis 사용 (RESP protocol 직접).

- [ ] **Step 9: README.md**

`backend/be-api-go/README.md`:

```markdown
# cf be-api-go

Go rewrite of cf-be-api (Python). SP-D in progress.

## Run (D-1~D-7 verification mode, port 8073)

```sh
cd backend/be-api-go
go run ./cmd/be-api
```

## Test

```sh
go test ./...
```

## Architecture

`docs/superpowers/specs/2026-05-10-sp-d-go-rewrite-design.md`

## Status

- [x] D-1 skeleton + healthz
- [ ] D-2 domain + ports + adapters (postgres/falkor/source)
- [ ] D-3 embed (ONNX) + semantic_search
- [ ] D-4 read endpoints + camping_filter
- [ ] D-5 etago absorption + /eta*
- [ ] D-6 admin + graph
- [ ] D-7 integration + perf bench
- [ ] D-8 cutover (Big bang)
```

- [ ] **Step 10: Commit + PR**

```bash
cd D:/github/cf-go
git add backend/be-api-go/ scripts/falkor-go-smoke.sh
git commit -m "feat(sp-d): D-1 Go skeleton — chi + healthz + settings + falkor smoke

backend/be-api-go scaffold. chi router, /healthz, envconfig settings,
slog logging. FalkorDB Go client smoke result: <PASS|FAIL → fallback>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/d1-go-skeleton
gh pr create --title "SP-D D-1: Go skeleton" --body "..."
gh pr merge --auto --merge || gh pr merge --merge
```

---

## Task D-2: domain + ports + adapters (postgres + falkor + source)

**Goal:** Camp/FeaturedAxis/error structs (domain), CampReader/GraphReader/SourceReader interfaces (ports), pgx-based postgres adapter, falkordb-go (or REST fallback) adapter, JSONL replay source adapter. CampReader.ListCamps Go 결과 == Python 결과 (10 시나리오).

**Files (under `D:/github/cf-go/backend/be-api-go/`):**
- Create: `internal/domain/{models,errors,featured_axes,concept_seeds,camping_filter}.go`
- Create: `internal/ports/{repo,graph,embed,eta,geocode,source,vector}.go`
- Create: `internal/adapters/postgres/{pool,camp_repo,concept_repo,theme_repo,filter_repo,mark_repo}.go`
- Create: `internal/adapters/falkor/graph.go`
- Create: `internal/adapters/source/jsonl_replay.go`
- Create: `internal/adapters/postgres/camp_repo_test.go`
- Create: `tests/cross_validation/list_camps_test.go` (Python 동치 검증)

- [ ] **Step 1: Branch**

```bash
cd D:/github/cf-go
git checkout feature/sp-d-go-rewrite
git pull origin main --rebase
git checkout -b sprint/d2-domain-adapters
```

- [ ] **Step 2: go.mod 업데이트**

```bash
cd backend/be-api-go
go get github.com/jackc/pgx/v5 github.com/jackc/pgx/v5/pgxpool github.com/pgvector/pgvector-go
# falkor: PASS 시 falkordb-go, FAIL 시 stdlib + redigo
go get github.com/FalkorDB/falkordb-go || go get github.com/redis/go-redis/v9
go mod tidy
```

- [ ] **Step 3: domain/models.go (Camp struct)**

```go
package domain

import "time"

type Camp struct {
	ID          string                 `json:"id"`
	Name        string                 `json:"name"`
	Sido        *string                `json:"sido,omitempty"`
	Sigungu     *string                `json:"sigungu,omitempty"`
	Lat         *float64               `json:"lat,omitempty"`
	Lon         *float64               `json:"lon,omitempty"`
	Source      string                 `json:"source"`        // "camfit" | "txcp"
	Categories  []string               `json:"categories,omitempty"`
	LocationTypes []string             `json:"locationTypes,omitempty"`
	Collections []map[string]any       `json:"collections,omitempty"`
	Featured    map[string]bool        `json:"featured,omitempty"`
	Geo         *Geo                   `json:"geo,omitempty"`
	UpdatedAt   *time.Time             `json:"updated_at,omitempty"`
	Extra       map[string]any         `json:"-"`             // catch-all for projection
}

type Geo struct {
	Lat float64 `json:"lat"`
	Lon float64 `json:"lon"`
}

// Field tags 는 Python Pydantic 의 alias 와 정확히 일치해야 — D-4 fixture 비교에서 검출.
```

⚠️ Camp struct 의 정확한 fields 는 cf_be_api/domain/models.py 의 `class Camp` 에서 1:1 복사 (alias 포함). 위는 시드 — 실제 작업 시 Python source 보고 보강.

- [ ] **Step 4: domain/featured_axes.go**

Python `cf_be_api/domain/featured_axes.py` 의 `FEATURED_AXES` 리스트를 Go 슬라이스로:

```go
package domain

type FeaturedAxis struct {
	ID       string   `json:"id"`
	Ko       string   `json:"ko"`
	Icon     string   `json:"icon,omitempty"`
	Tone     string   `json:"tone,omitempty"`
	Keywords []string `json:"keywords,omitempty"`
}

var FEATURED_AXES = []FeaturedAxis{
	// ⚠️ 실제 작업 시 Python featured_axes.py 의 FEATURED_AXES 를 1:1 옮김.
	// 예시: {ID: "valley", Ko: "계곡", Icon: "🏞️", Tone: "moss", Keywords: []string{"계곡", "valley"}},
}
```

- [ ] **Step 5: domain/camping_filter.go (P6 포팅)**

```go
package domain

// CampingTokens — 캠핑 도메인 카테고리/타입 코드 (camfit + txcp)
var campingTokens = map[string]struct{}{
	"autoCamping": {}, "glamping": {}, "caravan": {}, "carCamping": {},
	"trailer": {}, "experience": {},
	"BB000": {}, "BB001": {}, "BB002": {}, "BB006": {},
}

// IsCampingFacility — Python is_camping_facility 와 동치.
// camp.Categories + camp.Collections 의 코드/이름에 캠핑 토큰 한 개 이상이면 true.
func IsCampingFacility(c *Camp) bool {
	if c == nil {
		return false
	}
	for _, cat := range c.Categories {
		if _, ok := campingTokens[cat]; ok {
			return true
		}
	}
	for _, lt := range c.LocationTypes {
		if _, ok := campingTokens[lt]; ok {
			return true
		}
	}
	for _, col := range c.Collections {
		if name, ok := col["name"].(string); ok {
			if _, ok := campingTokens[name]; ok {
				return true
			}
		}
	}
	return false
}
```

⚠️ 정확한 토큰 셋은 Python `cf_be_api/domain/camping_filter.py` 의 `CAMPING_TOKENS` 그대로 (P6 PR #30 참조).

- [ ] **Step 6: ports/repo.go**

```go
package ports

import (
	"context"
	"github.com/whyjp/cf/be-api-go/internal/domain"
)

type CampReader interface {
	ListCamps(ctx context.Context, opts ListCampsOptions) ([]*domain.Camp, error)
	GetCamp(ctx context.Context, id string) (*domain.Camp, error)
}

type ListCampsOptions struct {
	Region   *string
	Concepts []string
	Limit    int
}

type CampWriter interface {
	UpsertCamp(ctx context.Context, c *domain.Camp) error
}
```

다른 ports (graph.go / embed.go / eta.go / geocode.go / source.go / vector.go) 도 Python `cf_be_api/ports/*.py` 와 1:1 매핑하여 작성. ⚠️ 작업 시 각 파일 inspect 후 Go interface 로.

- [ ] **Step 7: adapters/postgres/pool.go + camp_repo.go**

`pool.go`:

```go
package postgres

import (
	"context"
	"github.com/jackc/pgx/v5/pgxpool"
)

func NewPool(ctx context.Context, dsn string) (*pgxpool.Pool, error) {
	return pgxpool.New(ctx, dsn)
}
```

`camp_repo.go`:

```go
package postgres

import (
	"context"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

type CampRepo struct {
	pool *pgxpool.Pool
}

func NewCampRepo(pool *pgxpool.Pool) *CampRepo {
	return &CampRepo{pool: pool}
}

func (r *CampRepo) ListCamps(ctx context.Context, opts ports.ListCampsOptions) ([]*domain.Camp, error) {
	// ⚠️ Python cf_be_api/adapters/postgres/camp_repo.py 의 list_camps SQL 과 동치 쿼리.
	// 컬럼 매핑은 Python 쿼리 SELECT 절을 1:1 복사 + pgx scan.
	// limit default 10000 (P5).
	limit := opts.Limit
	if limit == 0 {
		limit = 10000
	}
	// ... pseudocode — 실제 SQL 은 Python source 참조 후 작성
	rows, err := r.pool.Query(ctx, "SELECT ... FROM camps ... LIMIT $1", limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var camps []*domain.Camp
	for rows.Next() {
		c := &domain.Camp{}
		// scan into c.* fields
		camps = append(camps, c)
	}
	return camps, nil
}

func (r *CampRepo) GetCamp(ctx context.Context, id string) (*domain.Camp, error) {
	// ⚠️ Python get_site_detail 동치
	return nil, nil
}
```

⚠️ SQL 은 Python `cf_be_api/adapters/postgres/camp_repo.py` 의 `list_camps` / `get_camp` 메서드 본체에서 1:1 복사. region/concepts 필터링 SQL 도 동일.

- [ ] **Step 8: adapters/falkor/graph.go**

D-1 smoke 결과에 따라:
- **falkordb-go PASS**: 그 라이브러리 사용
- **FAIL**: stdlib + go-redis 로 RESP 프로토콜 직접 호출 (`GRAPH.QUERY camfit "MATCH (n) ..."`)

```go
package falkor

import (
	"context"
	// 결정에 따라 import
)

type GraphRepo struct {
	// client 필드
}

func NewGraphRepo(addr string) (*GraphRepo, error) {
	// init client
	return &GraphRepo{}, nil
}

func (g *GraphRepo) Query(ctx context.Context, cypher string) ([]map[string]any, error) {
	// ⚠️ Python cf_be_api/adapters/falkor/graph.py 의 query 메서드 동치
	return nil, nil
}
```

- [ ] **Step 9: adapters/source/jsonl_replay.go**

Python `cf_be_api/adapters/source/local_replay.py` 동치 — JSONL 파일 읽어서 Camp dict yield.

- [ ] **Step 10: cross-validation 테스트 (Python ↔ Go)**

`tests/cross_validation/list_camps_test.go`:

```go
//go:build cross
// +build cross

package cross_validation

import (
	"context"
	"encoding/json"
	"os/exec"
	"testing"
	"github.com/stretchr/testify/assert"
	// ... Go list_camps 호출
)

func TestListCamps_CrossValidate_GangwonValley(t *testing.T) {
	// Go side
	goResp := callGoBeApi("/sites?region=강원&concept=valley")
	// Python side (현 main 의 cf_be_api 로 호출)
	pyResp := callPythonBeApi("/sites?region=강원&concept=valley")
	// ID set 비교
	goIDs := extractIDs(goResp)
	pyIDs := extractIDs(pyResp)
	assert.Equal(t, sortStrings(pyIDs), sortStrings(goIDs))
}

func callGoBeApi(path string) []map[string]any {
	// HTTP GET to localhost:8073 (Go)
	return nil
}
func callPythonBeApi(path string) []map[string]any {
	// HTTP GET to localhost:8071 (Python — 현재 운영 그대로)
	return nil
}
// helpers...
```

```bash
# Go be-api on 8073
cd backend/be-api-go && DATABASE_URL=... FALKORDB_URL=... BE_API_PORT=8073 go run ./cmd/be-api &
GO_PID=$!
# Python be-api on 8071 (이미 운영 중)
sleep 2
go test -tags cross ./tests/cross_validation/... -v 2>&1 | tail -10
kill $GO_PID
```

기대: 10 시나리오 모두 PASS — region+concept 조합 별로 ID 셋 일치.

- [ ] **Step 11: Commit + PR**

```bash
cd D:/github/cf-go
git add backend/be-api-go/internal/ backend/be-api-go/tests/
git commit -m "feat(sp-d): D-2 domain + ports + postgres/falkor/source adapters

CampReader.ListCamps cross-validates against Python (10 scenarios).
FalkorDB Go client decision: <falkordb-go | go-redis RESP fallback>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/d2-domain-adapters
gh pr create --title "SP-D D-2: domain + ports + adapters" --body "..."
gh pr merge --auto --merge || gh pr merge --merge
```

---

## Task D-3: embed (ONNX) + semantic_search 엔드포인트

**Goal:** D-0 의 ONNX 코드를 `internal/adapters/embed/` 로 흡수. semantic_search use case + handlers `/sites/search`, `/sites/{id}/similar`. Python top-10 일치율 ≥ 0.95.

**Files:**
- Create: `internal/adapters/embed/{onnx_model,tokenizer}.go`
- Create: `internal/usecases/semantic_search.go`
- Create: `internal/api/sites_search.go`
- Create: `internal/adapters/embed/onnx_model_test.go`
- Create: `tests/cross_validation/sites_search_test.go`

- [ ] **Step 1: Branch**

```bash
cd D:/github/cf-go && git checkout feature/sp-d-go-rewrite && git pull origin main --rebase
git checkout -b sprint/d3-embed-search
```

- [ ] **Step 2: D-0 PoC 코드 → adapters/embed/ 이전**

`poc/d0-onnx/main.go` + `inference.go` → `backend/be-api-go/internal/adapters/embed/{onnx_model,tokenizer}.go` 로 분할 + 인터페이스 적용:

```go
package embed

import (
	"context"
	ort "github.com/yalue/onnxruntime_go"
	"github.com/sugarme/tokenizer"
)

type OnnxEmbedder struct {
	session *ort.AdvancedSession
	tok     *tokenizer.Tokenizer
}

func NewOnnxEmbedder(modelPath, tokPath string) (*OnnxEmbedder, error) {
	// init runtime + load model + load tokenizer
	return &OnnxEmbedder{}, nil
}

func (e *OnnxEmbedder) Encode(ctx context.Context, text string) ([]float32, error) {
	// runMeanPool from D-0 PoC
	return nil, nil
}

func (e *OnnxEmbedder) Close() error {
	return e.session.Destroy()
}
```

`internal/ports/embed.go`:

```go
package ports

import "context"

type Embedder interface {
	Encode(ctx context.Context, text string) ([]float32, error)
	Close() error
}
```

- [ ] **Step 3: usecases/semantic_search.go**

```go
package usecases

import (
	"context"
	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

type SemanticSearch struct {
	embed  ports.Embedder
	vector ports.VectorIndex // pgvector adapter
	camp   ports.CampReader
}

func NewSemanticSearch(e ports.Embedder, v ports.VectorIndex, c ports.CampReader) *SemanticSearch {
	return &SemanticSearch{embed: e, vector: v, camp: c}
}

func (s *SemanticSearch) Search(ctx context.Context, q string, k int) ([]*domain.Camp, error) {
	// 1) embed q
	emb, err := s.embed.Encode(ctx, q)
	if err != nil {
		return nil, err
	}
	// 2) vector knn (pgvector)
	hits, err := s.vector.SearchByEmbedding(ctx, emb, k)
	if err != nil {
		return nil, err
	}
	// 3) hydrate Camp by IDs
	// ... batch load via CampReader
	return nil, nil
}

func (s *SemanticSearch) Similar(ctx context.Context, siteID string, k int) ([]*domain.Camp, error) {
	// fetch camp's existing embedding (or re-embed name/desc), then knn
	return nil, nil
}
```

- [ ] **Step 4: adapters/pgvector/search.go**

Python `cf_be_api/adapters/pgvector/search.py` 동치 — pgvector `<-> ` 연산자로 cosine search.

```go
package pgvector

import (
	"context"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/pgvector/pgvector-go"
)

type Index struct {
	pool *pgxpool.Pool
}

func (i *Index) SearchByEmbedding(ctx context.Context, emb []float32, k int) ([]string, error) {
	v := pgvector.NewVector(emb)
	rows, err := i.pool.Query(ctx,
		"SELECT camp_id FROM camp_embeddings ORDER BY embedding <-> $1 LIMIT $2",
		v, k)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var ids []string
	for rows.Next() {
		var id string
		rows.Scan(&id)
		ids = append(ids, id)
	}
	return ids, nil
}
```

- [ ] **Step 5: api/sites_search.go**

```go
package api

import (
	"encoding/json"
	"net/http"
	"strconv"
	"github.com/go-chi/chi/v5"
)

func (h *Handlers) SiteSearch(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("q")
	if q == "" {
		http.Error(w, "missing q", http.StatusBadRequest)
		return
	}
	k := 20
	if ks := r.URL.Query().Get("k"); ks != "" {
		if v, err := strconv.Atoi(ks); err == nil {
			k = v
		}
	}
	camps, err := h.semantic.Search(r.Context(), q, k)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(camps)
}

func (h *Handlers) SiteSimilar(w http.ResponseWriter, r *http.Request) {
	siteID := chi.URLParam(r, "site_id")
	k := 10
	if ks := r.URL.Query().Get("k"); ks != "" {
		if v, err := strconv.Atoi(ks); err == nil {
			k = v
		}
	}
	camps, err := h.semantic.Similar(r.Context(), siteID, k)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(camps)
}
```

router 등록:

```go
r.Route("/sites", func(r chi.Router) {
    r.Get("/search", h.SiteSearch)
    r.Get("/{site_id}/similar", h.SiteSimilar)
    // 다음 Sprint 에서 /sites, /sites/{id}, ...
})
```

- [ ] **Step 6: cross-validation 테스트**

`tests/cross_validation/sites_search_test.go`:

```go
//go:build cross
package cross_validation

import (
	"sort"
	"testing"
	"github.com/stretchr/testify/assert"
)

func TestSiteSearch_CrossValidate(t *testing.T) {
	queries := []string{"강원", "오토캠핑", "계곡 옆", "키즈", "글램핑"}
	for _, q := range queries {
		t.Run(q, func(t *testing.T) {
			goIDs := extractIDs(callGoBeApi("/sites/search?q=" + q + "&k=10"))
			pyIDs := extractIDs(callPythonBeApi("/sites/search?q=" + q + "&k=10"))
			// top-10 일치율 ≥ 0.95
			overlap := overlapPct(goIDs, pyIDs)
			assert.GreaterOrEqual(t, overlap, 0.95, "query: %s", q)
		})
	}
}

func overlapPct(a, b []string) float64 {
	set := map[string]bool{}
	for _, x := range a {
		set[x] = true
	}
	hit := 0
	for _, x := range b {
		if set[x] {
			hit++
		}
	}
	return float64(hit) / float64(len(b))
}
```

- [ ] **Step 7: build + test + smoke**

```bash
cd backend/be-api-go && go build ./... && go test ./...
# 포트 8073 부팅
DATABASE_URL=... FALKORDB_URL=... BE_API_PORT=8073 ./be-api &
sleep 3
curl -sf "http://127.0.0.1:8073/sites/search?q=강원&k=10" | head -c 300
go test -tags cross ./tests/cross_validation/... -v
kill %1
```

기대: 5 query 모두 overlap ≥ 0.95.

- [ ] **Step 8: Commit + PR**

```bash
git add backend/be-api-go/
git commit -m "feat(sp-d): D-3 embed (ONNX) + semantic_search

OnnxEmbedder + pgvector knn + SemanticSearch use case.
/sites/search, /sites/{id}/similar handlers.
Cross-validation vs Python: top-10 overlap ≥ 0.95.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/d3-embed-search
gh pr create --title "SP-D D-3: embed + semantic search" --body "..."
gh pr merge --auto --merge || gh pr merge --merge
```

---

## Task D-4: 사용자-읽기 엔드포인트 일괄 + camping_filter 포팅

**Goal:** Python /sites, /sites/{id}, /facets, /concepts*, /themes*, /marks*, /featured-axes 모두 Go 포팅. P6 camping_filter 적용. 응답 byte-수준 동일 (regression fixtures).

**Files:**
- Create: `internal/usecases/{list_camps,get_site_detail,list_facets,list_concepts,list_themes,list_marks}.go`
- Create: `internal/api/{sites,facets,concepts,themes,marks,featured_axes}.go`
- Create: `internal/adapters/postgres/{concept_repo,theme_repo,filter_repo,mark_repo}.go`
- Create: `tests/regression/{sites,facets,...}_test.go` — fixture 비교

- [ ] **Step 1: Branch**

```bash
cd D:/github/cf-go && git checkout feature/sp-d-go-rewrite && git pull origin main --rebase
git checkout -b sprint/d4-read-endpoints
```

- [ ] **Step 2: 각 use case + handler 1:1 포팅**

각 엔드포인트 마다 동일 패턴 (Python source 참조 → Go 작성 → fixture 비교):

| Python source | Go target |
|---|---|
| `cf_be_api/api.py:sites()` (~line 137) | `internal/api/sites.go:Sites` + `internal/usecases/list_camps.go` |
| `cf_be_api/api.py:site_detail()` (~115) | `internal/api/sites.go:SiteDetail` + `usecases/get_site_detail.go` |
| `cf_be_api/api.py:facets()` (~335) | `internal/api/facets.go:Facets` + `usecases/list_facets.go` |
| `cf_be_api/api.py:concepts()` (~378) | `internal/api/concepts.go:Concepts` |
| `cf_be_api/api.py:concept_camps()` (~383) | `internal/api/concepts.go:ConceptCamps` |
| `cf_be_api/api.py:themes()` (~391) | `internal/api/themes.go:Themes` |
| `cf_be_api/api.py:theme_camps()` (~399) | `internal/api/themes.go:ThemeCamps` |
| `cf_be_api/api.py:list_marks()` (~412) | `internal/api/marks.go:Marks` |
| `cf_be_api/api.py:axis_camps()` (~424) | `internal/api/marks.go:AxisCamps` |
| `cf_be_api/api.py:featured_axes()` (~317) | `internal/api/featured_axes.go:FeaturedAxes` |

각각:
1. Python 함수 본체 읽고 SQL/로직 파악
2. Go usecase + handler 작성 (CampReader/repo 호출)
3. router 등록
4. fixture 회귀 테스트 작성

`internal/usecases/list_camps.go`:

```go
package usecases

import (
	"context"
	"github.com/whyjp/cf/be-api-go/internal/domain"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

type ListCamps struct {
	repo ports.CampReader
}

func NewListCamps(r ports.CampReader) *ListCamps {
	return &ListCamps{repo: r}
}

func (uc *ListCamps) Execute(ctx context.Context, opts ports.ListCampsOptions) ([]*domain.Camp, error) {
	camps, err := uc.repo.ListCamps(ctx, opts)
	if err != nil {
		return nil, err
	}
	// P6 camping filter
	filtered := make([]*domain.Camp, 0, len(camps))
	for _, c := range camps {
		if domain.IsCampingFacility(c) {
			filtered = append(filtered, c)
		}
	}
	return filtered, nil
}
```

`internal/api/sites.go`:

```go
package api

import (
	"encoding/json"
	"net/http"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

func (h *Handlers) Sites(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	opts := ports.ListCampsOptions{Limit: 10000}
	if region := q.Get("region"); region != "" {
		opts.Region = &region
	}
	for _, c := range q["concept"] {
		opts.Concepts = append(opts.Concepts, c)
	}
	camps, err := h.listCamps.Execute(r.Context(), opts)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(camps)
}
```

(다른 핸들러도 동일 패턴 — Python 동치 SQL/로직 그대로.)

- [ ] **Step 3: regression fixture 비교 테스트**

`tests/regression/sites_test.go`:

```go
//go:build regression
package regression

import (
	"encoding/json"
	"io/ioutil"
	"net/http"
	"os"
	"sort"
	"testing"
	"github.com/stretchr/testify/assert"
)

func normalize(d any) string {
	b, _ := json.Marshal(d)
	var v any
	json.Unmarshal(b, &v)
	out, _ := json.Marshal(sortKeys(v))
	return string(out)
}

func sortKeys(v any) any {
	switch x := v.(type) {
	case map[string]any:
		out := make(map[string]any)
		keys := make([]string, 0, len(x))
		for k := range x {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			out[k] = sortKeys(x[k])
		}
		return out
	case []any:
		out := make([]any, len(x))
		for i, item := range x {
			out[i] = sortKeys(item)
		}
		return out
	}
	return v
}

func TestSites_RegressionFixtures(t *testing.T) {
	if os.Getenv("RUN_REGRESSION") != "1" {
		t.Skip("RUN_REGRESSION=1 required")
	}
	// 사전: Go be-api 부팅 (8073). PG/falkor 라이브 환경.
	cases := []struct {
		fixture string
		url     string
	}{
		{"after_p6_sites_gangwon.json", "http://127.0.0.1:8073/sites?region=강원"},
		{"after_p6_sites_valley.json", "http://127.0.0.1:8073/sites?concept=valley"},
		// ... 기타
	}
	for _, c := range cases {
		t.Run(c.fixture, func(t *testing.T) {
			resp, _ := http.Get(c.url)
			defer resp.Body.Close()
			body, _ := ioutil.ReadAll(resp.Body)
			var actual any
			json.Unmarshal(body, &actual)

			fb, _ := os.ReadFile("fixtures/" + c.fixture)
			var expected any
			json.Unmarshal(fb, &expected)

			assert.Equal(t, normalize(expected), normalize(actual))
		})
	}
}
```

⚠️ A3 fixture (PR #11) 는 P6 (PR #30) 이후 invalidated. D-4 시작 시 새 fixture 캡처 필요:

```bash
# main worktree, Python be-api 부팅 상태에서
cd D:/github/cf
mkdir -p backend/be-for-fe/tests/fixtures/regression-d4
curl -s "http://localhost:8070/sites?region=강원" > backend/be-for-fe/tests/fixtures/regression-d4/after_p6_sites_gangwon.json
# 등등 — D-4 시작 직전 sprint 별 시작 단계로 캡처
```

이 fixture 를 `D:/github/cf-go/backend/be-api-go/tests/regression/fixtures/` 로 복사 후 비교.

- [ ] **Step 4: 모든 엔드포인트 build + test + smoke**

```bash
cd backend/be-api-go && go build ./... && go test ./...
# 부팅 후
RUN_REGRESSION=1 go test -tags regression ./tests/regression/... -v
```

기대: 모든 엔드포인트 fixture 와 byte-equal.

- [ ] **Step 5: Commit + PR**

```bash
git add backend/be-api-go/
git commit -m "feat(sp-d): D-4 read endpoints + camping_filter

/sites /sites/{id} /facets /concepts* /themes* /marks* /featured-axes.
P6 camping_filter applied. Regression fixtures byte-equal vs Python.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push -u origin sprint/d4-read-endpoints
gh pr create ... && gh pr merge --auto --merge
```

---

## Task D-5: etago 흡수 + /eta* 엔드포인트

**Goal:** `etago/internal/{route,parse,duration}/*.go` 를 `backend/be-api-go/internal/adapters/{eta,geocode}/` 로 이전. 기존 etago Go 테스트 동반 마이그레이션. /eta, /eta/batch, /eta/cache 핸들러 + use case eta_for_fleet.

**Files:**
- Move: `etago/internal/route/kakao*.go` → `backend/be-api-go/internal/adapters/geocode/kakao*.go`
- Move: `etago/internal/route/{naver,osrm,provider,route}*.go` → `backend/be-api-go/internal/adapters/eta/`
- Move: `etago/internal/parse/*.go` → split between adapters/{eta,geocode}/parse*.go
- Move: `etago/internal/duration/*.go` → adapters/eta/duration*.go
- Drop: `etago/cmd/etago/*` + `etago/internal/envfile/*` (envconfig 통합)
- Create: `internal/usecases/eta_for_fleet.go`
- Create: `internal/api/eta.go`

- [ ] **Step 1: Branch**

```bash
cd D:/github/cf-go && git checkout feature/sp-d-go-rewrite && git pull origin main --rebase
git checkout -b sprint/d5-etago-absorption
```

- [ ] **Step 2: etago 코드 이전**

```bash
mkdir -p backend/be-api-go/internal/adapters/{eta,geocode}

# kakao geocoding
git mv etago/internal/route/kakao.go backend/be-api-go/internal/adapters/geocode/kakao.go
git mv etago/internal/route/kakao_test.go backend/be-api-go/internal/adapters/geocode/kakao_test.go

# naver/osrm/provider/route ETA
git mv etago/internal/route/naver.go backend/be-api-go/internal/adapters/eta/naver.go
git mv etago/internal/route/naver_test.go backend/be-api-go/internal/adapters/eta/naver_test.go
git mv etago/internal/route/naver_ncp_test.go backend/be-api-go/internal/adapters/eta/naver_ncp_test.go
git mv etago/internal/route/osrm.go backend/be-api-go/internal/adapters/eta/osrm.go
git mv etago/internal/route/osrm_test.go backend/be-api-go/internal/adapters/eta/osrm_test.go
git mv etago/internal/route/provider.go backend/be-api-go/internal/adapters/eta/provider.go
git mv etago/internal/route/route.go backend/be-api-go/internal/adapters/eta/route.go
git mv etago/internal/route/route_test.go backend/be-api-go/internal/adapters/eta/route_test.go

# parse + duration
git mv etago/internal/parse/ backend/be-api-go/internal/adapters/eta/parse/
# (kakao 관련 parse 가 있다면 split — Step 3에서 정리)
git mv etago/internal/duration/ backend/be-api-go/internal/adapters/eta/duration/

# 제거
git rm -r etago/cmd etago/internal/envfile
```

- [ ] **Step 3: import path rewrite**

```bash
cd backend/be-api-go
# package 이름 + import 경로
find internal/adapters/eta internal/adapters/geocode -name "*.go" -exec \
  sed -i 's|github.com/whyjp/etago/internal/route|github.com/whyjp/cf/be-api-go/internal/adapters/eta|g' {} +
find internal/adapters/eta internal/adapters/geocode -name "*.go" -exec \
  sed -i 's|github.com/whyjp/etago/internal/parse|github.com/whyjp/cf/be-api-go/internal/adapters/eta/parse|g' {} +
find internal/adapters/eta internal/adapters/geocode -name "*.go" -exec \
  sed -i 's|github.com/whyjp/etago/internal/duration|github.com/whyjp/cf/be-api-go/internal/adapters/eta/duration|g' {} +
# package 이름: route → eta or geocode
find internal/adapters/eta -name "*.go" -exec sed -i 's|^package route$|package eta|g' {} +
find internal/adapters/geocode -name "*.go" -exec sed -i 's|^package route$|package geocode|g' {} +
```

- [ ] **Step 4: envfile → envconfig 흡수**

기존 etago 의 `envfile.Load` 호출을 `settings.Load()` 로 대체:

```bash
grep -rn "envfile" backend/be-api-go/internal/adapters/
```

각 호출을 `cfg.NaverNCPClientID` / `cfg.NaverNCPClientSecret` / `cfg.KakaoRESTKey` 로 변경. settings/config.go 에 필드 추가:

```go
type Config struct {
	// ... 기존
	NaverNCPClientID     string `envconfig:"NAVER_NCP_CLIENT_ID"`
	NaverNCPClientSecret string `envconfig:"NAVER_NCP_CLIENT_SECRET"`
	KakaoRESTKey         string `envconfig:"KAKAO_REST_KEY"`
}
```

- [ ] **Step 5: 기존 etago 테스트 통과 확인**

```bash
cd backend/be-api-go
go build ./... 2>&1 | tail -10
go test ./internal/adapters/eta/... ./internal/adapters/geocode/... -v 2>&1 | tail -20
```

기대: 기존 etago 테스트 (kakao_test, naver_test, osrm_test, route_test, naver_ncp_test) 100% PASS.

- [ ] **Step 6: usecase + ports 정리**

`internal/ports/eta.go`:

```go
package ports

import "context"

type EtaProvider interface {
	Estimate(ctx context.Context, originLat, originLon, destLat, destLon float64) (minutes int, err error)
	EstimateBatch(ctx context.Context, originLat, originLon float64, dests []DestPoint) (map[string]int, error)
}

type DestPoint struct {
	ID  string
	Lat float64
	Lon float64
}

type GeocodeProvider interface {
	Geocode(ctx context.Context, placeName string) (lat, lon float64, err error)
}
```

`internal/usecases/eta_for_fleet.go`:

```go
package usecases

import (
	"context"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

type EtaForFleet struct {
	eta     ports.EtaProvider
	geocode ports.GeocodeProvider
}

func NewEtaForFleet(e ports.EtaProvider, g ports.GeocodeProvider) *EtaForFleet {
	return &EtaForFleet{eta: e, geocode: g}
}

func (uc *EtaForFleet) Batch(ctx context.Context, origin string, dests []ports.DestPoint, maxMinutes *int) (map[string]EtaResult, error) {
	// 1) geocode origin (place name → lat/lon)
	oLat, oLon, err := uc.geocode.Geocode(ctx, origin)
	if err != nil {
		return nil, err
	}
	// 2) batch eta
	results, err := uc.eta.EstimateBatch(ctx, oLat, oLon, dests)
	if err != nil {
		return nil, err
	}
	// 3) max_minutes filter (within flag)
	out := map[string]EtaResult{}
	for id, m := range results {
		within := true
		if maxMinutes != nil && m > *maxMinutes {
			within = false
		}
		out[id] = EtaResult{Minutes: m, Within: within}
	}
	return out, nil
}

type EtaResult struct {
	Minutes int  `json:"minutes"`
	Within  bool `json:"within"`
}
```

- [ ] **Step 7: api/eta.go**

```go
package api

import (
	"encoding/json"
	"net/http"
	"strconv"
	"github.com/whyjp/cf/be-api-go/internal/ports"
)

type EtaBatchRequest struct {
	Origin     string             `json:"origin"`
	IDs        []string           `json:"ids"`
	MaxMinutes *int               `json:"max_minutes,omitempty"`
	Concurrency int                `json:"concurrency"`
	TimeoutS    int                `json:"timeout_s"`
}

func (h *Handlers) Eta(w http.ResponseWriter, r *http.Request) {
	// GET /eta?origin_lat=...&origin_lon=...&dest_lat=...&dest_lon=...
	originLat, _ := strconv.ParseFloat(r.URL.Query().Get("origin_lat"), 64)
	originLon, _ := strconv.ParseFloat(r.URL.Query().Get("origin_lon"), 64)
	destLat, _ := strconv.ParseFloat(r.URL.Query().Get("dest_lat"), 64)
	destLon, _ := strconv.ParseFloat(r.URL.Query().Get("dest_lon"), 64)
	m, err := h.eta.Estimate(r.Context(), originLat, originLon, destLat, destLon)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(map[string]any{"minutes": m})
}

func (h *Handlers) EtaBatch(w http.ResponseWriter, r *http.Request) {
	var req EtaBatchRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	// dests resolved from req.IDs via CampReader
	dests := make([]ports.DestPoint, 0, len(req.IDs))
	for _, id := range req.IDs {
		c, err := h.campReader.GetCamp(r.Context(), id)
		if err != nil || c == nil || c.Lat == nil || c.Lon == nil {
			continue
		}
		dests = append(dests, ports.DestPoint{ID: id, Lat: *c.Lat, Lon: *c.Lon})
	}
	results, err := h.etaForFleet.Batch(r.Context(), req.Origin, dests, req.MaxMinutes)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(map[string]any{"results": results})
}

func (h *Handlers) EtaCacheClear(w http.ResponseWriter, r *http.Request) {
	// 캐시 (Redis 등) 초기화
	json.NewEncoder(w).Encode(map[string]int{"cleared": 0})
}
```

router:

```go
r.Route("/eta", func(r chi.Router) {
    r.Get("/", h.Eta)
    r.Post("/batch", h.EtaBatch)
    r.Delete("/cache", h.EtaCacheClear)
})
```

- [ ] **Step 8: Cross-validation 테스트**

```bash
# Python /eta/batch 결과 캡처 (현 main 운영 상태)
curl -s -X POST "http://localhost:8070/eta/batch" \
  -H "Content-Type: application/json" \
  -d '{"origin":"강남역","ids":["camp1","camp2"],"max_minutes":120,"concurrency":4,"timeout_s":12}' \
  > /tmp/py_eta_batch.json

# Go (포트 8073)
curl -s -X POST "http://127.0.0.1:8073/eta/batch" \
  -H "Content-Type: application/json" \
  -d '{...}' > /tmp/go_eta_batch.json

# 비교 — minutes 가 ±1분 이내 일치 (etago 내부 호출이 실시간 트래픽이라 약간 변동)
python3 -c "
import json
py = json.load(open('/tmp/py_eta_batch.json'))['results']
go = json.load(open('/tmp/go_eta_batch.json'))['results']
for k in py:
    diff = abs(py[k]['minutes'] - go[k]['minutes'])
    assert diff <= 1, f'{k}: diff={diff}'
print('PASS')
"
```

- [ ] **Step 9: Commit + PR**

```bash
git add -A
git commit -m "feat(sp-d): D-5 etago absorption + /eta* endpoints

etago/internal/{route,parse,duration} → backend/be-api-go/internal/adapters/{eta,geocode}.
envfile → envconfig. CLI removed.
/eta /eta/batch /eta/cache handlers + eta_for_fleet usecase.
Cross-validation: minutes ±1 vs Python.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push -u origin sprint/d5-etago-absorption
gh pr create ... && gh pr merge --auto --merge
```

---

## Task D-6: 어드민 + 그래프 엔드포인트

**Goal:** /admin/rebuild-graph, /admin/reembed, /graph/schema, /graph/sample, /graph/expand, /graph/search 포팅. graph.html 어드민 페이지 정상 작동.

**Files:**
- Create: `internal/api/{admin,graph}.go`
- Create: `internal/usecases/{rebuild_graph,reembed,graph_query}.go`

- [ ] **Step 1: Branch**

```bash
cd D:/github/cf-go && git checkout feature/sp-d-go-rewrite && git pull origin main --rebase
git checkout -b sprint/d6-admin-graph
```

- [ ] **Step 2: 6 엔드포인트 1:1 포팅**

각각 Python `cf_be_api/api.py` 에서 대응 함수 (line ~471 admin, ~553/644/820/936 graph) 본체를 Go 로 옮김. Falkor 쿼리 (Cypher-like) 는 GraphRepo.Query 호출.

`internal/api/admin.go`:

```go
package api

import (
	"encoding/json"
	"net/http"
)

func (h *Handlers) AdminRebuildGraph(w http.ResponseWriter, r *http.Request) {
	if err := h.rebuildGraph.Execute(r.Context()); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func (h *Handlers) AdminReembed(w http.ResponseWriter, r *http.Request) {
	if err := h.reembed.Execute(r.Context()); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}
```

`internal/api/graph.go` — graph_schema, graph_sample, graph_expand, graph_search. ⚠️ 본체 길이 (Python 200+ lines) 가 큰 부분 — Python source 1:1 포팅, helper 분리 권장.

- [ ] **Step 3: graph.html 어드민 검증**

```bash
# Go be-api on 8073
DATABASE_URL=... FALKORDB_URL=... BE_API_PORT=8073 ./be-api &
sleep 2
# graph.html ?api=http://127.0.0.1:8073 로 호출
curl -sf "http://127.0.0.1:8073/graph/schema" | head -c 300
curl -sf "http://127.0.0.1:8073/graph/sample?label=Camp&limit=5" | head -c 300
kill %1
```

수동: 브라우저에서 fe/dist/graph.html 를 file:// 로 열고 ?api=http://127.0.0.1:8073 로 어드민 작동 확인.

- [ ] **Step 4: Commit + PR**

```bash
git add backend/be-api-go/
git commit -m "feat(sp-d): D-6 admin + graph endpoints

/admin/rebuild-graph /admin/reembed /graph/schema /graph/sample
/graph/expand /graph/search. graph.html 어드민 정상.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push -u origin sprint/d6-admin-graph
gh pr create ... && gh pr merge --auto --merge
```

---

## Task D-7: 통합 + 성능 벤치

**Goal:** Python be-api (잠시 :8074) vs Go be-api (:8073) cross-validate 풀 시나리오. ETA batch 1000건, embedding 100건, sites 풀 fetch latency 비교 → `docs/sp-d-performance-baseline.md`. Go ≥ Python 모든 워크로드.

**Files:**
- Create: `D:/github/cf-go/scripts/perf-bench.sh`
- Create: `D:/github/cf-go/docs/sp-d-performance-baseline.md`

- [ ] **Step 1: Branch**

```bash
cd D:/github/cf-go && git checkout feature/sp-d-go-rewrite && git pull origin main --rebase
git checkout -b sprint/d7-integration-perf
```

- [ ] **Step 2: 두 서비스 동시 부팅**

```bash
# Python be-api on 8074 (BACKEND_PORT 변경)
cd D:/github/cf
BACKEND_PORT=8074 uv run --package cf-be-api uvicorn cf_be_api.api:app --port 8074 &
PY_PID=$!

# Go be-api on 8073
cd D:/github/cf-go/backend/be-api-go
DATABASE_URL=... FALKORDB_URL=... BE_API_PORT=8073 ./be-api &
GO_PID=$!
sleep 5
```

- [ ] **Step 3: perf-bench.sh — 시나리오별 latency 측정**

`scripts/perf-bench.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

PY=http://localhost:8074
GO=http://127.0.0.1:8073
N=20

bench() {
    local label=$1 url=$2
    echo "=== $label ==="
    echo "Python:" 
    for i in $(seq 1 $N); do
        curl -s -o /dev/null -w "%{time_total}\n" "$PY$url"
    done | awk 'BEGIN{s=0}{s+=$1}END{printf "  avg: %.3fs\n", s/NR}'
    echo "Go:"
    for i in $(seq 1 $N); do
        curl -s -o /dev/null -w "%{time_total}\n" "$GO$url"
    done | awk 'BEGIN{s=0}{s+=$1}END{printf "  avg: %.3fs\n", s/NR}'
}

bench "/sites" "/sites"
bench "/sites?region=강원" "/sites?region=강원"
bench "/sites/search?q=강원" "/sites/search?q=강원&k=10"
bench "/facets" "/facets"
bench "/featured-axes" "/featured-axes"

# /eta/batch 는 POST — 별도
echo "=== /eta/batch (1000 ids) ==="
ids=$(python3 -c "import json; print(json.dumps([f'camp_{i}' for i in range(1000)]))")
body="{\"origin\":\"강남역\",\"ids\":$ids,\"concurrency\":8,\"timeout_s\":30}"
echo "Python:"
for i in $(seq 1 5); do
    curl -s -X POST -H "Content-Type: application/json" -d "$body" -o /dev/null -w "%{time_total}\n" "$PY/eta/batch"
done | awk '{s+=$1}END{printf "  avg: %.3fs\n", s/NR}'
echo "Go:"
for i in $(seq 1 5); do
    curl -s -X POST -H "Content-Type: application/json" -d "$body" -o /dev/null -w "%{time_total}\n" "$GO/eta/batch"
done | awk '{s+=$1}END{printf "  avg: %.3fs\n", s/NR}'
```

```bash
chmod +x scripts/perf-bench.sh
./scripts/perf-bench.sh 2>&1 | tee /tmp/perf.log
```

- [ ] **Step 4: 결과 도큐먼트**

`docs/sp-d-performance-baseline.md`:

```markdown
# SP-D Performance Baseline

**Date**: <YYYY-MM-DD>
**Hardware**: <CPU/RAM>
**Workload**: <describe>

## Latency comparison (avg of N=20 unless noted)

| Endpoint | Python (ms) | Go (ms) | Speedup |
|---|---|---|---|
| GET /sites | <X> | <Y> | <Y/X>x |
| GET /sites?region=강원 | <X> | <Y> | <ratio>x |
| GET /sites/search?q=강원 | <X> | <Y> | <ratio>x |
| GET /facets | <X> | <Y> | <ratio>x |
| GET /featured-axes | <X> | <Y> | <ratio>x |
| POST /eta/batch (1000 ids) | <X> | <Y> | <ratio>x |

## Verdict

Go ≥ Python (모든 워크로드): PASS | FAIL

## Notes
- ETA 의 가장 큰 변화는 subprocess 제거 효과 (등 추정).
- embedding 은 ONNX runtime 의 in-process inference 효과.
```

- [ ] **Step 5: Cross-validate 풀 시나리오**

`tests/integration/full_test.go`:

```go
//go:build integration
package integration

import (
	"net/http"
	"io/ioutil"
	"encoding/json"
	"sort"
	"testing"
	"github.com/stretchr/testify/assert"
)

func TestFullCrossValidation(t *testing.T) {
	scenarios := []struct {
		name string
		method, url string
		body string
	}{
		{"sites empty", "GET", "/sites", ""},
		{"sites region", "GET", "/sites?region=강원", ""},
		{"sites concept valley", "GET", "/sites?concept=valley", ""},
		{"facets", "GET", "/facets", ""},
		{"featured-axes", "GET", "/featured-axes", ""},
		{"concepts", "GET", "/concepts", ""},
		{"themes", "GET", "/themes", ""},
		{"marks", "GET", "/marks", ""},
		// ... 30개 시나리오
	}
	for _, s := range scenarios {
		t.Run(s.name, func(t *testing.T) {
			py := fetch("http://localhost:8074", s)
			go_ := fetch("http://127.0.0.1:8073", s)
			assert.Equal(t, normalize(py), normalize(go_), "scenario: %s", s.name)
		})
	}
}

// fetch + normalize 는 D-4 와 동일
```

- [ ] **Step 6: 정리 + commit + PR**

```bash
kill $PY_PID $GO_PID

cd D:/github/cf-go
git add scripts/perf-bench.sh docs/sp-d-performance-baseline.md
git commit -m "docs(sp-d): D-7 integration + perf bench

Cross-validation: Python (8074) vs Go (8073) 30 scenarios.
Performance: <summary>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push -u origin sprint/d7-integration-perf
gh pr create ... && gh pr merge --auto --merge
```

⚠️ Go performance 가 Python 보다 떨어지는 워크로드가 있으면 D-7 에서 BLOCKED. 원인 분석 (낮은 동시성? pgxpool 사이즈? ONNX warmup?) 후 fix sprint 추가.

---

## Task D-8: Cutover (Big bang) — 사용자 manual approval 필수

**Goal:** Go be-api 가 :8071 으로 부팅. Python `backend/be-api/` + `etago/` 디렉터리 제거. scripts 갱신. main 머지. **사용자 명시 승인 단계 추가** (auto-merge 금지).

**Files:**
- Modify: `D:/github/cf/scripts/dev-up.sh`, `dev-down.sh`, `lib/env.sh`, `test.sh`
- Modify: `D:/github/cf/pyproject.toml` (root) — workspace members 정리
- Modify: `D:/github/cf/backend/be-for-fe/src/cf_be_for_fe/settings.py` — BE_API_BASE_URL 그대로 (포트 8071)
- Delete: `D:/github/cf/backend/be-api/` (Python 패키지 전체)
- Delete: `D:/github/cf/etago/` (디렉터리 전체)
- Move: `D:/github/cf-go/backend/be-api-go/` → `D:/github/cf/backend/be-api/` (Go 패키지가 이름 그대로 차지)

- [ ] **Step 1: Branch (main worktree 에서)**

```bash
cd D:/github/cf
git checkout main && git pull
git checkout -b sprint/d8-cutover
```

- [ ] **Step 2: Go 바이너리를 backend/be-api/ 로 이동**

```bash
# 워크트리에서 .git 빼고 코드 통째 복사
rm -rf backend/be-api etago
cp -r D:/github/cf-go/backend/be-api-go backend/be-api
# 또는 git mv via rebase from feature/sp-d-go-rewrite (cleaner history)
```

⚠️ 권장: 워크트리 브랜치 `feature/sp-d-go-rewrite` 를 main 에 merge (rebase 또는 merge commit) — 이후 sprint/d8-cutover 는 cleanup 만:

```bash
# 옵션 A — feature 브랜치 머지 후 cleanup
cd D:/github/cf
git fetch
git merge feature/sp-d-go-rewrite --no-ff -m "Merge SP-D Go be-api work"
# 충돌 (동일 경로 backend/be-api Python ↔ Go) 발생 — 해결: Go 채택
# 그 다음 cleanup commit
git rm -r etago
# pyproject.toml 의 cf-be-api 멤버 제거
```

⚠️ 어떤 옵션이든 : Python `backend/be-api/` 와 Go `backend/be-api/` 가 같은 경로 — Python 디렉터리 제거 후 Go 디렉터리 그 자리에. cf-be-api 패키지 이름은 PyPI 에서 사라짐. uv workspace pyproject.toml 업데이트.

- [ ] **Step 3: pyproject.toml (root) 업데이트**

```toml
[tool.uv.workspace]
members = ["crawl/txcp", "crawl/camfit", "backend/be-for-fe", "pipeline"]
# backend/be-api 제거 (Go 가 됐음)

[tool.uv.sources]
cf-be-for-fe = { workspace = true }
# cf-be-api 줄 제거
```

`backend/be-for-fe/pyproject.toml` 의 `cf-be-api` 의존성 제거 (BFF 는 Go API 와 HTTP 통신만, dep 없음):

```toml
[project]
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "httpx>=0.27",
    "pydantic>=2.7",
    "pydantic-settings>=2.4",
    # "cf-be-api" 제거 — Go 와 HTTP 만
]

[tool.uv.sources]
# cf-be-api = { workspace = true } 제거
```

⚠️ BFF 가 cf-be-api 의 schemas (Pydantic) 를 import 하던 부분 정리 — D-4 에서 BFF projection 은 dict 기반이라 Pydantic 의존 없음 가정. 확인 필요.

- [ ] **Step 4: scripts 갱신**

`scripts/lib/env.sh` 끝:

```bash
# Go be-api (D-8 cutover)
export BE_API_PORT="${BE_API_PORT:-8071}"   # 동일 포트, 단지 Go 바이너리
export BE_API_BIN="$REPO_ROOT/backend/be-api/be-api"   # built Go binary
```

`scripts/dev-up.sh` 수정 — be-api 를 Go 바이너리로 부팅:

```bash
start_be_api() {
    if [ -f "$BE_API_PID_FILE" ] && pid_alive "$(cat "$BE_API_PID_FILE")"; then
        log_warn "be-api already running"
        return 0
    fi
    if [ ! -x "$BE_API_BIN" ]; then
        log_info "building be-api Go binary"
        (cd "$REPO_ROOT/backend/be-api" && go build -o be-api ./cmd/be-api)
    fi
    log_info "starting be-api (Go) on $BE_API_HOST:$BE_API_PORT"
    DATABASE_URL="$DATABASE_URL" \
    FALKORDB_URL="$FALKORDB_URL" \
    NAVER_NCP_CLIENT_ID="${NAVER_NCP_CLIENT_ID:-}" \
    NAVER_NCP_CLIENT_SECRET="${NAVER_NCP_CLIENT_SECRET:-}" \
    KAKAO_REST_KEY="${KAKAO_REST_KEY:-}" \
    BE_API_HOST="$BE_API_HOST" \
    BE_API_PORT="$BE_API_PORT" \
    nohup "$BE_API_BIN" > "$BE_API_LOG_FILE" 2>&1 &
    write_pid "$BE_API_PID_FILE" "$!"
}
```

`scripts/test.sh` — be-api Python 테스트 row 제거, Go 빌드 + go test 추가:

```bash
log_info "go test cf-be-api"
(cd "$REPO_ROOT/backend/be-api" && go test ./...) || exit 1
```

`scripts/backend-up.sh` — Go binary 만 부팅하도록 갱신.

- [ ] **Step 5: BFF settings 변경 없음 확인**

BFF 의 BE_API_BASE_URL 디폴트가 `http://localhost:8071` — Go be-api 도 같은 포트라 변경 불필요. cf-be-api dep 제거 외에는 BFF 코드 변경 없음.

```bash
grep -n "be_api_base_url\|cf-be-api\|cf_be_api" backend/be-for-fe/src/cf_be_for_fe/
```

발견된 Python import 모두 제거 또는 stub.

- [ ] **Step 6: fallback 모드 제공**

`scripts/dev-up.sh` 에 환경변수 분기:

```bash
if [ "${FALLBACK_PYTHON_BE_API:-0}" = "1" ]; then
    log_warn "FALLBACK_PYTHON_BE_API=1 — Go be-api 우회, 이전 Python 패키지 git revert 필요"
    log_warn "수단: git revert <merge sha>; ./scripts/dev-up.sh"
    exit 1
fi
```

이건 안전망 — 실제 fallback 절차는 git revert.

- [ ] **Step 7: 풀 smoke**

```bash
cd D:/github/cf
./scripts/dev-up.sh
sleep 4
curl -sf http://localhost:8070/healthz | head -c 300 && echo
curl -sf http://localhost:8071/healthz | head -c 300 && echo
curl -sf "http://localhost:8070/sites?region=강원" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'count={len(d)}')"
curl -sI -A "iPhone" http://localhost:8070/ | head -3
./scripts/test.sh 2>&1 | tail -10
./scripts/dev-down.sh
```

기대:
- 두 healthz 모두 200
- /sites count > 1900 (P6 필터 후)
- iPhone UA → 302 /m.html
- test.sh 모든 packages PASS (Go test 포함, Python be-api 사라짐)

- [ ] **Step 8: Commit + PR (auto-merge 금지)**

```bash
git add -A
git status -s   # 의도한 변경만인지 검토
git commit -m "feat(sp-d): D-8 cutover — Python be-api → Go be-api (Big bang)

- backend/be-api/ Python 패키지 제거
- backend/be-api/ Go 패키지로 차지 (포트 8071 유지)
- etago/ 디렉터리 제거 (Go 코드는 backend/be-api/internal/adapters/{eta,geocode}/)
- workspace pyproject members 정리, BFF cf-be-api dep 제거
- scripts/dev-up.sh 가 Go 바이너리 빌드+부팅
- BFF 설정·포트 변경 없음 (fe 무영향)

⚠️ Big bang. fallback: git revert <this commit>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin sprint/d8-cutover

# ⚠️ Auto-merge 금지 — 사용자 명시 승인 필요
gh pr create --title "SP-D D-8 CUTOVER — Python be-api → Go (Big bang)" --body "$(cat <<'EOF'
## ⚠️ MANUAL APPROVAL REQUIRED

Big bang cutover. Auto-merge 비활성화.

## Summary
- backend/be-api/ Python → Go 교체 (포트 8071 유지)
- etago/ 디렉터리 제거 (코드는 be-api adapters 흡수)
- BFF 설정·포트 무변경 (fe 무영향)

## Pre-merge checklist
- [ ] D-7 perf baseline OK
- [ ] D-7 cross-validation 30 시나리오 PASS
- [ ] 풀 smoke 결과 위 commit 메시지 참조
- [ ] fallback 절차: git revert <PR merge sha>

## Post-merge actions
- 워크트리 정리: `git worktree remove D:/github/cf-go`
- main 동기 후 dev-up.sh 부팅 → 모든 fe 트래픽 Go 통과 확인

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"

# ⚠️ MERGE 는 사용자가 직접 승인하거나 명시 지시 후
# gh pr merge --merge   # 사용자 승인 후만
```

⚠️ 사용자 입장: PR 검토 → 승인 → manual `gh pr merge --merge`. AI implementer 는 머지 명령 실행 금지.

- [ ] **Step 9: Post-merge 정리**

머지 후 (사용자 승인):

```bash
cd D:/github/cf
git checkout main && git pull
git worktree remove D:/github/cf-go
git branch -D feature/sp-d-go-rewrite 2>/dev/null
./scripts/dev-up.sh
sleep 4
curl -sf http://localhost:8070/sites | python3 -c "import sys,json; print(len(json.load(sys.stdin)))"
```

기대: count 정상 (~1996), 모든 fe 트래픽 Go 통과.

---

## Self-review checklist

**Spec coverage**:
- [x] Spec 4절 디렉터리 → D-1~D-6 의 Files 섹션
- [x] Spec 5절 etago 흡수 매핑 → D-5 Step 2-3
- [x] Spec 6절 라이브러리 스택 → D-1 Step 2 + D-3 Step 2
- [x] Spec 8절 Sprint 구조 → 본 plan 의 Task D-0~D-8 1:1 매핑
- [x] Spec 9절 D-0 PoC 게이트 → D-0 Step 8 (cosine ≥0.99/0.95)
- [x] Spec 10절 워크트리 전략 → 본 plan 첫 섹션
- [x] Spec 11절 위험 → 각 task 의 ⚠️ 마커 + D-7 fallback + D-8 manual approval

**Type consistency**:
- `domain.Camp` (D-2) → 모든 use case + handler 사용 일관
- `ports.CampReader.ListCamps(ctx, opts)` (D-2) → list_camps usecase + sites handler (D-4)
- `ports.Embedder.Encode(ctx, text)` (D-3) → semantic_search (D-3)
- `ports.EtaProvider.EstimateBatch(ctx, originLat, originLon, dests)` (D-5)
- `ports.GeocodeProvider.Geocode(ctx, placeName)` (D-5)
- `EtaResult{Minutes, Within}` (D-5) → handler 응답

**Placeholder check**:
- ⚠️ 마커가 명시한 부분: domain.Camp 의 정확한 fields (D-2) — Python source 보고 1:1, FEATURED_AXES 리스트 (D-2) — Python featured_axes.py 1:1, postgres SQL (D-2 Step 7) — Python camp_repo.py 1:1, falkor adapter 디테일 (D-2 Step 8) — D-1 smoke 결정에 따름. 이는 plan 의 한계가 아니라 *원본 source 1:1 복사 필요* 명시 (skill 의 placeholder 와 다른 종류 — 명확한 source 참조 있음).
- D-3 의 `helper inline` 류 코드 — `inference.go` 분리 명시.
- D-5 의 envfile 흡수 grep 결과에 따른 호출 변경 — Step 4 에서 `cfg.NaverNCPClientID` 등 명시.

**PR 단위·자동 머지** — D-0~D-7 은 `gh pr merge --auto --merge` (저위험), D-8 은 사용자 manual approval (Big bang).

## 알려진 한계

- D-2 의 Camp struct, FEATURED_AXES 리스트, postgres SQL 은 Python source 정확값 의존 — plan 의 코드는 시그니처/패턴만 + ⚠️ 마커.
- D-2 의 Falkor adapter 는 D-1 smoke 결과 (falkordb-go vs RESP 직접) 에 따라 분기.
- D-3 의 ONNX 추론 디테일 (sequence padding, position ids 등) 은 D-0 PoC 의 정확한 코드를 그대로 가져감.
- D-7 perf 결과가 Go < Python 인 워크로드가 있으면 BLOCKED — fix sprint 별도.
- D-8 cutover PR 의 merge 는 사용자 명시 승인 (auto-merge 금지) — implementer subagent 가 임의 머지 금지.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-10-sp-d-go-rewrite.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — sprint 별 fresh subagent. D-0 게이트 결과로 D-1+ 진입 결정. D-8 은 사용자 manual approval 후 진행.

**2. Inline Execution** — 본 세션이 sprint 직접 실행.

**어느 방식?**
