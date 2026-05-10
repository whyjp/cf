// Command d0-poc — SP-D D-0 GATE: ONNX inference parity vs Python sentence-transformers.
//
// Loads:
//   - tokenizer/tokenizer.json  (sugarme/tokenizer, HuggingFace fast format)
//   - onnx_model/ko-sroberta.onnx (yalue/onnxruntime_go via onnxruntime.dll)
//   - expected.json (50 Korean samples + reference 768-d float embeddings from
//     sentence-transformers, normalize=False)
//
// For each sample: tokenize (max_length=128, [CLS]+[SEP], pad to seq), forward
// through ONNX, mean-pool last_hidden_state (mask-weighted) → 768-d float, then
// cosine vs the expected embedding.
//
// GATE: cosine avg ≥ 0.99 AND cosine min ≥ 0.95 → PASS, else FAIL.
package main

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"runtime"

	"github.com/sugarme/tokenizer"
	"github.com/sugarme/tokenizer/pretrained"
	ort "github.com/yalue/onnxruntime_go"
)

const (
	hiddenDim    = 768
	maxSeqLength = 128
	padTokenID   = 1 // [PAD] in ko-sroberta tokenizer
	gateAvgMin   = 0.99
	gateMinMin   = 0.95
)

type expectedFile struct {
	Model      string      `json:"model"`
	Normalize  bool        `json:"normalize"`
	Dim        int         `json:"dim"`
	Samples    []string    `json:"samples"`
	Embeddings [][]float64 `json:"embeddings"`
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintf(os.Stderr, "FATAL: %v\n", err)
		os.Exit(1)
	}
}

func run() error {
	// ---- Load expected ground truth ------------------------------------------
	expected, err := loadExpected("expected.json")
	if err != nil {
		return fmt.Errorf("load expected.json: %w", err)
	}
	n := len(expected.Samples)
	if n == 0 || len(expected.Embeddings) != n {
		return fmt.Errorf("expected.json malformed: samples=%d embeddings=%d", n, len(expected.Embeddings))
	}
	fmt.Printf("loaded %d samples (model=%s, dim=%d, normalize=%v)\n",
		n, expected.Model, expected.Dim, expected.Normalize)

	// ---- Load tokenizer ------------------------------------------------------
	tokPath, err := filepath.Abs(filepath.Join("tokenizer", "tokenizer.json"))
	if err != nil {
		return fmt.Errorf("resolve tokenizer path: %w", err)
	}
	tk, err := pretrained.FromFile(tokPath)
	if err != nil {
		return fmt.Errorf("load tokenizer (%s): %w", tokPath, err)
	}
	tk.WithTruncation(&tokenizer.TruncationParams{
		MaxLength: maxSeqLength,
		Strategy:  tokenizer.LongestFirst,
		Stride:    0,
	})
	fmt.Printf("tokenizer loaded: %s\n", tokPath)

	// ---- Init ONNX runtime ---------------------------------------------------
	libName := sharedLibName()
	libPath, err := filepath.Abs(libName)
	if err != nil {
		return fmt.Errorf("resolve ort lib path: %w", err)
	}
	ort.SetSharedLibraryPath(libPath)
	if err := ort.InitializeEnvironment(); err != nil {
		return fmt.Errorf("init ort env (%s): %w", libPath, err)
	}
	defer ort.DestroyEnvironment()
	fmt.Printf("onnxruntime initialized (lib=%s, version=%s)\n", libPath, ort.GetVersion())

	modelPath, err := filepath.Abs(filepath.Join("onnx_model", "ko-sroberta.onnx"))
	if err != nil {
		return fmt.Errorf("resolve onnx model path: %w", err)
	}
	session, err := ort.NewDynamicAdvancedSession(
		modelPath,
		[]string{"input_ids", "attention_mask"},
		[]string{"last_hidden_state", "pooler_output"},
		nil,
	)
	if err != nil {
		return fmt.Errorf("create ort session (%s): %w", modelPath, err)
	}
	defer session.Destroy()
	fmt.Printf("onnx model loaded: %s\n", modelPath)

	// ---- Inference + cosine --------------------------------------------------
	cosines := make([]float64, n)
	for i, sample := range expected.Samples {
		ids, mask, err := encodeSample(tk, sample)
		if err != nil {
			return fmt.Errorf("sample[%d] tokenize %q: %w", i, sample, err)
		}
		got, err := runMeanPool(session, ids, mask)
		if err != nil {
			return fmt.Errorf("sample[%d] inference: %w", i, err)
		}
		want := expected.Embeddings[i]
		if len(want) != hiddenDim {
			return fmt.Errorf("sample[%d] expected dim=%d, want %d", i, len(want), hiddenDim)
		}
		cos := cosineFloat32Float64(got, want)
		cosines[i] = cos
		fmt.Printf("  sample[%02d] cos=%.8f  (%s)\n", i, cos, truncateForLog(sample, 40))
	}

	avg, lo := summarize(cosines)
	pass := avg >= gateAvgMin && lo >= gateMinMin

	fmt.Println()
	fmt.Printf("cosine avg : %.6f\n", avg)
	fmt.Printf("cosine min : %.6f\n", lo)
	fmt.Printf("gate avg ≥ %.2f && min ≥ %.2f\n", gateAvgMin, gateMinMin)
	if pass {
		fmt.Println("GATE: PASS")
	} else {
		fmt.Println("GATE: FAIL")
	}
	return nil
}

