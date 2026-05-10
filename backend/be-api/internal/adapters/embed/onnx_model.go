// OnnxEmbedder — adapter implementing ports.Embedder via ONNX Runtime.
//
// Model: jhgan/ko-sroberta-multitask exported to ONNX (opset 14, dynamo=False)
// per D-0. Inference applies mask-weighted mean pooling over `last_hidden_state`
// to produce a 768-dim float32 embedding. Cosine vs the Python sentence-
// transformers reference is ≥ 0.99 avg / ≥ 0.95 min (see D-0 GATE).
//
// The adapter owns the ONNX environment and a single dynamic session. The
// session is goroutine-safe per onnxruntime_go documentation; Encode does NOT
// add additional locking. Close MUST be called once on shutdown — destroying
// the environment more than once is a panic in onnxruntime_go.
package embed

import (
	"context"
	"fmt"
	"sync"

	ort "github.com/yalue/onnxruntime_go"

	"github.com/whyjp/cf/be-api/internal/ports"
)

// HiddenDim is the embedding dimensionality for ko-sroberta-multitask.
const HiddenDim = 768

// envOnce ensures we only initialise/destroy the global ORT environment once
// across all OnnxEmbedder instances in the process.
var (
	envOnce sync.Once
	envErr  error
)

// OnnxEmbedder implements ports.Embedder.
type OnnxEmbedder struct {
	session *ort.DynamicAdvancedSession
	tok     *Tokenizer
}

// Compile-time assertion: OnnxEmbedder implements ports.Embedder.
var _ ports.Embedder = (*OnnxEmbedder)(nil)

// NewOnnxEmbedder loads `tokenizer.json` and the ONNX model.
//
//   libPath:       absolute path to onnxruntime.dll / libonnxruntime.so
//   modelPath:     absolute path to ko-sroberta.onnx
//   tokenizerPath: absolute path to tokenizer.json
//                  (padding/truncation stripped per D-0)
func NewOnnxEmbedder(libPath, modelPath, tokenizerPath string) (*OnnxEmbedder, error) {
	envOnce.Do(func() {
		ort.SetSharedLibraryPath(libPath)
		if err := ort.InitializeEnvironment(); err != nil {
			envErr = fmt.Errorf("init ort env (%s): %w", libPath, err)
		}
	})
	if envErr != nil {
		return nil, envErr
	}

	tok, err := LoadTokenizer(tokenizerPath)
	if err != nil {
		return nil, fmt.Errorf("load tokenizer (%s): %w", tokenizerPath, err)
	}

	session, err := ort.NewDynamicAdvancedSession(
		modelPath,
		[]string{"input_ids", "attention_mask"},
		[]string{"last_hidden_state", "pooler_output"},
		nil,
	)
	if err != nil {
		return nil, fmt.Errorf("create ort session (%s): %w", modelPath, err)
	}
	return &OnnxEmbedder{session: session, tok: tok}, nil
}

// Encode tokenizes `text` and returns the 768-d mean-pooled embedding.
// Honours ctx cancellation between tokenisation and inference (the underlying
// ORT Run is uninterruptible).
func (e *OnnxEmbedder) Encode(ctx context.Context, text string) ([]float32, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	ids, mask, err := e.tok.Encode(text)
	if err != nil {
		return nil, fmt.Errorf("tokenize: %w", err)
	}
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	return runMeanPool(e.session, ids, mask)
}

// Close destroys the ONNX session. The shared environment is NOT destroyed —
// onnxruntime_go panics on double-destroy and the env is process-scoped.
func (e *OnnxEmbedder) Close() error {
	if e.session == nil {
		return nil
	}
	err := e.session.Destroy()
	e.session = nil
	return err
}

// runMeanPool runs one forward pass and returns a 768-d mask-weighted mean
// pooled vector. Code lifted verbatim from D-0 `poc/d0-onnx/inference.go` —
// keep in sync if D-0 changes.
func runMeanPool(session *ort.DynamicAdvancedSession, ids []int64, mask []int64) ([]float32, error) {
	if len(ids) != len(mask) {
		return nil, fmt.Errorf("ids/mask length mismatch: %d vs %d", len(ids), len(mask))
	}
	seq := int64(len(ids))
	shape := ort.NewShape(1, seq)

	idsTensor, err := ort.NewTensor(shape, ids)
	if err != nil {
		return nil, fmt.Errorf("create input_ids tensor: %w", err)
	}
	defer idsTensor.Destroy()

	maskTensor, err := ort.NewTensor(shape, mask)
	if err != nil {
		return nil, fmt.Errorf("create attention_mask tensor: %w", err)
	}
	defer maskTensor.Destroy()

	lhsShape := ort.NewShape(1, seq, HiddenDim)
	lhsTensor, err := ort.NewEmptyTensor[float32](lhsShape)
	if err != nil {
		return nil, fmt.Errorf("create last_hidden_state tensor: %w", err)
	}
	defer lhsTensor.Destroy()

	poolerShape := ort.NewShape(1, HiddenDim)
	poolerTensor, err := ort.NewEmptyTensor[float32](poolerShape)
	if err != nil {
		return nil, fmt.Errorf("create pooler_output tensor: %w", err)
	}
	defer poolerTensor.Destroy()

	if err := session.Run(
		[]ort.Value{idsTensor, maskTensor},
		[]ort.Value{lhsTensor, poolerTensor},
	); err != nil {
		return nil, fmt.Errorf("session.Run: %w", err)
	}

	lhs := lhsTensor.GetData() // length = 1 * seq * HiddenDim, row-major
	out := make([]float32, HiddenDim)
	var weight float32
	for t := int64(0); t < seq; t++ {
		m := float32(mask[t])
		if m == 0 {
			continue
		}
		weight += m
		base := int(t) * HiddenDim
		for h := 0; h < HiddenDim; h++ {
			out[h] += lhs[base+h] * m
		}
	}
	if weight == 0 {
		return out, nil
	}
	for h := 0; h < HiddenDim; h++ {
		out[h] /= weight
	}
	return out, nil
}
