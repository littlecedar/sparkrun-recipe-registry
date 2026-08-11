# Memory — expert parallelism on DGX Spark / GB10 (single node)

Durable lessons learned while reviewing the qwen3.8-flash-next-nvfp4 spec and
researching single-node MoE serving on GB10.

## EP vs TP / offload on one GB10 box (from Qwen3.8-Flash-Next NVFP4 field notes)

- **One DGX Spark = one GB10 = one unified-memory "node" (128 GB).** There is
  no multi-node PCIe link between the two 46-BP GPUs; they share one CPU/DRAM
  pool. So "expert parallelism" (EP) across the two GPUs is really a
  multi-device split inside a single node.
- **Do NOT run expert parallelism (EP) on GB10.** Field notes explicitly say
  so: with unified memory, host RAM is the same pool as device memory, so
  expert offload to the CPU "saves nothing." And the experts are touched every
  token, so disk paging would thrash. vLLM has no expert-mmap path anyway.
- **Do NOT run expert/offload-based strategies; use tensor parallelism (TP2).**
  The validated default recipe for running this 122 GiB NVFP4 model on a single
  GB10 is plain `tensor-parallel-size=2` (TP1/TP2), no `--enable-expert-parallel`.
- **No CPU/offload gain on unified memory.** Anything that only works because of
  a separate CPU memory pool (CPU offload, `--load-format` offload) is moot.
  The one memory trick that *does* help is **PLE table mmap** (the 44 GiB
  n-gram embedding table is served from NVMe via mmap, not kept resident) and
  **hybrid mode** (FP8 side layers) which saves ~7 GiB more and speeds decode.
- **Spec-env gotcha:** `VLLM_LOAD_FORMAT: offload` is wrong on GB10 (unified
  memory, offload saves nothing). `--load-format fastsafetensors` overrides the
  vLLM default `instanttensor` draft loader and defeats the draft flow. Use
  `--load-format {load_format}` (leave the default).
- **No EP guidance needed for the draft** — the model ships a built-in MTP head
  enabled via `--speculative-config '{"method":"mtp","num_speculative_tokens":2}'`.
- **Confirmed single-node numbers to sanity-check expectations:** ~19-21 tok/s
  decode, ~43.5 tok/s median 40-prompt, ~1000+ tok/s cold prefill, ~10 min
  cold weight load.

See `specs/qwen3-8-flash-next-nvfp4-review.md` for the full spec-line review;
this note captures the general EP-on-GB10 guidance.
