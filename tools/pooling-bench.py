#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Load/latency client for vLLM *pooling* endpoints (/v1/embeddings, /v2/embed, /v1/score).

Why this file exists
--------------------
sparkrun's benchmarking plugins (`benchmarking/*.yaml`, `framework: llama-benchy`, and
`tool-eval-bench`) all drive `/chat/completions`.  A pooling engine has no chat endpoint, so
no `benchmarking/*.yaml` profile measures an embedding or reranker server at all, and the
framework's "no measured rows" path is a *skip*, not an error -- a wasted run looks like a
clean one.  This is the stopgap: a small concurrent client that produces p50/p90/p99,
requests/s, tokens/s, and an error breakdown for the endpoints those plugins cannot reach.
See recipes/qwen3/QWEN3-EMBED-OPTIMIZATION-WORK.md §5 ("Instrumentation gap").

Why it is not just `curl`
-------------------------
`curl` answers "did it return 200".  Every interesting failure in this model family returns
200.  So the checks that matter are baked in here rather than left to the operator:

* Which prompt path was actually exercised (§2 F11).  A plain `{"input": "..."}` body on
  `/v1/embeddings` resolves to EmbeddingCompletionRequest and takes the *un-instructed*
  base pooling path: no chat template, none of the checkpoint's trained instruction.  It
  returns plausible 2048-dim vectors computed from a prompt the model was never trained on.
  The default mode here is therefore an instructed one, the shape is printed in every
  report header, and the shape is hashed so two reports can be proven comparable.
* Embedding dimension (--dimension-check), two-different-inputs-must-differ, and
  same-input-twice-must-match.
* Rerank near-uniform score vectors (a wiring defect wearing a 200 OK) and a rank-inversion
  check against a built-in fixture whose correct order is not debatable.

Everything is host-agnostic: the only way a target gets here is `--base-url`.  Nothing in
this file knows about any machine, network, or cluster.

Stdlib only, on purpose -- this has to run on a head node, inside a container, and on a
laptop with no venv.  asyncio for concurrency, a hand-rolled HTTP/1.1 client on top of
asyncio streams for the request path (see "Transport" below for why not urllib).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import math
import os
import random
import re
import ssl
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

VERSION = "0.1"

# ---------------------------------------------------------------------
# Defaults and thresholds
# ---------------------------------------------------------------------

#: The encoder's trained instruction, from the checkpoint's
#: config_sentence_transformers.json (prompts.default).  Overridable with --instruction.
DEFAULT_INSTRUCTION = "Represent the user's input."

#: 1_Pooling/config.json says embedding_dimension: 2048 for the 2B encoder.  Pass 0 to
#: disable the check when pointing at a model of another size.
DEFAULT_DIMENSION = 2048

#: Rerank scores whose max-min spread is below this are "near-uniform".  vLLM's score
#: endpoint returns classifier activations, usually in [0, 1] for a 2-way softmax reranker,
#: so a whole document set inside 1e-3 of each other means the template/classifier wiring
#: is wrong (§2 F7, F8), not that the documents are all equally good.
DEFAULT_UNIFORM_EPS = 1e-3

#: Cosine distance above which a repeated identical input is considered "not reproducible".
#: bf16 pooling plus batching leaves a small but non-zero floor; 1e-3 is generous.
DEFAULT_STABILITY_EPS = 1e-3
# Swapping query and document on a real cross-encoder moves the score by far more than
# this. A bi-encoder's dot product is exactly symmetric, so it moves by float noise only.
# Kept tight on purpose: a false "asymmetric" verdict is the one failure mode that would
# wave through the F7 bi-encoder bug.
DEFAULT_ASYM_EPS = 1e-4

#: Cosine distance below which two *different* inputs are considered identical.  Deliberately
#: tiny: this is a "the server is returning a constant vector" detector, not a semantic one.
IDENTICAL_EPS = 1e-9

#: --requests below this prints the noise-floor warning.  The repo's own boot-check.yaml is
#: explicit that "a single run at a single depth resolves nothing"; same idea, same reason.
NOISE_FLOOR_REQUESTS = 30

#: Chars per token used to hit --input-tokens.  Rough English heuristic on a BPE-ish
#: tokenizer; it is an *approximation knob* only.  usage.prompt_tokens from the server is
#: the ground truth and is reported alongside the target.
CHARS_PER_TOKEN = 4.0

#: Fixed corpus for generated payloads.  Word choice is arbitrary; what matters is that it
#: is stable across runs and that a seeded shuffle of it produces distinct, non-degenerate
#: text.  Do not "improve" this list without re-seeding: it changes every past baseline.
CORPUS = (
    "archive bridge calculus database ethernet firewall gateway hardware ingress "
    "junction kernel latency middleware namespace observability pagination query "
    "routing scheduling throughput universe virtualization websocket exception "
    "fraction histogram integer jitter keyword literal modular nested operator "
    "parallel queue recursion scalar temporal unsigned variance algorithm binary "
    "compile datatype expression float grammar hash index journal keyword lambda "
    "matrix noun object pattern rational subset token unary vector witness axiom "
    "batch cluster daemon entropy fork garbage heap inode journal kernel linker "
    "mount namespace opcode page quota root socket thread uptime vfs wait zero"
).split()

#: Built-in rerank fixture.  The expected order must be obvious to a human without a model:
#: a direct answer, a topically-adjacent non-answer, and something irrelevant.  The rank
#: check asserts the full order, so this is a real inversion detector and not a vibe check.
RANK_FIXTURE_QUERY = "What is the capital of France?"
RANK_FIXTURE_DOCS = [
    "The capital of France is Paris.",
    "France is a country in Western Europe.",
    "The best pizza recipe uses mozzarella, fresh basil, and tomato sauce.",
]

# Exit codes.  Distinct on purpose: "the server errored" and "the server answered
# confidently and wrongly" are different pages in a runbook.
EXIT_OK = 0
EXIT_TRANSPORT = 1
EXIT_USAGE = 2
EXIT_CHECK_FAILED = 3

# ---------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile.  No numpy, and no interpolation lies either."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    # Nearest-rank-with-upward-bias: pct=50 on 10 samples gives the 5th of 10 (0-indexed 4).
    rank = max(0, min(len(ordered) - 1, math.ceil(pct / 100.0 * len(ordered)) - 1))
    return ordered[rank]


def cosine_distance(a: list[float], b: list[float]) -> float:
    """1 - cosine similarity.  0.0 for parallel vectors, 2.0 for opposite."""
    if len(a) != len(b):
        raise ValueError(f"vector length mismatch: {len(a)} vs {len(b)}")
    dot = norm_a = norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        # A zero vector has no direction; treat it as maximally unlike anything else so a
        # dead pooler never "passes" the stability check by outputting zeros.
        return 1.0
    return 1.0 - dot / math.sqrt(norm_a * norm_b)


def sha256_short(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def fmt_ms(seconds: float) -> str:
    return f"{seconds * 1000.0:.2f} ms"


def word(fmt: str, ok: bool) -> str:
    return fmt.format("PASS" if ok else "FAIL")


# ---------------------------------------------------------------------
# Payload generation (deterministic from --seed)
# ---------------------------------------------------------------------


def make_text(rng: random.Random, target_tokens: int, tag: str = "") -> str:
    """Pseudo-text of roughly `target_tokens` tokens.

    Not English prose and not meant to be: it must be tokenizable, distinct per draw, and
    byte-identical between runs at the same seed.  `tag` is prepended so that "the same
    input twice" and "two different inputs" are unambiguous even at seed boundaries.
    """
    words = max(1, int(target_tokens * 0.75))
    parts = []
    if tag:
        parts.append(tag)
    parts.extend(rng.choice(CORPUS) for _ in range(words))
    text = " ".join(parts)
    # Aim at the token target by character count; the server's own usage is the truth.
    target_chars = max(1, int(target_tokens * CHARS_PER_TOKEN))
    while len(text) < target_chars:
        parts.append(rng.choice(CORPUS))
        text = " ".join(parts)
    return text[:target_chars]


def make_texts(seed: int, count: int, target_tokens: int, salt: bool = False) -> list[str]:
    """`count` pseudo-texts. With `salt`, every text is unique even at an identical seed.

    Determinism is normally the point here (same seed => same payloads => two runs are
    comparable), so `salt` is off by default and deliberately opt-in. When it is on, each
    text gets a random token so a server with prefix caching cannot answer it from KV —
    which is what you want when measuring masks or memory caps, and *not* what you want
    when comparing two runs of the same configuration against each other.
    """
    rng = random.Random(seed)
    out = []
    for i in range(count):
        tag = f"s{seed}"
        if salt:
            # os.urandom, not rng: the whole purpose is to defeat reproducibility of the
            # *content*, and a seeded RNG would faithfully reproduce the same "unique"
            # texts on the next run and reintroduce exactly the reuse being avoided.
            tag += f"-u{os.urandom(8).hex()}"
        out.append(make_text(rng, target_tokens, tag=tag))
    return out


def _prom_val(line: str) -> float | None:
    """Parse the trailing value off a Prometheus exposition line."""
    try:
        return float(line.rsplit(" ", 1)[1])
    except (IndexError, ValueError):
        return None


# Metric names for the in-process prefix cache.  vLLM exports both
# vllm:prefix_cache_hits_total (the local KV radix cache) and
# vllm:external_prefix_cache_hits_total (a KV connector, 0.0 on a single node), and the two
# share a suffix -- so substring matching reads the wrong one.  These patterns are used with
# .match(), which is start-anchored, so the namespace is matched explicitly: an optional
# `<ns>:`, then the suffix anchored at the end.  That accepts `vllm:prefix_...` and a bare
# `prefix_...`, and rejects `vllm:external_prefix_...` because `external_` is not inside the
# optional namespace group.
_LOCAL_PREFIX_HITS = re.compile(r"(?:[\w.-]+:)?prefix_cache_hits_total\Z")
_LOCAL_PREFIX_QUERIES = re.compile(r"(?:[\w.-]+:)?prefix_cache_queries_total\Z")


# ---------------------------------------------------------------------
# Request shapes
# ---------------------------------------------------------------------
#
# Each builder returns (path, payload).  `shape_of()` returns a template of the same call
# with placeholders instead of data, which is what gets printed in the report header and
# hashed.  The hash is the point: two reports with the same shape hash measured the same
# code path, which is the only defence we have against quietly comparing an instructed run
# against an un-instructed one.


MODES = ("embed-v1-chat", "embed-v1-raw", "embed-v2")


def build_embed_request(
    mode: str,
    model: str,
    texts: list[str],
    instruction: str,
    image_url: str | None,
) -> tuple[str, dict]:
    """One request carrying `texts`.  Returns (path, payload)."""
    if mode == "embed-v1-raw":
        # UN-INSTRUCTED.  Kept because it is the shape everyone reaches for by default and
        # because A/B-ing it against the instructed shapes is exactly the experiment §5
        # item 2b asks for.  It is never the default.
        if image_url:
            raise ValueError("embed-v1-raw cannot carry an image; use --mode embed-v1-chat or embed-v2")
        return "/v1/embeddings", {"model": model, "input": list(texts), "encoding_format": "float"}

    if mode == "embed-v1-chat":
        if len(texts) != 1:
            # /v1/embeddings chat form carries exactly one conversation per request, so
            # batching is impossible here; main() clamps --batch to 1 for this mode.
            raise ValueError("embed-v1-chat carries one conversation per request (batch must be 1)")
        text = texts[0]
        if image_url:
            # Multimodal chat input: content is a part list.  Needs a chat template on the
            # server that knows how to render it, same caveat as any VLM embed.
            content: object = [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": text},
            ]
        else:
            content = text
        payload = {
            "model": model,
            # VERIFIED against the pinned vLLM (b40673cd0) on hardware: the chat form of
            # /v1/embeddings takes `input` as a LIST of messages, not an object with a
            # `messages` key. EmbeddingChatInputRequest declares
            # `input: list[ChatCompletionMessageParam]`, and a nested {"messages": [...]}
            # is rejected with a 400 listing every EmbeddingCompletionRequest alternative.
            # Sending the list is what makes `sparkrun`-style `--instructed` traffic work;
            # the before-validator then copies it into `messages` internally.
            "input": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": content},
            ],
            "encoding_format": "float",
        }
        return "/v1/embeddings", payload

    if mode == "embed-v2":
        if image_url:
            payload = {
                "model": model,
                "input_type": "default",
                "inputs": [
                    {
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_url}},
                            {"type": "text", "text": text},
                        ]
                    }
                    for text in texts
                ],
                "embedding_types": ["float"],
            }
        else:
            payload = {
                "model": model,
                "input_type": "default",
                "texts": list(texts),
                "embedding_types": ["float"],
            }
        return "/v2/embed", payload

    raise ValueError(f"unknown mode: {mode}")


