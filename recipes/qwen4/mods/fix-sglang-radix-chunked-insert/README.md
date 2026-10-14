---
name: fix-sglang-radix-chunked-insert
description: >
  Stop the hybrid (Mamba/GDN) radix cache from inserting chunked-prefill KV pages that a
  retraction can still free — the corruption behind sglang#38319's "!!!!" decode loop.
---

# Why this mod exists

`MambaRadixCache.cache_unfinished_req()` inserts **each prefill chunk's** KV pages into
the radix tree while the request is still in flight. If that request is subsequently
retracted or aborted, `cache_finished_req()` frees those pages — but the radix tree
still references them. The next request that shares the prefix then reads pages
belonging to a dead request and decodes an impossible token forever: the "!!!!" loop,
token id 0 / 248319 (sgl-project/sglang#38319).

Upstream fix is the closed PR sgl-project/sglang#38355 (andreasknopke): for chunked
prefill, skip the insert and defer it to `cache_finished_req`.

This mod applies that fix as anchored, idempotent source edits, gated by
`SGLANG_DISABLE_CHUNKED_RADIX_INSERT` (default `1` = fix on; `0` restores stock
behaviour).

## Provenance and license

This is a **port of third-party code**, not original work. It is adapted from
`mods/sglang-radix-chunked-insert-fix/run.sh` in
<https://github.com/ursuciprian/qwen3.8-flash-next-dgx-spark-tp-2> (Apache-2.0), which
is itself a port of sgl-project/sglang#38355. Upstream copyright and the Apache-2.0
notice are retained in `run.sh`, and the changes we made to it are stated there. Do not
strip those headers.

## Anchor verification against our container

Verified `VERIFIED` before adopting, inside
`lmsysorg/sglang:dev-cu13-qwen38-next-local@sha256:9d2a843c…` (branch
`qwen4-main-squashed`, HEAD `9b2aee2283`): all four anchors match **exactly once** in
`srt/mem_cache/{cache_init_params,kv_cache_builder,mamba_radix_cache}.py`. That is not
luck — our container is on the very branch #38355 was based on. The mod refuses to
write anything if any anchor matches 0 or ≥2 times, and refuses to half-apply.

## What this is NOT

It is a **quality/correctness** fix, not a performance one. Deferring inserts gives up
some prefix reuse *within* a long chunked prefill, so prefill throughput for multi-chunk
requests could drop slightly. Treat any decode-tok/s change here as noise unless it
exceeds our established inter-boot spread. Its value is that it removes a whole class of
silent wrong-output failures, which no tok/s number measures.