// ---------- helpers ----------------------------------------------------------

func loadExpected(path string) (*expectedFile, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var e expectedFile
	if err := json.Unmarshal(b, &e); err != nil {
		return nil, err
	}
	return &e, nil
}

// encodeSample tokenizes one input string into int64 input_ids and
// attention_mask, padded to maxSeqLength on the right with padTokenID
// (matches the Python tokenizer config: padding_side=right, pad_token=[PAD]=1).
func encodeSample(tk *tokenizer.Tokenizer, sample string) ([]int64, []int64, error) {
	enc, err := tk.EncodeSingle(sample, true) // addSpecialTokens=true → [CLS]…[SEP]
	if err != nil {
		return nil, nil, err
	}
	idsRaw := enc.GetIds()
	maskRaw := enc.GetAttentionMask()
	if len(idsRaw) != len(maskRaw) {
		return nil, nil, fmt.Errorf("ids/mask length differ: %d vs %d", len(idsRaw), len(maskRaw))
	}
	if len(idsRaw) > maxSeqLength {
		idsRaw = idsRaw[:maxSeqLength]
		maskRaw = maskRaw[:maxSeqLength]
	}
	ids := make([]int64, len(idsRaw))
	mask := make([]int64, len(maskRaw))
	for i, v := range idsRaw {
		ids[i] = int64(v)
	}
	for i, v := range maskRaw {
		mask[i] = int64(v)
	}
	// Pad to maxSeqLength (Python uses padding="max_length" inside ST encode for batches;
	// here we keep dynamic seq per sample which is mathematically equivalent for
	// mean-pooling — pad tokens are masked off anyway. We do NOT pad to fixed
	// length to avoid wasted compute. But tokenizer-level padding is OFF.)
	return ids, mask, nil
}

func cosineFloat32Float64(a []float32, b []float64) float64 {
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

func summarize(xs []float64) (avg, lo float64) {
	if len(xs) == 0 {
		return 0, 0
	}
	lo = xs[0]
	var sum float64
	for _, x := range xs {
		sum += x
		if x < lo {
			lo = x
		}
	}
	return sum / float64(len(xs)), lo
}

func sharedLibName() string {
	switch runtime.GOOS {
	case "windows":
		return "onnxruntime.dll"
	case "darwin":
		return "libonnxruntime.dylib"
	default:
		return "libonnxruntime.so"
	}
}

func truncateForLog(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n]) + "…"
}
