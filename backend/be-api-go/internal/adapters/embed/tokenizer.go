// Tokenizer wrapper — sugarme/tokenizer + truncation workaround.
//
// Background: `pretrained.FromFile` of an upstream HuggingFace `tokenizer.json`
// fails on RoBERTa configs that include `padding`/`truncation` blocks. The D-0
// PoC handled this by stripping those blocks from `tokenizer.json` at export
// time and re-applying truncation programmatically here. We preserve that
// workaround verbatim so the Go path is bit-identical to D-0 inference.
package embed

import (
	"github.com/sugarme/tokenizer"
	"github.com/sugarme/tokenizer/pretrained"
)

// MaxSeqLength matches the Python `sentence-transformers` default for
// jhgan/ko-sroberta-multitask (max_length=128, truncation=longest-first).
const MaxSeqLength = 128

// Tokenizer is a thin wrapper around `*tokenizer.Tokenizer` that handles the
// padding/truncation-stripping workaround and exposes the int64 ids/mask
// shape the ONNX session wants.
type Tokenizer struct {
	tk *tokenizer.Tokenizer
}

// LoadTokenizer reads a HuggingFace `tokenizer.json` (with padding/truncation
// blocks stripped — see file header) and re-applies truncation via the Go
// API. MaxLength=128, Strategy=LongestFirst — matches D-0 PoC.
func LoadTokenizer(path string) (*Tokenizer, error) {
	tk, err := pretrained.FromFile(path)
	if err != nil {
		return nil, err
	}
	tk.WithTruncation(&tokenizer.TruncationParams{
		MaxLength: MaxSeqLength,
		Strategy:  tokenizer.LongestFirst,
		Stride:    0,
	})
	return &Tokenizer{tk: tk}, nil
}

// Encode tokenizes a single string with [CLS]…[SEP] special tokens, returning
// int64 input_ids and attention_mask suitable for an ONNX RoBERTa session.
//
// We do NOT pad to MaxSeqLength — the model accepts dynamic seq length and
// mean-pooling is mathematically identical (pad tokens are masked off).
func (t *Tokenizer) Encode(text string) (ids []int64, mask []int64, err error) {
	enc, err := t.tk.EncodeSingle(text, true) // addSpecialTokens=true
	if err != nil {
		return nil, nil, err
	}
	idsRaw := enc.GetIds()
	maskRaw := enc.GetAttentionMask()
	if len(idsRaw) > MaxSeqLength {
		idsRaw = idsRaw[:MaxSeqLength]
		maskRaw = maskRaw[:MaxSeqLength]
	}
	ids = make([]int64, len(idsRaw))
	mask = make([]int64, len(maskRaw))
	for i, v := range idsRaw {
		ids[i] = int64(v)
	}
	for i, v := range maskRaw {
		mask[i] = int64(v)
	}
	return ids, mask, nil
}