def build_score_request(
    model: str,
    query: str,
    documents: list[str],
    image_url: "str | None | list[str]",
) -> tuple[str, dict]:
    """One /v1/score request: one query against N documents.

    With an image, documents become content-part objects (vLLM's multimodal score input
    shape), and the query stays a plain string.

    `image_url` may be a single URL (the same image on every document) or a list with one
    entry per document. Passing a list is what makes --synthetic-images meaningful, and the
    reason it must be per-document rather than per-request is arithmetic, not taste: each
    (query, document) pair is scored as its own sequence, so with one shared image all N
    pairs begin with the same query plus the same ~1240-token image placeholder run. At N=10
    that shared prefix is roughly 80% of each sequence, so the KV radix cache answers almost
    the whole benchmark from one cached image -- which is how the first image-throughput
    number came out 82% cache-served while every image looked distinct at request level.
    """
    if isinstance(image_url, list):
        if len(image_url) != len(documents):
            raise ValueError(
                f"image_url list has {len(image_url)} entries for {len(documents)} documents"
            )
        images = image_url
    else:
        images = [image_url] * len(documents)
    if images and images[0] is not None:
        docs: list = [
            {
                "content": [
                    {"type": "image_url", "image_url": {"url": img}},
                    {"type": "text", "text": doc},
                ]
            }
            for doc, img in zip(documents, images)
        ]
    else:
        docs = list(documents)
    return "/v1/score", {"model": model, "queries": query, "documents": docs}


def shape_of(mode: str, multimodal: str) -> str:
    """Canonical, data-free template of the embed request -- printed and hashed."""
    if mode == "embed-v1-raw":
        obj = {"model": "<model>", "input": ["<text>", "..."], "encoding_format": "float"}
        return json.dumps(obj, indent=2, sort_keys=False)
    if mode == "embed-v1-chat":
        user: object = "<text>"
        if multimodal == "image":
            user = [
                {"type": "image_url", "image_url": {"url": "<image-url>"}},
                {"type": "text", "text": "<text>"},
            ]
        obj = {
            "model": "<model>",
            # Must mirror build_embed_request(): `input` is a LIST of messages (see there).
            "input": [
                {"role": "system", "content": "<instruction>"},
                {"role": "user", "content": user},
            ],
            "encoding_format": "float",
        }
        return json.dumps(obj, indent=2, sort_keys=False)
    if mode == "embed-v2":
        if multimodal == "image":
            obj = {
                "model": "<model>",
                "input_type": "default",
                "inputs": [
                    {
                        "content": [
                            {"type": "image_url", "image_url": {"url": "<image-url>"}},
                            {"type": "text", "text": "<text>"},
                        ]
                    },
                    "...",
                ],
                "embedding_types": ["float"],
            }
        else:
            obj = {
                "model": "<model>",
                "input_type": "default",
                "texts": ["<text>", "..."],
                "embedding_types": ["float"],
            }
        return json.dumps(obj, indent=2, sort_keys=False)
    raise ValueError(f"unknown mode: {mode}")


def score_shape_of(multimodal: str) -> str:
    docs: object = ["<document>", "..."]
    if multimodal == "image":
        docs = [
            {
                "content": [
                    {"type": "image_url", "image_url": {"url": "<image-url>"}},
                    {"type": "text", "text": "<document>"},
                ]
            },
            "...",
        ]
    return json.dumps({"model": "<model>", "queries": "<query>", "documents": docs}, indent=2)


# ---------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------


def parse_embeddings(obj: object, path: str) -> tuple[list[list[float]], int | None]:
    """Pull vectors + prompt-token count out of a v1 or v2 embed response.

    Returns (vectors, prompt_tokens).  Raises ValueError with a usable message when the
    shape is not one of the two we know, because a silently empty vector list would make
    every downstream check pass vacuously.
    """
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: response is not a JSON object")

    # OpenAI shape: {"data": [{"embedding": [...]}], "usage": {...}}
    if "data" in obj:
        data = obj.get("data")
        if not isinstance(data, list) or not data:
            raise ValueError(f"{path}: 'data' is empty -- server returned no vectors")
        vectors = []
        for i, item in enumerate(data):
            if not isinstance(item, dict) or "embedding" not in item:
                raise ValueError(f"{path}: data[{i}] has no 'embedding'")
            emb = item["embedding"]
            if isinstance(emb, str):
                # encoding_format base64 would land here; we always ask for float, so a
                # string means the server ignored the request field.  Decode it rather than
                # fail, but only because the bytes are unambiguous.
                emb = list(struct_unpack_float32_le(base64.b64decode(emb)))
            if not isinstance(emb, list):
                raise ValueError(f"{path}: data[{i}]['embedding'] is {type(emb).__name__}")
            vectors.append([float(x) for x in emb])
        return vectors, prompt_tokens_of(obj)

    # Cohere shape: {"embeddings": {"float": [[...]]}, "meta": {...}}
    if "embeddings" in obj:
        emb = obj["embeddings"]
        if isinstance(emb, dict):
            rows = emb.get("float")
            if rows is None:
                raise ValueError(f"{path}: embeddings has no 'float' key (asked for float)")
        else:
            rows = emb
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{path}: 'embeddings' is empty")
        return [[float(x) for x in row] for row in rows], prompt_tokens_of(obj)

    keys = ",".join(sorted(obj))[:120]
    raise ValueError(f"{path}: unrecognized response shape (keys: {keys})")


def prompt_tokens_of(obj: dict) -> int | None:
    """prompt_tokens where the server bothers to report it (v1 usage / v2 billed_units)."""
    usage = obj.get("usage")
    if isinstance(usage, dict):
        for key in ("prompt_tokens", "total_tokens"):
            value = usage.get(key)
            if isinstance(value, int):
                return value
    meta = obj.get("meta")
    if isinstance(meta, dict):
        billed = meta.get("billed_units")
        if isinstance(billed, dict) and isinstance(billed.get("input_tokens"), int):
            return billed["input_tokens"]
    return None


def parse_scores(obj: object, path: str) -> tuple[list[float], int | None]:
    """Pull per-document scores (in request order) from a scoring response.

    Two response shapes are legal and they are NOT interchangeable (vLLM
    entrypoints/pooling/scoring/protocol.py):
      /v1/score   -> ScoreResponse   {"data":   [{"index", "score"}],            "usage"}
      /v1/rerank  -> RerankResponse  {"results": [{"index", "relevance_score"}],  "usage"}
    Accepting both here means one code path covers both endpoints; it does NOT mean the two
    endpoints are the same request. /v1/score takes `queries`+`documents`, /v1/rerank takes
    `query`+`documents`+`top_n`. Sending the wrong body gets a 422, which is why the shape is
    built per-endpoint in build_score_request rather than shared.
    """
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: response is not a JSON object")
    for key, field in (("data", "score"), ("results", "relevance_score")):
        rows = obj.get(key)
        if isinstance(rows, list) and rows:
            pairs = []
            for i, item in enumerate(rows):
                if not isinstance(item, dict) or field not in item:
                    raise ValueError(f"{path}: {key}[{i}] has no '{field}'")
                index = item.get("index", i)
                pairs.append((index if isinstance(index, int) else i, float(item[field])))
            pairs.sort(key=lambda p: p[0])
            return [score for _, score in pairs], prompt_tokens_of(obj)
    raise ValueError(
        f"{path}: no score list found -- expected 'data'/'score' (/v1/score) or "
        f"'results'/'relevance_score' (/v1/rerank); keys present: {sorted(obj)[:8]}"
    )


def check_symmetry(pairs: list[tuple[float, float]], eps: float) -> Check:
    """Detect a reranker that is secretly a bi-encoder, without any ground truth.

    A cross-encoder (what Qwen3-VL-Reranker is when wired correctly: --convert classify +
    the yes/no 2-way softmax over a (query, document) prompt) is an *asymmetric* function:
    score(A as query, B as document) and score(B as query, A as document) are different
    numbers, because the two texts occupy different slots in the prompt.

    A bi-encoder is a dot product of independently-encoded vectors, so it is *symmetric*:
    swapping query and document cannot change the score. That is exactly what vLLM serves
    when the architecture rewrite is missing and --convert auto resolves to `embed`
    (SCORE_TYPE_MAP: embed -> bi-encoder). §2 F7.

    So: if swapping query and document leaves every score unchanged, the reranker is
    answering as an embedding model. No fixture, no labels, no ground truth required --
    it falls out of the arithmetic. This is the cheapest trustworthy F7 check there is.
    """
    if not pairs:
        return Check("cross-encoder-symmetry", False, "no probe pairs completed", fatal=True)
    worst = max(abs(a - b) for a, b in pairs)
    symmetric = worst <= eps
    detail = (
        f"{len(pairs)} swapped pairs, max |score(A,B) - score(B,A)| = {worst:.3e} "
        f"(asymmetry threshold {eps:.1e})"
    )
    if symmetric:
        detail += (
            " -- SYMMETRIC: this is behaving like a bi-encoder, i.e. an embedding model "
            "answering /v1/score. Check hf_overrides architectures + --convert classify "
            "and the launch log's 'Resolved architecture:' line (§2 F7)."
        )
    else:
        detail += " -- asymmetric, consistent with a cross-encoder."
    return Check("cross-encoder-symmetry", not symmetric, detail, fatal=True)


