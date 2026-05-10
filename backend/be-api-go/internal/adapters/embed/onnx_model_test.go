// Regression test — verify the Go ONNX path matches the D-0 PoC's expected
// embeddings (which themselves were validated against Python sentence-
// transformers in D-0). PASS gate: cosine avg ≥ 0.99 AND min ≥ 0.95 — same
// thresholds D-0 used.
//
// Skipped unless the four env vars below are set, so CI without GPU/model
// assets passes silently. To run locally:
//
//   set ONNXRUNTIME_LIB=...\onnxruntime.dll
//   set KO_SROBERTA_ONNX=...\ko-sroberta.onnx
//   set KO_SROBERTA_TOKENIZER=...\tokenizer.json
//   set D0_EXPECTED_JSON=...\poc\d0-onnx\expected.json
//   go test -run TestOnnxEmbedder_RegressionVsD0Expected ./internal/adapters/embed -v
package embed

import (
	"context"
	"encoding/json"
	"math"
	"os"
	"testing"
)

type expectedFile struct {
	Model      string      `json:"model"`
	Normalize  bool        `json:"normalize"`
	Dim        int         `json:"dim"`
	Samples    []string    `json:"samples"`
	Embeddings [][]float64 `json:"embeddings"`
}

func cosineF32F64(a []float32, b []float64) float64 {
	if len(a) != len(b) {
		return math.NaN()
	}
	var dot, na, nb float64
	for i := range a {
		ai := float64(a[i])
		bi := b[i]
		dot += ai * bi
		na += ai * ai
		nb += bi * bi
	}
	if na == 0 || nb == 0 {
		return 0
	}
	return dot / (math.Sqrt(na) * math.Sqrt(nb))
}

func TestOnnxEmbedder_RegressionVsD0Expected(t *testing.T) {
	libPath := os.Getenv("ONNXRUNTIME_LIB")
	modelPath := os.Getenv("KO_SROBERTA_ONNX")
	tokPath := os.Getenv("KO_SROBERTA_TOKENIZER")
	expPath := os.Getenv("D0_EXPECTED_JSON")
	if libPath == "" || modelPath == "" || tokPath == "" || expPath == "" {
		t.Skip("set ONNXRUNTIME_LIB / KO_SROBERTA_ONNX / KO_SROBERTA_TOKENIZER / D0_EXPECTED_JSON to run regression")
	}

	raw, err := os.ReadFile(expPath)
	if err != nil {
		t.Fatalf("read expected.json: %v", err)
	}
	var exp expectedFile
	if err := json.Unmarshal(raw, &exp); err != nil {
		t.Fatalf("parse expected.json: %v", err)
	}
	if len(exp.Samples) == 0 || len(exp.Samples) != len(exp.Embeddings) {
		t.Fatalf("expected.json malformed: samples=%d embeddings=%d",
			len(exp.Samples), len(exp.Embeddings))
	}

	e, err := NewOnnxEmbedder(libPath, modelPath, tokPath)
	if err != nil {
		t.Fatalf("init embedder: %v", err)
	}
	defer e.Close()

	ctx := context.Background()
	var sum, lo float64 = 0, 1.0
	for i, s := range exp.Samples {
		got, err := e.Encode(ctx, s)
		if err != nil {
			t.Fatalf("encode sample[%d] %q: %v", i, s, err)
		}
		c := cosineF32F64(got, exp.Embeddings[i])
		sum += c
		if c < lo {
			lo = c
		}
	}
	avg := sum / float64(len(exp.Samples))
	t.Logf("D-0 regression: cosine avg=%.6f min=%.6f over %d samples", avg, lo, len(exp.Samples))
	if avg < 0.99 {
		t.Errorf("avg cosine %.6f < 0.99", avg)
	}
	if lo < 0.95 {
		t.Errorf("min cosine %.6f < 0.95", lo)
	}
}
