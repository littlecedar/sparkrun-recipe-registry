#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Reference serve for shashanth-27xA9/Kimi-K3.1-Pro-SuperExpert-12GB.

Why this exists
---------------
No serving engine loads this checkpoint (see README.md): its `architectures` entry
`KimiK31SuperExpertForCausalLM` exists only in the repo's own `auto_map`, vLLM/SGLang must have the
architecture in their registries, and the shipped GGUF carries zero tensors. The only loader that can
construct it is transformers' `AutoModelForCausalLM(..., trust_remote_code=True)`, so this arm is a
REFERENCE probe: a small OpenAI-compatible surface over that loader, one request at a time.

What it does NOT pretend to be: the weights are U8 nibble-packed and dequantized inside
`forward()`, so decode speed is Python-bound and every number this serve produces is a
correctness probe, never a serving benchmark.

Endpoints: GET /health, GET /v1/models, POST /v1/completions (raw prompt). /v1/chat/completions
returns 400: the repo's tokenizer_config carries no chat_template, so there is nothing to render.
"""
from __future__ import annotations

import argparse
import json
import os
import threading

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from transformers import AutoTokenizer

TAG = "[kimi-superexpert-ref]"
_LOCK = threading.Lock()
_STATE: dict[str, object] = {}


class Completion(BaseModel):
    model: str | None = None
    prompt: str
    max_tokens: int = 256
    temperature: float = 0.0
    top_p: float = 0.9


def load(model_path: str, served_name: str | None = None) -> None:
    from transformers import AutoModelForCausalLM

    print(f"{TAG} loading {model_path} (trust_remote_code, fp16, reference route only)", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path, trust_remote_code=True, torch_dtype=torch.float16
    ).to("cuda").eval()
    _STATE.update(tokenizer=tokenizer, model=model)
    name = served_name or os.environ.get("SERVED_MODEL_NAME") or "Kimi-K3.1-Pro-SuperExpert-12GB"
    _STATE["name"] = name
    print(f"{TAG} ready: served name {name!r}, no chat template (completions only)", flush=True)


def build() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok" if _STATE.get("model") is not None else "loading"}

    @app.get("/v1/models")
    def models():
        return {"object": "list", "data": [{"id": _STATE.get("name", ""), "object": "model"}]}

    @app.post("/v1/chat/completions")
    def chat(_body: dict):
        raise HTTPException(
            status_code=400,
            detail="no chat template in this repo's tokenizer_config; POST raw prompts to /v1/completions",
        )

    @app.post("/v1/completions")
    def completions(body: Completion):
        tok = _STATE["tokenizer"]
        model = _STATE["model"]
        with _LOCK:
            inputs = tok(body.prompt, return_tensors="pt").to("cuda")
            with torch.no_grad():
                out = model.generate(
                    **inputs,
                    max_new_tokens=body.max_tokens,
                    do_sample=body.temperature > 0,
                    temperature=max(body.temperature, 1e-5),
                    top_p=body.top_p,
                    pad_token_id=tok.pad_token_id,
                )
            text = tok.decode(out[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
        return JSONResponse(
            {
                "object": "text_completion",
                "model": _STATE.get("name", ""),
                "choices": [{"index": 0, "text": text, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": int(inputs["input_ids"].shape[-1])},
            }
        )

    return app


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--model", required=True, help="prepared snapshot path (sparkrun renders {model})")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--context-length", type=int, default=8192,
                    help="reference serve cap; the checkpoint's config claims 1M but attention is dense")
    ap.add_argument("--served-model-name", default=None,
                    help="name reported by /v1/models; sparkrun's vllm runtime appends it")
    args = ap.parse_args()
    print(f"{TAG} context cap {args.context_length} (dense SDPA attention, reference route)", flush=True)
    load(args.model, args.served_model_name)
    uvicorn.run(build(), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