def struct_unpack_float32_le(blob: bytes) -> tuple[float, ...]:
    """base64 embedding decode.  Isolated so the `struct` import stays local and obvious."""
    import struct

    n = len(blob) // 4
    return struct.unpack(f"<{n}f", blob[: 4 * n])


# ---------------------------------------------------------------------
# Quality checks (the reason this is not curl)
# ---------------------------------------------------------------------


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    #: A warn-severity check prints but never changes the exit code.
    fatal: bool = True

    def to_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "fatal": self.fatal, "detail": self.detail}


def check_dimension(vectors: list[list[float]], expected: int) -> Check:
    if expected <= 0:
        return Check("dimension", True, "skipped (--dimension-check 0)", fatal=True)
    bad = [(i, len(v)) for i, v in enumerate(vectors) if len(v) != expected]
    if bad:
        got = sorted({length for _, length in bad})
        return Check(
            "dimension",
            False,
            f"{len(bad)} of {len(vectors)} vectors are not {expected}-dim (got {got})",
        )
    return Check("dimension", True, f"all {len(vectors)} vectors are {expected}-dim")


def check_distinct(vectors: list[list[float]], labels: list[str]) -> Check:
    """Two different inputs must not produce the same vector."""
    if len(vectors) < 2:
        return Check("distinct-inputs", True, "skipped (need 2 vectors)", fatal=False)
    worst = -1.0
    worst_pair = ""
    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            dist = cosine_distance(vectors[i], vectors[j])
            if dist < worst or worst < 0:
                worst, worst_pair = dist, f"{labels[i]} vs {labels[j]}"
    ok = worst > IDENTICAL_EPS
    detail = f"min cosine distance {worst:.3e} ({worst_pair})"
    if not ok:
        detail += " -- identical vectors for different inputs: the pooler is degenerate"
    return Check("distinct-inputs", ok, detail)


def check_stability(a: list[float], b: list[float], eps: float) -> Check:
    dist = cosine_distance(a, b)
    ok = dist <= eps
    detail = f"same input twice: cosine distance {dist:.3e} (tolerance {eps:.1e})"
    if not ok:
        detail += " -- non-reproducible embeddings; batch-composition effects or a race"
    return Check("stability", ok, detail)


def check_uniform(scores: list[float], eps: float, label: str) -> Check:
    """Near-uniform score vector => the rerank wiring is wrong, not the documents."""
    if len(scores) < 2:
        return Check(f"uniform[{label}]", True, "skipped (fewer than 2 documents)", fatal=False)
    spread = max(scores) - min(scores)
    ok = spread > eps
    detail = f"{len(scores)} scores, spread {spread:.3e} (threshold {eps:.1e})"
    if not ok:
        detail += " -- near-uniform: check --chat-template / --convert / hf_overrides (§2 F7-F8)"
    return Check(f"uniform[{label}]", ok, detail, fatal=False)


def check_rank(scores: list[float]) -> Check:
    """Order the fixture documents the way a competent reader would.

    Expected order is 0 > 1 > 2.  We report every inverted pair, because "top-1 is right but
    1 and 2 are swapped" is a different finding from "the ranking is random".
    """
    if len(scores) != len(RANK_FIXTURE_DOCS):
        return Check("rank-fixture", False, f"expected {len(RANK_FIXTURE_DOCS)} scores, got {len(scores)}")
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    inversions = [
        f"{a}>{b}"
        for a in range(len(scores))
        for b in range(a + 1, len(scores))
        if scores[a] <= scores[b]
    ]
    detail = f"observed order {order} (expected {[i for i in range(len(scores))]}), scores " + ", ".join(
        f"{s:.6f}" for s in scores
    )
    if inversions:
        detail = f"inverted pairs {inversions}; " + detail
    return Check("rank-fixture", not inversions, detail)


# ---------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------
#
# Why a hand-rolled client instead of urllib.request in a thread pool:
#   1. A thread pool adds GIL scheduling to the measurement path of a latency benchmark,
#      which is precisely the quantity being reported.
#   2. urllib has no keep-alive, so every sample would include a TCP handshake and the
#      numbers would describe the loopback stack rather than the server.
# It is ~120 lines, POST-only, and handles the two framings vLLM's uvicorn actually uses
# (Content-Length and chunked).  TLS is supported; anything past that (proxies, HTTP/2,
# unix sockets) is out of scope for a stopgap.


class TransportError(RuntimeError):
    """Connection framing failure before any response byte.  Safe to retry once."""


@dataclass
class Reply:
    status: int
    reason: str
    body: bytes
    elapsed: float
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status < 300

    @property
    def status_label(self) -> str:
        return self.error or str(self.status)


class Connection:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, hostport: str):
        self.reader = reader
        self.writer = writer
        self.hostport = hostport
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:  # noqa: BLE001 - closing a dead socket is not an interesting error
            pass

    async def exchange(self, path: str, payload: dict, headers: dict[str, str], timeout: float) -> Reply:
        body = json.dumps(payload).encode("utf-8")
        request = [
            f"POST {path} HTTP/1.1",
            f"Host: {self.hostport}",
            "User-Agent: sparkrun-pooling-bench/" + VERSION,
            "Accept: application/json",
            "Content-Type: application/json",
            "Content-Length: {}".format(len(body)),
            "Connection: keep-alive",
        ]
        request.extend(f"{key}: {value}" for key, value in headers.items())
        raw = ("\r\n".join(request) + "\r\n\r\n").encode("ascii") + body

        t0 = time.perf_counter()
        try:
            self.writer.write(raw)
            await self.writer.drain()
            status, reason, resp_headers, version = await asyncio.wait_for(self._read_head(), timeout)
            payload_bytes = await asyncio.wait_for(self._read_body(status, resp_headers), timeout)
        except (TransportError, ConnectionError, asyncio.IncompleteReadError, TimeoutError, OSError) as exc:
            await self.aclose()
            raise TransportError(f"{type(exc).__name__}: {exc}") from exc
        elapsed = time.perf_counter() - t0
        # "No Connection: close header" is NOT proof the peer will keep this socket open.
        # An HTTP/1.0 response is implicitly close unless the server says keep-alive, and
        # servers that do say so (uvicorn/vLLM) answer HTTP/1.1. Treating silence as
        # keep-alive pooled sockets that the peer had already finished with, and every
        # later request then paid a guaranteed transport error -- see the retry note in
        # PoolClient.post for why that was unrecoverable.
        conn_hdr = resp_headers.get("connection", "").lower()
        if version >= (1, 1):
            keep = conn_hdr != "close"
        else:
            keep = conn_hdr == "keep-alive"
        keep = keep and status != 408
        reply = Reply(status, reason, payload_bytes, elapsed)
        reply.error = None
        if not keep:
            await self.aclose()
        return reply

    async def _read_head(self) -> tuple[int, str, dict[str, str], tuple[int, int]]:
        line = await self.reader.readline()
        if not line:
            raise TransportError("peer closed the connection before responding (idle keep-alive reap)")
        parts = line.decode("latin-1").strip().split(" ", 2)
        if len(parts) < 2 or not parts[0].upper().startswith("HTTP/"):
            raise TransportError(f"malformed status line: {line[:80]!r}")
        # HTTP version matters for keep-alive semantics, so parse it rather than dropping it.
        try:
            version = tuple(int(x) for x in parts[0][5:].split(".", 1))
        except ValueError:
            version = (1, 0)
        try:
            status = int(parts[1])
        except ValueError as exc:
            raise TransportError(f"non-numeric status: {parts[1]!r}") from exc
        reason = parts[2] if len(parts) > 2 else ""
        headers: dict[str, str] = {}
        while True:
            header = await self.reader.readline()
            if header in (b"\r\n", b"\n", b""):
                break
            key, _, value = header.decode("latin-1").partition(":")
            headers[key.strip().lower()] = value.strip()
        return status, reason, headers, version

    async def _read_body(self, status: int, headers: dict[str, str]) -> bytes:
        if status in (204, 304):
            return b""
        if headers.get("transfer-encoding", "").lower().find("chunked") >= 0:
            chunks = []
            while True:
                size_line = await self.reader.readline()
                if not size_line:
                    raise TransportError("truncated chunk stream")
                size = int(size_line.split(b";")[0].strip() or b"0", 16)
                if size == 0:
                    # Trailing headers, if any, run until a blank line.
                    while True:
                        trailer = await self.reader.readline()
                        if trailer in (b"\r\n", b"\n", b""):
                            break
                    break
                chunks.append(await self.reader.readexactly(size))
                await self.reader.readexactly(2)  # CRLF after each chunk
            return b"".join(chunks)
        length = headers.get("content-length")
        if length is not None:
            return await self.reader.readexactly(int(length))
        # No framing at all: the server intends to close, so read to EOF.
        return await self.reader.read()


