package main

import (
	"fmt"

	ort "github.com/yalue/onnxruntime_go"
)

// runMeanPool performs a single forward pass through the ONNX session and
// returns a 768-dim mean-pooled embedding (mask-weighted, matching
// sentence-transformers' default Pooling(mode="mean") behavior).
//
// `ids` and `mask` are the int64 input_ids and attention_mask for one sample
// (shape [1, seq]); the function builds tensors, runs inference, applies
// mask-weighted mean pooling on last_hidden_state, and returns the resulting
// 768-d float32 vector.
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

	// last_hidden_state output: [1, seq, hidden]; we don't know hidden ahead of
	// time so allocate after probing model — but for ko-sroberta hidden=768.
	lhsShape := ort.NewShape(1, seq, hiddenDim)
	lhsTensor, err := ort.NewEmptyTensor[float32](lhsShape)
	if err != nil {
		return nil, fmt.Errorf("create last_hidden_state tensor: %w", err)
	}
	defer lhsTensor.Destroy()

	poolerShape := ort.NewShape(1, hiddenDim)
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

	lhs := lhsTensor.GetData() // length = 1 * seq * hiddenDim, row-major
	out := make([]float32, hiddenDim)
	var weight float32
	for t := int64(0); t < seq; t++ {
		m := float32(mask[t])
		if m == 0 {
			continue
		}
		weight += m
		base := int(t) * hiddenDim
		for h := 0; h < hiddenDim; h++ {
			out[h] += lhs[base+h] * m
		}
	}
	if weight == 0 {
		return out, nil
	}
	for h := 0; h < hiddenDim; h++ {
		out[h] /= weight
	}
	return out, nil
}
