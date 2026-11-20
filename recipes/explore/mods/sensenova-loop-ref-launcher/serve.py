#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""OpenAI-compatible reference serve for sensenova/SenseNova-Loop-9B.

Why this exists
---------------
No pinned engine loads this checkpoint (evidence in the lane README): vLLM needs the unmerged
PR #64832 and SGLang the unmerged PR #47281, llama.cpp needs the OpenSenseNova fork because
upstream registers no `sensenova_loop` architecture, and the architecture is not a static graph
anyway — `modeling_sensenova_loop.py` replays physical layers 4..28 a second time and reshapes
the residual into two mHC streams, neither of which a paged-attention engine can express.
The one loader that builds it is transformers' own `trust_remote_code` path over its `qwen3_5`
backbone, so this arm is a REFERENCE probe: one request at a time, no batching, no paged KV.

Endpoints: GET /health, GET /v1/models, POST /v1/chat/completions (non-streaming).
"""
from __future__ import annotations

import argparse
import threading
from typing import Any

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from transformers import AutoModelForCausalLM, AutoTokenizer

TAG = "[sensenova-loop-ref]"
_LOCK = threading.Lock()
_STATE: dict[str, Any] = {}


def split_reasoning(text: str) -> tuple[str | None, str]:
    """The template opens ` thinking`; the model closes it and the answer follows."""
    if "</think>" not in text:
        return None, text.strip()
    head, _, tail = text.partition("</think>")
    return head.replace(" thinking", "").strip() or None, tail.strip()


def load(model_path: str, served_name: str | None, context_length: int) -> None:
    print(f"{TAG} loading {model_path} (trust_remote_code, bf16, reference route)", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path, trust_remote_code=True, dtype=torch.bfloat16, device_map={"": "cuda"}
    ).eval()
    _STATE.update(
        tokenizer=tokenizer,
        model=model,
        name=served_name or "sensenova/SenseNova-Loop-9B",
        context_length=context_length,
    )
    print(f"{TAG} ready: {_STATE['name']} (context cap {context_length})", flush=True)


def build() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok" if _STATE.get("model") is not None else "loading"}

    @app.get("/v1/models")
    def models():
        return {"object": "list", "data": [{"id": _STATE.get("name", ""), "object": "model"}]}

    @app.post("/v1/chat/completions")
    def chat(body: dict[str, Any]):
        if body.get("stream"):
            raise HTTPException(status_code=400, detail="this reference serve is non-streaming")
        messages = body.get("messages") or []
        if not messages:
            raise HTTPException(status_code=400, detail="messages is required")
        tok, model = _STATE["tokenizer"], _STATE["model"]
        max_new = int(body.get("max_tokens") or 512)
        # The checkpoint claims 524288 positions; a reference serve caps one prefill instead.
        room = max(1, int(_STATE["context_length"]) - max_new)
        prompt = tok.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            **(body.get("chat_template_kwargs") or {}),
        )
        ids = tok(prompt, return_tensors="pt", truncation=True, max_length=room).to("cuda")
        # Greedy: this is a correctness probe, so sampling is deliberately not offered.
        with _LOCK, torch.inference_mode():
            out = model.generate(**ids, max_new_tokens=max_new, do_sample=False)
        prompt_len = int(ids["input_ids"].shape[-1])
        new_len = int(out.shape[-1]) - prompt_len
        reasoning, answer = split_reasoning(
            tok.decode(out[0][prompt_len:], skip_special_tokens=True)
        )
        message: dict[str, Any] = {"role": "assistant", "content": answer}
        if reasoning:
            message["reasoning_content"] = reasoning
        return {
            "id": "chatcmpl-ref",
            "object": "chat.completion",
            "model": _STATE["name"],
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": "length" if new_len >= max_new else "stop",
                }
            ],
            "usage": {"prompt_tokens": prompt_len, "completion_tokens": new_len},
        }

    return app


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--model", required=True, help="prepared snapshot path (sparkrun renders {model})")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--context-length", type=int, default=32768,
                    help="prompt cap for this reference serve; the checkpoint claims 524288")
    ap.add_argument("--served-model-name", default=None,
                    help="name reported by /v1/models; sparkrun's vllm runtime appends it too")
    args = ap.parse_args()
    load(args.model, args.served_model_name, args.context_length)
    uvicorn.run(build(), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