class PoolClient:
    """POST-only keep-alive pool sized to the requested concurrency."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None,
        timeout: float,
        concurrency: int,
        keepalive: bool = True,
        tls_insecure: bool = False,
    ):
        parts = urlsplit(base_url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError(f"--base-url must be http(s)://host:port[/prefix], got {base_url!r}")
        self.scheme = parts.scheme
        self.host = parts.hostname
        self.port = parts.port or (443 if parts.scheme == "https" else 80)
        # A base URL ending in /v1 is the OpenAI convention and means the same origin to us,
        # because /v2/embed does not live under /v1.  Strip it rather than produce /v1/v2/embed.
        prefix = parts.path.rstrip("/")
        if prefix.endswith("/v1"):
            prefix = prefix[: -len("/v1")]
        self.prefix = prefix
        self.hostport = self.host if self.port in (80, 443) else f"{self.host}:{self.port}"
        self.timeout = timeout
        self.keepalive = keepalive
        self.tls_insecure = tls_insecure
        self._headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        self._conns: list[Connection] = []
        self._sem = asyncio.Semaphore(max(1, concurrency))
        self._max = max(1, concurrency)
        self.connect_failures = 0
        # How many times a transport error forced us to discard the whole idle pool. A
        # high count against a real server is not an error, it is information: the server
        # is reaping keep-alive connections aggressively, and --no-keepalive may measure
        # more honestly than the pool does.
        self.pool_drops = 0

    def url_for(self, path: str) -> str:
        return f"{self.scheme}://{self.hostport}{self.prefix}{path}"

    async def _open(self) -> Connection:
        ssl_ctx = None
        if self.scheme == "https":
            ssl_ctx = ssl.create_default_context()
            if self.tls_insecure:
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port, ssl=ssl_ctx), self.timeout
        )
        return Connection(reader, writer, self.hostport)

    async def _borrow(self) -> Connection:
        while self._conns:
            conn = self._conns.pop()
            if not conn.closed:
                return conn
        return await self._open()

    def _give(self, conn: Connection) -> None:
        if self.keepalive and not conn.closed and len(self._conns) < self._max:
            self._conns.append(conn)
        else:
            asyncio.get_running_loop().create_task(conn.aclose())

    async def post(self, path: str, payload: dict) -> Reply:
        """POST with one retry.

        The retry exists for exactly one case: the server reaped an idle keep-alive
        connection between requests, so our first write hits a socket the peer already
        finished with. That is normal and expected against uvicorn/vLLM after any pause.

        Retrying only helps if the *next* connection is fresh. The first version of this
        closed the failed socket (which `Connection.exchange` already does) but left every
        other idle socket in the pool alone -- and when the server reaps on an idle
        timeout it reaps all of them, so attempt 2 popped another dead socket from the
        pool and failed identically. The retry was structurally incapable of working,
        which showed up as 'the warmup pass succeeded and then every probe failed'.

        So: on a transport error, throw away the whole idle pool. Reconnecting a handful of
        sockets is cheap; a benchmark that silently reports zero measured requests is not.
        """
        full = f"{self.prefix}{path}"
        async with self._sem:
            last_error = "unknown"
            for attempt in (1, 2):
                try:
                    conn = await self._borrow()
                except (OSError, asyncio.TimeoutError) as exc:
                    self.connect_failures += 1
                    return Reply(0, "", b"", 0.0, error=f"connect failed: {type(exc).__name__}")
                try:
                    reply = await conn.exchange(full, payload, self._headers, self.timeout)
                except TransportError as exc:
                    last_error = str(exc)
                    if attempt == 1:
                        self.pool_drops += 1
                        await self._drop_idle()
                    continue
                if not conn.closed:
                    self._give(conn)
                return reply
            return Reply(0, "", b"", 0.0, error=f"transport: {last_error}")

    async def get(self, path: str) -> Reply:
        """One-shot GET, for /metrics only.

        Deliberately not pooled and deliberately not routed through `Connection.exchange`:
        that helper is on the load path and always sends a JSON body, and bending it to
        cover a control-plane request would risk the thing being measured for a report
        string. This opens a socket, reads one response, and closes it.
        """
        t0 = time.perf_counter()
        ssl_ctx = None
        if self.scheme == "https":
            ssl_ctx = ssl.create_default_context()
            if self.tls_insecure:
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port, ssl=ssl_ctx), self.timeout
            )
        except (OSError, asyncio.TimeoutError) as exc:
            return Reply(0, "", b"", 0.0, error=f"connect failed: {type(exc).__name__}")
        try:
            lines = [
                f"GET {self.prefix}{path} HTTP/1.1",
                f"Host: {self.hostport}",
                "User-Agent: sparkrun-pooling-bench/" + VERSION,
                "Accept: text/plain, application/openmetrics-text",
                "Connection: close",
            ]
            lines += [f"{k}: {v}" for k, v in self._headers.items() if k == "Authorization"]
            writer.write(("\r\n".join(lines) + "\r\n\r\n").encode("ascii"))
            await writer.drain()
            conn = Connection(reader, writer, self.hostport)
            status, reason, resp_headers, _v = await asyncio.wait_for(conn._read_head(), self.timeout)
            body = await asyncio.wait_for(conn._read_body(status, resp_headers), self.timeout)
            return Reply(status, reason, body, time.perf_counter() - t0)
        except (TransportError, ConnectionError, asyncio.IncompleteReadError, TimeoutError, OSError) as exc:
            return Reply(0, "", b"", time.perf_counter() - t0, error=f"{type(exc).__name__}: {exc}")
        finally:
            try:
                writer.close()
            except Exception:
                pass

    async def prefix_cache_hits(self) -> tuple[float, float] | None:
        """Return (hits, queries) from /metrics, or None if unavailable.

        Why this is worth a code path: vLLM enables prefix caching by default for these
        checkpoints, so a benchmark that reuses a corpus mostly measures KV residency
        rather than the thing it claims to vary. On one recorded run that produced a 4x
        throughput swing between two protocols on an *identically configured* server, with
        repeats inside each protocol agreeing to under 1%. Reporting the hit rate is the
        cheapest way to tell a real result from a cache artifact.
        """
        reply = await self.get("/metrics")
        if not reply.ok:
            return None
        try:
            text = reply.body.decode("utf-8", "replace")
        except UnicodeDecodeError:
            return None
        hits = queries = None
        for line in text.splitlines():
            if line.startswith("#"):
                continue
            name = line.split("{", 1)[0].split(" ", 1)[0].strip()
            # Match the namespace-qualified name, rejecting any `_`-prefixed variant.
            # A `name.endswith(...)` test is wrong here and was wrong in the first version
            # of this method: vLLM also exports vllm:external_prefix_cache_{hits,queries}_
            # total, which also ends with "prefix_cache_hits_total" and is 0.0 on a
            # single-node box. With endswith, the external zeroes silently overwrote the
            # local counters and the tool reported a confident "0.0% cache-served" for a
            # server whose real hit rate was 68%.  A leading `_` rejects `external_` while
            # still accepting any namespace a fork might use.
            if _LOCAL_PREFIX_HITS.match(name):
                hits = _prom_val(line)
            elif _LOCAL_PREFIX_QUERIES.match(name):
                queries = _prom_val(line)
        if hits is None or queries is None:
            return None
        return hits, queries

    async def _drop_idle(self) -> None:
        """Close every idle socket. Called when the peer has proved it is not honouring
        keep-alive on the connections we are holding."""
        conns, self._conns = self._conns, []
        for conn in conns:
            await conn.aclose()

    async def aclose(self) -> None:
        for conn in self._conns:
            await conn.aclose()
        self._conns.clear()


# ---------------------------------------------------------------------
# Load generation
# ---------------------------------------------------------------------


@dataclass
class Outcome:
    """Everything we want to know about one completed exchange."""

    latency: float
    status: str
    ok: bool
    prompt_tokens: int | None = None
    units: int = 0  # texts embedded, or documents scored
    vectors: list[list[float]] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    note: str = ""


@dataclass
class RunResult:
    outcomes: list[Outcome] = field(default_factory=list)
    errors: Counter[str] = field(default_factory=Counter)
    parse_errors: list[str] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    wall_seconds: float = 0.0
    units: int = 0  # texts or documents actually processed
    prompt_tokens: int = 0
    tokens_reported_by_server: bool = False
    # Prefix-cache hit rate over the measured window, when /metrics was readable.
    # (hits_delta, queries_delta) -- see PoolClient.prefix_cache_hits for why this matters.
    prefix_cache: tuple[float, float] | None = None

    @property
    def requests_total(self) -> int:
        return len(self.outcomes)

    @property
    def requests_ok(self) -> int:
        return sum(1 for o in self.outcomes if o.ok)

    @property
    def errors_total(self) -> int:
        return sum(1 for o in self.outcomes if not o.ok)

    def latencies(self) -> list[float]:
        return [o.latency for o in self.outcomes if o.ok]

    def to_dict(self) -> dict:
        lat = self.latencies()
        return {
            "version": VERSION,
            "requests_total": self.requests_total,
            "requests_ok": self.requests_ok,
            "errors": dict(self.errors),
            "parse_errors": self.parse_errors[:20],
            "wall_seconds": round(self.wall_seconds, 6),
            "units": self.units,
            "prompt_tokens": self.prompt_tokens,
            "tokens_server_reported": self.tokens_reported_by_server,
            "latency_ms": {
                "p50": round(percentile(lat, 50) * 1000, 3) if lat else None,
                "p90": round(percentile(lat, 90) * 1000, 3) if lat else None,
                "p99": round(percentile(lat, 99) * 1000, 3) if lat else None,
                "max": round(max(lat) * 1000, 3) if lat else None,
                "mean": round((sum(lat) / len(lat)) * 1000, 3) if lat else None,
            },
            "checks": [c.to_dict() for c in self.checks],
        }


def make_samplers(
    client: PoolClient,
    jobs: list[tuple[str, dict, int, str]],
    on_reply: Callable[[Outcome], None] | None = None,
) -> list[Callable[[], Coroutine]]:
    """Turn (path, payload, units, kind) tuples into coroutine factories.

    Factories, not coroutines: the rerank fixture pass re-runs the same job shape, and a
    coroutine cannot be awaited twice.

    `run_one` BOTH calls `on_reply` (if the caller wants a live sink, e.g. a progress hook)
    AND returns the Outcome. It has to return it: `drive()` is the thing that owns the
    RunResult, and a one-argument callback that drive cannot see is exactly how every
    measured request used to be silently discarded -- the report printed
    "0 ok / 0 failed (total 0)" against a server that had answered all of them. An
    instrument that reports nothing while the thing it measures is working is the worst
    kind of instrument, which is why this is spelled out here.
    """

    async def run_one(path: str, payload: dict, units: int, kind: str) -> Outcome:
        reply = await client.post(path, payload)
        if not reply.ok:
            outcome = Outcome(reply.elapsed, reply.status_label, False, note="request failed")
        else:
            try:
                obj = json.loads(reply.body.decode("utf-8") or "null")
                if kind == "score":
                    scores, prompt_tokens = parse_scores(obj, path)
                    vectors: list[list[float]] = []
                else:
                    vectors, prompt_tokens = parse_embeddings(obj, path)
                    scores = []
                outcome = Outcome(
                    reply.elapsed,
                    str(reply.status),
                    True,
                    prompt_tokens=prompt_tokens,
                    units=units,
                    vectors=vectors,
                    scores=scores,
                )
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                outcome = Outcome(reply.elapsed, str(reply.status), False, note=f"parse: {exc}")
        if on_reply is not None:
            on_reply(outcome)
        return outcome

    return [(lambda p=p, d=d, u=u, k=k: run_one(p, d, u, k)) for p, d, u, k in jobs]


async def drive(
    client: PoolClient,
    samplers: list[Callable[[], Coroutine]],
    *,
    repeats: int = 1,
) -> RunResult:
    """Run every sampler `repeats` times, respecting the client's concurrency semaphore."""
    result = RunResult()

    def record(outcome: Outcome) -> None:
        result.outcomes.append(outcome)
        if outcome.ok:
            result.units += outcome.units
            if outcome.prompt_tokens is not None:
                result.prompt_tokens += outcome.prompt_tokens
                result.tokens_reported_by_server = True
        else:
            result.errors[outcome.status] += 1
            if outcome.note.startswith("parse:"):
                result.parse_errors.append(outcome.note)

    tasks = [sampler() for _ in range(max(1, repeats)) for sampler in samplers]
    t0 = time.perf_counter()
    outcomes = await asyncio.gather(*tasks)
    result.wall_seconds = time.perf_counter() - t0
    for outcome in outcomes:
        record(outcome)
    # A sampler that returns None means somebody re-wrote run_one to stop returning its
    # Outcome. Fail here rather than reporting a clean-looking empty measurement window.
    if tasks and any(o is None for o in outcomes):
        raise RuntimeError(
            "internal error: samplers returned no Outcome; the measurement window would be "
            "silently empty (see make_samplers). Refusing to report."
        )
    return result


