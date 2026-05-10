"""SP-D D-0: Export jhgan/ko-sroberta-multitask to ONNX.

Outputs:
  poc/d0-onnx/tokenizer/        — HF tokenizer files (tokenizer.json + vocab + config)
  poc/d0-onnx/onnx_model/ko-sroberta.onnx — ONNX model with dynamic batch+seq

Usage:
  uv run --no-project --with transformers --with torch --with onnx \
    python scripts/export-ko-sroberta-onnx.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import torch
from transformers import AutoModel, AutoTokenizer

MODEL_NAME = "jhgan/ko-sroberta-multitask"
ROOT = Path(__file__).resolve().parent.parent
TOKENIZER_DIR = ROOT / "poc" / "d0-onnx" / "tokenizer"
ONNX_DIR = ROOT / "poc" / "d0-onnx" / "onnx_model"
ONNX_PATH = ONNX_DIR / "ko-sroberta.onnx"


class KoSRobertaWrapper(torch.nn.Module):
    """Thin wrapper exposing (last_hidden_state, pooler_output) for ONNX export."""

    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor):
        out = self.model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            return_dict=True,
        )
        last_hidden_state = out.last_hidden_state
        pooler_output = (
            out.pooler_output
            if out.pooler_output is not None
            else last_hidden_state[:, 0, :]
        )
        return last_hidden_state, pooler_output


def main() -> int:
    TOKENIZER_DIR.mkdir(parents=True, exist_ok=True)
    ONNX_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[export] loading {MODEL_NAME}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME)
    model.eval()

    print(f"[export] saving tokenizer → {TOKENIZER_DIR}", flush=True)
    tokenizer.save_pretrained(str(TOKENIZER_DIR))

    # Force-save HuggingFace fast tokenizer.json (sugarme/tokenizer needs this).
    # Also strip padding/truncation sections — sugarme/tokenizer 0.2.2 has a
    # known bug where it panics on BatchLongest padding (no `size` key), and we
    # apply our own truncation/padding policy in main.go anyway.
    try:
        from tokenizers import Tokenizer  # type: ignore

        tj_path = TOKENIZER_DIR / "tokenizer.json"
        Tokenizer.from_pretrained(MODEL_NAME).save(str(tj_path))
        import json as _json

        with tj_path.open(encoding="utf-8") as _f:
            _tj = _json.load(_f)
        _tj["padding"] = None
        _tj["truncation"] = None
        with tj_path.open("w", encoding="utf-8") as _f:
            _json.dump(_tj, _f, ensure_ascii=False)
        print("[export] explicit tokenizer.json written (padding/truncation stripped)", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[export] WARN: explicit tokenizer.json failed: {exc}", flush=True)

    sample = tokenizer(
        ["감악산 출렁다리 캠핑장"],
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=16,
    )

    wrapper = KoSRobertaWrapper(model)
    wrapper.eval()

    print(f"[export] exporting ONNX -> {ONNX_PATH}", flush=True)
    # Force legacy TorchScript-based exporter (dynamo=False) so dynamic_axes works
    # cleanly with opset 14 (matches yalue/onnxruntime_go expectations).
    torch.onnx.export(
        wrapper,
        (sample["input_ids"], sample["attention_mask"]),
        str(ONNX_PATH),
        input_names=["input_ids", "attention_mask"],
        output_names=["last_hidden_state", "pooler_output"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "seq"},
            "attention_mask": {0: "batch", 1: "seq"},
            "last_hidden_state": {0: "batch", 1: "seq"},
            "pooler_output": {0: "batch"},
        },
        opset_version=14,
        do_constant_folding=True,
        dynamo=False,
    )

    size_mb = ONNX_PATH.stat().st_size / (1024 * 1024)
    print(f"[export] done: {ONNX_PATH} ({size_mb:.1f} MB)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