# ---------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------


def render_header(cfg: dict, shape_text: str, mode_note: str) -> None:
    print("sparkrun pooling-bench " + VERSION)
    print("=" * 72)
    print(f"  target        : {cfg['base_url']}  ({cfg['scheme_host_port']})")
    print(f"  model         : {cfg['model']}")
    print(f"  mode          : {cfg['mode']}   {mode_note}")
    print(f"  api key       : {cfg['api_key_source']}")
    print(f"  concurrency   : {cfg['concurrency']}   requests: {cfg['requests']}   warmup: {cfg['warmup']}")
    print(f"  inputs        : {cfg['input_desc']}   seed: {cfg['seed']}   timeout: {cfg['timeout']}s")
    print(f"  auth sent     : {'yes' if cfg['api_key_sent'] else 'no'} (never printed)")
    print()
    print("  EXACT REQUEST SHAPE USED (placeholders in <angle brackets>):")
    for line in shape_text.rstrip().splitlines():
        print("    " + line)
    print(f"  shape sha256  : {sha256_short(shape_text)}   <- two reports with the same hash"
          " measured the same code path")
    if cfg["instruction_shown"] is not None:
        print(f"  instruction   : {cfg['instruction_shown']!r}")
    print()


def noise_floor_warning(requests: int) -> bool:
    return requests < NOISE_FLOOR_REQUESTS


def render_result(result: RunResult, cfg: dict) -> None:
    lat = result.latencies()
    print("  ---- results " + "-" * 58)
    print(f"  requests      : {result.requests_ok} ok / {result.errors_total} failed"
          f" (total {result.requests_total})")
    if result.errors:
        breakdown = ", ".join(f"{status}={n}" for status, n in sorted(result.errors.items()))
        print(f"  status/errors : {breakdown}")
    else:
        print("  status/errors : none")
    for note in result.parse_errors[:3]:
        print(f"  parse error   : {note[:200]}")
    if lat:
        print(f"  latency p50   : {fmt_ms(percentile(lat, 50))}")
        print(f"  latency p90   : {fmt_ms(percentile(lat, 90))}")
        print(f"  latency p99   : {fmt_ms(percentile(lat, 99))}")
        print(f"  latency max   : {fmt_ms(max(lat))}")
        print(f"  latency mean  : {fmt_ms(sum(lat) / len(lat))}")
    else:
        print("  latency       : no successful requests -- nothing to report")
    if result.wall_seconds > 0:
        rps = result.requests_ok / result.wall_seconds
        ups = result.units / result.wall_seconds
        print(f"  wall time     : {result.wall_seconds:.3f} s")
        # Two separate labelled lines, not one line with two numbers in it. The previous
        # form -- "24.23 requests/s (2000 units in 8.254 s)" -- was read as a single
        # quantity often enough to corrupt a comparison, because requests and score
        # "units" (requests x docs-per-query) differ by docs_per_query and a reader
        # comparing two runs can easily take requests/s from one and the parenthetical
        # from the other. Label both, and say what a unit is.
        print(f"  throughput    : {rps:.2f} requests/s   [{result.requests_ok} requests in"
              f" {result.wall_seconds:.3f} s]")
        print(f"  unit throughput: {ups:.2f} units/s"
              f"   [{result.units} units = texts or documents, NOT requests]")
        if result.tokens_reported_by_server and result.prompt_tokens:
            tps = result.prompt_tokens / result.wall_seconds
            print(f"  tokens/s      : {tps:.1f} (prompt_tokens as reported by the server,"
                  f" total {result.prompt_tokens})")
        else:
            print("  tokens/s      : unavailable -- the server reported no usage counts;"
                  " requests/s and units/s are still valid")
    if result.prefix_cache is not None:
        hits, queries = result.prefix_cache
        rate = (hits / queries) if queries else 0.0
        line = (f"  prefix cache  : {rate:.1%} of {queries:.0f} token-chunks served from KV"
                f" during the measured window")
        # A high hit rate is the signature of measuring KV residency instead of the
        # variable under test, so say so in the line where it is visible.
        if rate >= 0.25:
            line += (" -- HIGH: this run is largely cache-served, so compare only against"
                     " other --salt runs and treat absolute throughput as unrepeatable")
        elif queries == 0:
            line += " -- no chunks seen; did the server expose both counters?"
        print(line)
    print()


def render_checks(checks: list[Check], heading: str = "anti-silent-wrong-answer checks") -> int:
    """Print checks and return the number of failed *fatal* checks."""
    print(f"  ---- {heading} " + "-" * max(0, 58 - len(heading)))
    fatal_failures = 0
    for check in checks:
        if check.ok:
            print(f"  [ PASS ] {check.name}: {check.detail}")
        elif check.fatal:
            print(f"  [ FAIL ] {check.name}: {check.detail}")
            fatal_failures += 1
        else:
            print(f"  [ WARN ] {check.name}: {check.detail}")
    if fatal_failures:
        print()
        print("  *** FAIL: at least one check that cannot be waved through did not pass.")
        print("  *** A 200 OK is not a pass. Read the detail above before trusting anything")
        print("  *** in the results block.")
    return fatal_failures


def footer(requests: int, kind: str = "measure") -> None:
    if kind == "smoke":
        print()
        print("  NOISE FLOOR: smoke is one request per shape. It proves the endpoints answer")
        print("  and the vectors/scores are shaped right; it says nothing about performance.")
        print("  Use `embed`/`rerank` with a real --requests count for that.")
        return
    if noise_floor_warning(requests):
        print()
        print("  NOISE FLOOR: --requests is small. Single-digit request counts resolve")
        print("  nothing -- one run at one depth proves only that it boots (same reasoning")
        print("  as benchmarking/boot-check.yaml). Treat every latency number above as an")
        print(f"  anecdote. Use --requests {NOISE_FLOOR_REQUESTS}+ and compare medians of")
        print("  repeated runs before believing a delta.")


# ---------------------------------------------------------------------
# Workloads
# ---------------------------------------------------------------------


_SYNTHETIC_PNG_MODULE = None


def _synthetic_png_module():
    """Load tools/synthetic_png.py once, by sibling path.

    Loaded by path rather than by name because this file is run three ways -- as a script,
    by path from a recipe, and from tests via importlib -- and in none of those cases can we
    assume tools/ is on sys.path. Path is taken from __file__, which is correct in all three.
    """
    global _SYNTHETIC_PNG_MODULE
    if _SYNTHETIC_PNG_MODULE is None:
        import importlib.util

        path = Path(__file__).resolve().parent / "synthetic_png.py"
        if not path.exists():
            raise SystemExit(f"image synthesis needs {path}, which is missing")
        spec = importlib.util.spec_from_file_location("synthetic_png", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["synthetic_png"] = module
        spec.loader.exec_module(module)
        _SYNTHETIC_PNG_MODULE = module
    return _SYNTHETIC_PNG_MODULE


def _synthetic_image_url(width: int, height: int, nonce: str) -> str:
    """A tiny PNG with genuinely distinct pixels, as a data: URL.

    The cache-busting mechanism has to change the image CONTENT, not its URL. That is not a
    style preference; it is what the hardware showed. A previous version of this function
    appended a random query string to the configured image URL, on the theory that the
    server's multimodal cache is keyed by URL. It is not. Re-running the identical benchmark
    with 450 distinct URLs produced an identical 81.5% prefix-cache hit rate and moved
    `mm_cache_hits_total` from 448 to 898 -- every new request hit the cache, because the
    fetched bytes were identical and the cache hashes content. URL mutation is inert here, and
    pretending otherwise would produce a confidently wrong throughput number.

    Solid-colour PNGs are used because they are ~250 base64 chars at 64x64 and ~7 KB at
    480x640 -- smaller on the wire than one photograph -- while still presenting the vision
    encoder with the same patch grid. Encoder and prefill cost is driven by the patch count
    (sequence length), not by image entropy, so a flat image is a fair proxy for capacity.
    It is NOT a proxy for realistic attention over real content: a flat image may score oddly,
    and what this measures is throughput headroom, not retrieval quality.
    """
    solid_data_url = _synthetic_png_module().solid_data_url
    # Three channels all vary with the nonce so distinct nonces give distinct bytes; the xor
    # keeps the blue channel from tracking green too closely. A collision in 24-bit colour
    # space is possible but vanishing for the few hundred images a run generates, and a
    # collision costs one cache hit, not a wrong answer.
    seed = int.from_bytes(hashlib.sha256(nonce.encode()).digest()[:3], "big")
    rgb = ((seed >> 16) & 0xFF, (seed >> 8) & 0xFF, (seed & 0xFF) ^ 0x5A)
    return solid_data_url(width, height, rgb)


def effective_image_urls(cfg: dict, count: int) -> "str | None | list[str]":
    """Image URL for one job's documents.

    Returns a LIST of `count` URLs when --synthetic-images is set, one distinct PNG per
    document, because sharing a single image across a request's documents re-creates the
    prefix-cache reuse we are trying to remove (see build_score_request). Without
    --synthetic-images the configured URL is returned unchanged; note that with --salt alone
    the TEXT is unique but every document still shares one image, which is the configuration
    whose 81.5% hit rate made the first image-throughput figure unusable (work doc §7 item 3).
    """
    if cfg.get("synthetic_images"):
        w, h = cfg.get("synthetic_size") or (480, 640)
        return [_synthetic_image_url(w, h, os.urandom(8).hex()) for _ in range(count)]
    return cfg.get("image_url")


def jobs_embed(cfg: dict, texts: list[str]) -> list[tuple[str, dict, int, str]]:
    jobs = []
    batch = cfg["batch"]
    for start in range(0, len(texts), batch):
        chunk = texts[start : start + batch]
        path, payload = build_embed_request(
            cfg["mode"], cfg["model"], chunk, cfg["instruction"], cfg["image_url"]
        )
        jobs.append((path, payload, len(chunk), "embed"))
    return jobs


def jobs_rerank(cfg: dict, n: int) -> list[tuple[str, dict, int, str]]:
    rng = random.Random(cfg["seed"])
    jobs = []
    for req_no in range(n):
        # See make_texts for why salt uses os.urandom rather than the seeded rng.
        nonce = f"-u{os.urandom(8).hex()}" if cfg.get("salt") else ""
        query = make_text(rng, max(8, cfg["input_tokens"] // 8),
                          tag=f"q{cfg['seed']}-{req_no}{nonce}")
        docs = [
            make_text(rng, cfg["input_tokens"], tag=f"d{i}{cfg['seed']}-{req_no}{nonce}")
            for i in range(cfg["docs_per_query"])
        ]
        path, payload = build_score_request(cfg["model"], query, docs,
                                            effective_image_urls(cfg, len(docs)))
        jobs.append((path, payload, len(docs), "score"))
    return jobs


def collect_vectors(result: RunResult, limit: int = 8) -> list[list[float]]:
    vectors = []
    for outcome in result.outcomes:
        vectors.extend(outcome.vectors)
        if len(vectors) >= limit:
            break
    return vectors[:limit]


def embed_checks(cfg: dict, result: RunResult, probe: list[list[float]] | None) -> list[Check]:
    checks: list[Check] = []
    measured = collect_vectors(result)
    inspectable = measured + (probe or [])
    if not inspectable:
        checks.append(Check("dimension", False, "no vectors returned to inspect"))
        checks.append(Check("distinct-inputs", False, "no vectors returned to inspect"))
        checks.append(Check("stability", False, "no vectors returned to inspect", fatal=False))
        return checks
    checks.append(check_dimension(inspectable, cfg["dimension_check"]))
    if probe and len(probe) >= 3:
        a, a_dup, b = probe[0], probe[1], probe[2]
        checks.append(check_distinct([a, b], ["probe A", "probe B"]))
        checks.append(check_stability(a, a_dup, cfg["stability_eps"]))
    else:
        # The probes could not run; fall back to the weaker in-band version so a partially
        # alive server still yields a verdict instead of a hole in the report.
        checks.append(check_distinct(measured[:2], ["v0", "v1"]))
        checks.append(
            Check("stability", False, "repeat probes did not complete; cannot assess", fatal=False)
        )
    return checks


def score_checks(cfg: dict, result: RunResult, fixture_scores: list[float] | None) -> list[Check]:
    checks: list[Check] = []
    if fixture_scores is not None:
        checks.append(check_uniform(fixture_scores, cfg["uniform_eps"], "fixture"))
        checks.append(check_rank(fixture_scores))
    else:
        checks.append(Check("rank-fixture", False, "fixture request never returned a score"))
        checks.append(Check("uniform[fixture]", False, "fixture request never returned a score"))
    measured = [o.scores for o in result.outcomes if o.ok and len(o.scores) >= 2]
    if not measured:
        checks.append(
            Check("uniform[measured]", False, "no measured response carried >=2 scores", fatal=False)
        )
        return checks
    spreads = [max(s) - min(s) for s in measured]
    near_uniform = sum(1 for s in spreads if s <= cfg["uniform_eps"])
    all_uniform = near_uniform == len(measured)
    checks.append(
        Check(
            "uniform[measured]",
            not all_uniform,
            f"{near_uniform}/{len(measured)} responses had a spread <= {cfg['uniform_eps']:.1e}"
            " (near-uniform scores mean the template/classifier wiring is wrong, §2 F7-F8)",
            fatal=all_uniform or cfg["fail_on_uniform"],
        )
    )
    return checks


async def _prefix_cache_delta(cfg: dict, client: PoolClient, result: RunResult) -> None:
    """Attach (hits_delta, queries_delta) to `result` if the flag is set and /metrics works.

    Reads /metrics before and after the measured window only, so warmup and the correctness
    probes do not inflate the denominator. Silently leaves the field None when the server
    has no /metrics or exposes neither counter: this is diagnostic, and a benchmark that
    fails because a metrics endpoint is disabled would be a worse tool than one that
    reports nothing.
    """
    if not cfg.get("report_prefix_cache"):
        return
    before = await client.prefix_cache_hits()
    if before is None:
        return
    # `result` is already populated by the caller's drive(); the caller re-invokes this
    # after the window, so only the "after" read happens here.
    after = await client.prefix_cache_hits()
    if after is None:
        return
    result.prefix_cache = (after[0] - before[0], after[1] - before[1])


async def measure_with_prefix_cache(cfg: dict, client: PoolClient, run):
    """Run `run()` and bracket only the measured window with /metrics reads.

    `run` is passed a callback to stash the before-read, because the before/after reads
    have to straddle drive() and not the probes.
    """
    return await run()


async def run_embed(cfg: dict) -> RunResult:
    client = make_client(cfg)
    try:
        total_texts = cfg["requests"] * cfg["batch"]
        texts = make_texts(cfg["seed"], max(2, total_texts), cfg["input_tokens"],
                           salt=bool(cfg.get("salt")))
        jobs = jobs_embed(cfg, texts)
        # Order: warmup -> unmeasured probes -> measured window.  Probing after warmup means
        # the probe is not paying for a cold cache, and probing before the measurement means
        # the probe's latency never enters the distribution.
        if cfg["warmup"] > 0:
            await drive(client, make_samplers(client, jobs[:1], lambda o: None), repeats=cfg["warmup"])
        probe = await probe_embed_async(cfg, client, texts)
        before = await client.prefix_cache_hits() if cfg.get("report_prefix_cache") else None
        result = await drive(client, make_samplers(client, jobs, lambda o: None))
        if before is not None:
            after = await client.prefix_cache_hits()
            if after is not None:
                result.prefix_cache = (after[0] - before[0], after[1] - before[1])
        result.checks = embed_checks(cfg, result, probe)
        return result
    finally:
        await client.aclose()


async def probe_embed_async(cfg: dict, client: PoolClient, texts: list[str]) -> list[list[float]] | None:
    """Unmeasured correctness probes: same input twice, and two different inputs.

    Three sequential requests, deliberately outside the measured window: a probe inside the
    sample both pollutes p99 and makes "same input twice" tautological.  Sequential on
    purpose -- gather() would complete in nondeterministic order and the labels (A, A-dup,
    B) are the whole meaning of the check.  Returns None if any probe failed.
    """
    vectors: list[list[float]] = []
    for text in (texts[0], texts[0], texts[1]):
        path, payload = build_embed_request(
            cfg["mode"], cfg["model"], [text], cfg["instruction"], cfg["image_url"]
        )
        reply = await client.post(path, payload)
        if not reply.ok:
            return None
        try:
            obj = json.loads(reply.body.decode("utf-8") or "null")
            got, _ = parse_embeddings(obj, path)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not got:
            return None
        vectors.append(got[0])
    return vectors


async def _swapped_pair_scores(
    client: PoolClient, cfg: dict
) -> tuple[list[tuple[float, float]], list[str]]:
    """Score (A,B) and (B,A) for a few pairs; return (score_pairs, notes).

    A cross-encoder must give different numbers; a bi-encoder cannot. See check_symmetry.
    Uses /v1/rerank when available because that is the endpoint whose name promises a
    cross-encoder, falling back to /v1/score. Both are accepted by parse_scores.
    """
    pairs: list[tuple[float, float]] = []
    notes: list[str] = []
    a, b = RANK_FIXTURE_DOCS[0], RANK_FIXTURE_DOCS[2]
    for first, second in ((RANK_FIXTURE_QUERY, a), (RANK_FIXTURE_QUERY, b), (a, b)):
        forward = await _one_score(client, cfg, first, [second])
        backward = await _one_score(client, cfg, second, [first])
        if forward is None or backward is None:
            notes.append(f"probe({first[:24]!r} <-> {second[:24]!r}) incomplete")
            continue
        pairs.append((forward[0], backward[0]))
    return pairs, notes


async def _one_score(client: PoolClient, cfg: dict, query: str, docs: list[str]) -> list[float] | None:
    path, payload = build_score_request(cfg["model"], query, docs,
                                        effective_image_urls(cfg, len(docs)))
    reply = await client.post(path, payload)
    if not reply.ok:
        return None
    try:
        obj = json.loads(reply.body.decode("utf-8") or "null")
        scores, _ = parse_scores(obj, path)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return scores or None


async def run_rerank(cfg: dict) -> RunResult:
    client = make_client(cfg)
    try:
        fixture_path, fixture_payload = build_score_request(
            cfg["model"], RANK_FIXTURE_QUERY, RANK_FIXTURE_DOCS,
            # Use the same image source as the measured traffic. Reading cfg["image_url"]
            # directly would silently drop the image whenever --synthetic-images is set
            # (that flag nulls image_url), and the rank/uniform checks would then certify
            # the text path while the report header claims multimodal.
            effective_image_urls(cfg, len(RANK_FIXTURE_DOCS)),
        )
        fixture_scores: list[float] | None = None

        async def fixture_probe() -> None:
            nonlocal fixture_scores
            reply = await client.post(fixture_path, fixture_payload)
            if reply.ok:
                try:
                    obj = json.loads(reply.body.decode("utf-8") or "null")
                    fixture_scores, _ = parse_scores(obj, fixture_path)
                except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
                    fixture_scores = None

        await fixture_probe()
        jobs = jobs_rerank(cfg, cfg["requests"])
        if cfg["warmup"] > 0:
            await drive(client, make_samplers(client, jobs[:1], lambda o: None), repeats=cfg["warmup"])
        # Bracket the measured window only. The before/after reads are two extra HTTP
        # requests, each on its own short-lived socket, so they never touch the pooled
        # connections the load rides on.
        pc_before = await client.prefix_cache_hits() if cfg.get("report_prefix_cache") else None
        result = await drive(client, make_samplers(client, jobs, lambda o: None))
        if pc_before is not None:
            pc_after = await client.prefix_cache_hits()
            if pc_after is not None:
                result.prefix_cache = (pc_after[0] - pc_before[0], pc_after[1] - pc_before[1])
        # The symmetry probe runs AFTER the measured window so its traffic cannot land in
        # the latency percentiles; it is a correctness check, not a load sample.
        pairs, notes = await _swapped_pair_scores(client, cfg)
        result.checks = score_checks(cfg, result, fixture_scores)
        symmetry = check_symmetry(pairs, cfg["asymmetry_eps"])
        if notes:
            symmetry.detail += "; " + "; ".join(notes)
        result.checks.append(symmetry)
        return result
    finally:
        await client.aclose()


def make_client(cfg: dict) -> PoolClient:
    return PoolClient(
        cfg["base_url"],
        api_key=cfg["api_key"],
        timeout=cfg["timeout"],
        concurrency=cfg["concurrency"],
        keepalive=cfg["keepalive"],
        tls_insecure=cfg["tls_insecure"],
    )


# ---------------------------------------------------------------------
# Smoke mode
# ---------------------------------------------------------------------
#
# One request to every pooling shape, printed as a table.  It is deliberately four rows and
# not three: /v1/embeddings appears twice, un-instructed and instructed, so the operator can
# see with their own eyes that both answer 200 with the same dimension while only one of them
# took the path the model was trained on (§2 F11).  That equivalence at the HTTP level is
# precisely why this needs to be a tool and not a curl.


SMOKE_ROWS = (
    ("/v1/embeddings un-instructed", "embed-v1-raw"),
    ("/v1/embeddings instructed   ", "embed-v1-chat"),
    ("/v2/embed instructed        ", "embed-v2"),
)


async def run_smoke(cfg: dict) -> tuple[list[Check], dict]:
    client = make_client(cfg)
    rows: list[Check] = []
    summary = {"vectors": [], "scores": []}
    try:
        text = make_text(random.Random(cfg["seed"]), cfg["input_tokens"], tag=f"smoke{cfg['seed']}")
        for label, mode in SMOKE_ROWS:
            path, payload = build_embed_request(
                mode, cfg["model"], [text], cfg["instruction"], cfg["image_url"]
            )
            rows.append(await smoke_embed_row(client, path, payload, label, cfg))
        fixture_path, fixture_payload = build_score_request(
            cfg["model"], RANK_FIXTURE_QUERY, RANK_FIXTURE_DOCS,
            # Use the same image source as the measured traffic. Reading cfg["image_url"]
            # directly would silently drop the image whenever --synthetic-images is set
            # (that flag nulls image_url), and the rank/uniform checks would then certify
            # the text path while the report header claims multimodal.
            effective_image_urls(cfg, len(RANK_FIXTURE_DOCS)),
        )
        reply = await client.post(fixture_path, fixture_payload)
        rows.append(await smoke_score_row(reply, fixture_path, cfg))
        return rows, summary
    finally:
        await client.aclose()


async def smoke_embed_row(
    client: PoolClient, path: str, payload: dict, label: str, cfg: dict
) -> Check:
    reply = await client.post(path, payload)
    if not reply.ok:
        return Check(label.strip(), False, f"HTTP {reply.status_label} in {fmt_ms(reply.elapsed)}")
    try:
        obj = json.loads(reply.body.decode("utf-8") or "null")
        vectors, tokens = parse_embeddings(obj, path)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return Check(label.strip(), False, f"{type(exc).__name__}: {exc}")
    lengths = sorted({len(v) for v in vectors})
    detail = f"{len(vectors)} vector(s), dim {lengths}, {fmt_ms(reply.elapsed)}"
    if tokens is not None:
        detail += f", prompt_tokens={tokens}"
    expected = cfg["dimension_check"]
    if expected > 0 and any(length != expected for length in lengths):
        return Check(label.strip(), False, detail + f" -- expected dim {expected}")
    if expected > 0:
        detail += f" (expected dim {expected})"
    return Check(label.strip(), True, detail)


async def smoke_score_row(reply: Reply, path: str, cfg: dict) -> Check:
    if not reply.ok:
        return Check("/v1/score (built-in fixture)", False, f"HTTP {reply.status_label}")
    try:
        obj = json.loads(reply.body.decode("utf-8") or "null")
        scores, _ = parse_scores(obj, path)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return Check("/v1/score (built-in fixture)", False, f"{type(exc).__name__}: {exc}")
    uniform = check_uniform(scores, cfg["uniform_eps"], "fixture")
    rank = check_rank(scores)
    ok = uniform.ok and rank.ok
    return Check("/v1/score (built-in fixture)", ok, f"{uniform.detail}; {rank.detail}")


# ---------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------

EPILOG = """\
examples
  # encoder: instructed chat form (the default), 1 text per request
  pooling-bench.py embed --base-url http://ENCODER:8010 --model Qwen/Qwen3-VL-Embedding-2B \\
      --requests 100 --concurrency 8 --input-tokens 256 --batch 1

  # encoder: Cohere /v2/embed, 16 texts per request, same seed => same payloads
  pooling-bench.py embed --base-url http://ENCODER:8010 --model Qwen/Qwen3-VL-Embedding-2B \\
      --mode embed-v2 --batch 16 --requests 64 --json-out embed-v2.json

  # encoder: the un-instructed body, for A/B-ing the prompt path (see notes below)
  pooling-bench.py embed --base-url http://ENCODER:8010 --model Qwen/Qwen3-VL-Embedding-2B \\
      --mode embed-v1-raw --requests 100

  # reranker: 1 query x 20 documents, and refuse to exit 0 on a uniform score vector
  pooling-bench.py rerank --base-url http://RERANKER:8011 --model Qwen/Qwen3-VL-Reranker-2B \\
      --requests 100 --docs-per-query 20 --concurrency 4 --fail-on-uniform

  # both endpoints, one request each, compact
  pooling-bench.py smoke --base-url http://ENCODER:8010 --model Qwen/Qwen3-VL-Embedding-2B

  # multimodal: an image part in every document/text, image fetched by the SERVER
  pooling-bench.py rerank --base-url http://RERANKER:8011 --model Qwen/Qwen3-VL-Reranker-2B \\
      --multimodal image --image-url https://example.invalid/shot.png --docs-per-query 5

notes
  * --base-url is required and is the ONLY way a target gets here.  No defaults, no config
    file, no hostname baked in.  A /v1 suffix on the URL is stripped, because /v2/embed does
    not live under it.
  * --api-key is read from $VLLM_API_KEY when the flag is absent.  The value is never
    printed, in the report or in --json-out.
  * The prompt path is the point.  /v1/embeddings with a plain {"input": "..."} body takes
    the un-instructed pooling path: no chat template, none of the checkpoint's trained
    instruction, plausible vectors from a prompt the model was not trained on.  The default
    here is --mode embed-v1-chat.  --mode embed-v1-raw exists so you can measure the
    difference, not so you can forget about it.
  * Requests are deterministic given --seed: same seed + same flags => same payloads, so two
    runs are comparable.  The report header carries a sha256 of the request shape; if it
    differs, the two runs are not comparable.
  * Latency is measured client-side around a keep-alive connection pool, so a sample is one
    request/response exchange, not one exchange plus a TCP handshake.  It includes queueing
    at the server and, at --concurrency N, includes contention: it is a wall-clock latency
    under load, which is what you asked for, not a service time.
  * tokens/s is only printed when the server reports usage.  vLLM does on both endpoints; a
    server that strips usage gets requests/s and units/s instead, and no fabricated number.
  * Exit codes: 0 clean, 1 transport/target unreachable, 2 bad flags, 3 a correctness check
    failed.  3 is the interesting one: the server answered 200 and was wrong.

stopgap notice
  This is not a sparkrun benchmarking plugin and is not wired into `sparkrun bench`.  It
  exists because llama-benchy drives /chat/completions and therefore cannot measure a pooling
  recipe at all.  Prefer writing the real plugin.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pooling-bench.py",
        description=(
            "Load/latency client for vLLM pooling endpoints (/v1/embeddings, /v2/embed, "
            "/v1/score), with correctness checks that a 200 OK cannot satisfy."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("mode_kind", choices=("embed", "rerank", "smoke"), help="what to drive")
    parser.add_argument("--base-url", required=True, metavar="URL", help="e.g. http://host:8010 (required; no default)")
    parser.add_argument("--model", required=True, help="served-model-name, usually the HF repo id")
    parser.add_argument("--api-key", default=None, help="bearer token; falls back to $VLLM_API_KEY; never printed")
    parser.add_argument(
        "--mode",
        choices=MODES,
        default="embed-v1-chat",
        help=(
            "embed request shape (default: embed-v1-chat = instructed). embed-v1-raw is the "
            "UN-INSTRUCTED plain body and exists for the A/B, not as a default"
        ),
    )
    parser.add_argument("--concurrency", type=int, default=8, metavar="N", help="in-flight requests (default 8)")
    parser.add_argument("--requests", type=int, default=50, metavar="N", help="measured requests (default 50)")
    parser.add_argument("--batch", type=int, default=1, metavar="N", help="texts per embed request (default 1; forced to 1 for embed-v1-chat)")
    parser.add_argument("--docs-per-query", type=int, default=10, metavar="N", help="documents per rerank request (default 10)")
    parser.add_argument("--input-tokens", type=int, default=128, metavar="N", help="approx tokens per text/document (default 128)")
    parser.add_argument("--multimodal", choices=("off", "image"), default="off", help="add an image part to each text/document")
    parser.add_argument("--image-url", default=None, help="image URL the SERVER fetches; required with --multimodal image")
    parser.add_argument(
        "--synthetic-images",
        action="store_true",
        help=(
            "send a distinct tiny solid-colour PNG per document instead of one shared "
            "--image-url. vLLM's multimodal cache is keyed on image CONTENT, not URL, so a "
            "shared URL means the vision encoder runs once and KV serves the rest: a measured "
            "run of that shape reported 53 units/s behind an 81.5%% prefix-cache hit rate. Use "
            "this for any image-throughput number. Sizes with --synthetic-size WxH "
            "(default 480x640, ~1240 tokens/image on this model)."
        ),
    )
    parser.add_argument(
        "--synthetic-size",
        default=None,
        metavar="WxH",
        help="pixels for --synthetic-images (default 480x640)",
    )
    parser.add_argument("--warmup", type=int, default=2, metavar="N", help="unmeasured requests first (default 2)")
    parser.add_argument("--timeout", type=float, default=60.0, metavar="SEC", help="per-request timeout (default 60)")
    parser.add_argument("--json-out", metavar="PATH", default=None, help="write the machine-readable result here")
    parser.add_argument("--seed", type=int, default=1234, help="payload RNG seed (default 1234)")
    parser.add_argument(
        "--salt",
        action="store_true",
        help=(
            "make every measured request text unique, so prefix caching cannot answer it "
            "from KV. vLLM enables prefix caching by default for these checkpoints, and a "
            "reused corpus mostly measures KV residency rather than the variable under test; "
            "a 4x throughput swing was measured that way between two protocols on an "
            "identically configured server. Use this for any A/B of masks or memory caps, "
            "together with --report-prefix-cache, and expect lower absolute throughput than "
            "a cached run -- that is the point, not a regression."
        ),
    )
    parser.add_argument(
        "--report-prefix-cache",
        action="store_true",
        help="fetch /metrics before and after and report the prefix-cache hit rate delta",
    )
    parser.add_argument("--instruction", default=DEFAULT_INSTRUCTION, help="system-message instruction for the instructed embed forms")
    parser.add_argument(
        "--dimension-check",
        type=int,
        default=DEFAULT_DIMENSION,
        metavar="INT",
        help=f"fail if embedding length != INT (default {DEFAULT_DIMENSION} for the 2B encoder; 0 disables)",
    )
    parser.add_argument(
        "--fail-on-uniform",
        action="store_true",
        help="make a near-uniform measured score vector a hard failure instead of a warning",
    )
    parser.add_argument("--uniform-eps", type=float, default=DEFAULT_UNIFORM_EPS, metavar="EPS", help="near-uniform threshold (default 1e-3)")
    parser.add_argument(
        "--asymmetry-eps",
        type=float,
        default=DEFAULT_ASYM_EPS,
        metavar="EPS",
        help="max |score(A,B) - score(B,A)| that still counts as a bi-encoder (default 1e-4)",
    )
    parser.add_argument("--stability-eps", type=float, default=DEFAULT_STABILITY_EPS, metavar="EPS", help="max cosine distance for the same input twice (default 1e-3)")
    parser.add_argument("--no-keepalive", action="store_true", help="open a fresh connection per request (measures connection setup too)")
    parser.add_argument("--insecure-tls", action="store_true", help="skip TLS certificate verification (lab use)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def resolve_config(args: argparse.Namespace) -> tuple[dict, list[str]]:
    """Validate flags into a cfg dict, returning (cfg, human notes)."""
    problems: list[str] = []
    notes: list[str] = []

    if args.concurrency < 1:
        problems.append("--concurrency must be >= 1")
    if args.requests < 1:
        problems.append("--requests must be >= 1")
    if args.batch < 1:
        problems.append("--batch must be >= 1")
    if args.docs_per_query < 1:
        problems.append("--docs-per-query must be >= 1")
    if args.input_tokens < 1:
        problems.append("--input-tokens must be >= 1")
    if args.timeout <= 0:
        problems.append("--timeout must be > 0")
    if args.warmup < 0:
        problems.append("--warmup must be >= 0")
    synthetic_size = None
    if args.synthetic_size:
        try:
            w_s, h_s = args.synthetic_size.lower().split("x", 1)
            synthetic_size = (int(w_s), int(h_s))
        except ValueError:
            problems.append(f"--synthetic-size must look like 480x640, got {args.synthetic_size!r}")
        else:
            if not (8 <= synthetic_size[0] <= 4096 and 8 <= synthetic_size[1] <= 4096):
                problems.append(f"--synthetic-size {args.synthetic_size} outside 8..4096 per side")
    if args.synthetic_images:
        # --synthetic-images subsumes --image-url: the whole point is to not use a shared URL.
        if args.multimodal == "off":
            notes.append("--synthetic-images implies --multimodal image; enabling it")
        args.multimodal = "image"
        if args.image_url:
            notes.append("--image-url is IGNORED with --synthetic-images (each document gets "
                         "its own generated PNG)")
            args.image_url = None
    elif args.multimodal == "image" and not args.image_url:
        problems.append("--multimodal image requires --image-url (the server fetches it; we "
                        "never do), or --synthetic-images to generate distinct PNGs")
    if args.multimodal == "off" and args.image_url:
        notes.append("--image-url given but --multimodal is off: the image will NOT be sent")
    if args.dimension_check < 0:
        problems.append("--dimension-check must be >= 0 (0 disables)")

    mode = args.mode
    if args.mode_kind == "rerank" and mode != "embed-v1-chat":
        notes.append(f"--mode {mode} is ignored for rerank (score requests have no prompt-path choice)")
    if args.mode_kind == "embed" and mode == "embed-v1-chat" and args.batch > 1:
        notes.append(f"--mode embed-v1-chat carries one conversation per request: --batch forced 1 (was {args.batch})")
    if args.mode_kind == "rerank" and mode == "embed-v1-raw" and args.multimodal == "image":
        problems.append("--mode embed-v1-raw cannot carry an image; use --mode embed-v1-chat or embed-v2")
    if args.mode_kind == "smoke":
        notes.append("smoke drives every shape itself (raw, chat, v2, score); --mode is not used")

    api_key = args.api_key if args.api_key is not None else os.environ.get("VLLM_API_KEY")
    if args.api_key is not None:
        api_key_source = "from --api-key"
    elif api_key:
        api_key_source = "from $VLLM_API_KEY"
    else:
        api_key_source = "none sent"

    batch = 1 if (args.mode_kind == "embed" and mode == "embed-v1-chat") else args.batch
    parts = urlsplit(args.base_url)
    scheme_host_port = f"{parts.scheme}://{parts.hostname or '?'}:{parts.port or (443 if parts.scheme == 'https' else 80)}"

    instructed = mode != "embed-v1-raw"
    mode_note = "(INSTRUCTED: chat template + system instruction)" if mode == "embed-v1-chat" else (
        "(INSTRUCTED: server-applied input_type prefix)" if mode == "embed-v2" else
        ("(n/a for this mode)" if args.mode_kind != "embed" else "*** UN-INSTRUCTED: no chat template, "
         "no trained instruction -- see notes ***")
    )
    if args.mode_kind == "rerank":
        mode_note = "(score requests: one query x N documents; prompt path is the server's --chat-template)"

    input_desc = (
        f"{args.input_tokens} approx tokens/text"
        + (f", {args.docs_per_query} docs/query" if args.mode_kind == "rerank" else f", batch {batch}")
        + (", +1 image part" if args.multimodal == "image" else "")
    )

    cfg = {
        "kind": args.mode_kind,
        "mode": mode,
        "base_url": args.base_url,
        "scheme_host_port": scheme_host_port,
        "model": args.model,
        "api_key": api_key,
        "api_key_sent": bool(api_key),
        "api_key_source": api_key_source,
        "concurrency": args.concurrency,
        "requests": args.requests,
        "batch": batch,
        "docs_per_query": args.docs_per_query,
        "input_tokens": args.input_tokens,
        "multimodal": args.multimodal,
        "image_url": args.image_url if args.multimodal == "image" else None,
        "synthetic_images": bool(args.synthetic_images),
        "synthetic_size": synthetic_size,
        "warmup": args.warmup,
        "timeout": args.timeout,
        "seed": args.seed,
        "salt": args.salt,
        "report_prefix_cache": args.report_prefix_cache,
        "instruction": args.instruction,
        "dimension_check": args.dimension_check,
        "fail_on_uniform": args.fail_on_uniform,
        "uniform_eps": args.uniform_eps,
        "asymmetry_eps": args.asymmetry_eps,
        "stability_eps": args.stability_eps,
        "keepalive": not args.no_keepalive,
        "tls_insecure": args.insecure_tls,
        "json_out": args.json_out,
        "input_desc": input_desc,
        "instructed": instructed,
        "mode_note": mode_note,
    }
    return cfg, notes


# ---------------------------------------------------------------------
# main
# ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg, notes = resolve_config(args)
    if notes:
        for note in notes:
            print(f"note: {note}", file=sys.stderr)
    if cfg["kind"] == "embed" and not cfg["instructed"]:
        print(
            "note: --mode embed-v1-raw measures the UN-INSTRUCTED prompt path. Fine for an "
            "A/B; do not compare its numbers to an instructed run's.",
            file=sys.stderr,
        )

    if cfg["kind"] == "embed":
        shape_text = shape_of(cfg["mode"], cfg["multimodal"])
    elif cfg["kind"] == "rerank":
        shape_text = score_shape_of(cfg["multimodal"])
    else:
        # Each smoke row drives a different request shape, so the header has to show all
        # of them. Flatten to a list of strings -- join() over a generator of *lists*
        # raises TypeError, which is exactly how this line used to fail.
        shape_parts: list[str] = []
        for label, mode in SMOKE_ROWS:
            shape_parts.append("[%s]" % label.strip())
            shape_parts.append(shape_of(mode, "off" if mode == "embed-v1-raw" else cfg["multimodal"]))
        shape_parts.append("[/v1/score (built-in fixture)]")
        shape_parts.append(score_shape_of(cfg["multimodal"]))
        shape_text = "\n".join(shape_parts)
    if cfg["kind"] == "embed" and cfg["mode"] == "embed-v1-chat":
        cfg["instruction_shown"] = cfg["instruction"]
    elif cfg["kind"] == "smoke":
        cfg["instruction_shown"] = cfg["instruction"]
    else:
        cfg["instruction_shown"] = None
    render_header(cfg, shape_text, cfg["mode_note"])

    try:
        if cfg["kind"] == "embed":
            result = asyncio.run(run_embed(cfg))
        elif cfg["kind"] == "rerank":
            result = asyncio.run(run_rerank(cfg))
        else:
            checks, _ = asyncio.run(run_smoke(cfg))
            result = RunResult(checks=checks)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return EXIT_TRANSPORT

    if cfg["kind"] == "smoke":
        # Smoke has one sample per row, so there is no distribution to report: the row
        # details (status, dimension, elapsed) are the output and the checks are the verdict.
        fatal_failures = render_checks(result.checks, heading="smoke: one request per shape")
        requests_for_footer = 1
    else:
        render_result(result, cfg)
        fatal_failures = render_checks(result.checks)
        requests_for_footer = cfg["requests"]
    footer(requests_for_footer)

    if cfg["json_out"]:
        payload = {
            "tool": "sparkrun-pooling-bench",
            "version": VERSION,
            "config": {k: v for k, v in cfg.items() if k != "api_key"},
            "api_key_source": cfg["api_key_source"],
            "request_shape": shape_text,
            "request_shape_sha256": sha256_short(shape_text),
            "noise_floor_warning": noise_floor_warning(cfg["requests"] if cfg["kind"] != "smoke" else 1),
            "result": result.to_dict(),
        }
        try:
            with open(cfg["json_out"], "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
            print(f"\n  json written  : {cfg['json_out']}")
        except OSError as exc:
            print(f"\n  json NOT written: {exc}", file=sys.stderr)
            return EXIT_USAGE

    if fatal_failures:
        return EXIT_CHECK_FAILED
    if cfg["kind"] != "smoke" and result.requests_ok == 0:
        print("\n  no request succeeded -- the target is unreachable or misconfigured")
        return EXIT_TRANSPORT
    if result.errors_total and cfg["kind"] != "smoke":
        return EXIT_TRANSPORT
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
