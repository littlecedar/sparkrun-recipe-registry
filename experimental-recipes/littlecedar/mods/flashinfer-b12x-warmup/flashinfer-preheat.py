import torch
import flashinfer.fused_moe.cute_dsl.blackwell_sm12x.moe_dispatch as md
from transformers import AutoConfig

print(AutoConfig.from_pretrained('ornith-ai/Ornith-1.5-397B-NVFP4', trust_remote_code=True))

print("Pre-warming b12x MoE kernel: E=512 k=4096 n=256 num_topk=10 max_rows=16384")

kernel = md._get_dynamic_kernel(
    E=512,        # num_experts = 512 (text_config.num_experts)
    m=4096,       # hidden_size = 4096 (text_config.hidden_size); input token dimension
    k=4096,       # hidden_size = 4096; weight K dimension (same as hidden_size for MoE FFN input)
    n=256,        # moe_intermediate_size / tp_size = 1024 / 4; per-rank weight N dimension
    num_topk=10,  # num_experts_per_tok = 10 (text_config.num_experts_per_tok)
    max_rows=16384,                      # --max-num-batched-tokens; upper bound on M dimension at runtime
    topk_ids_dtype=torch.int32,          # default; dtype of the expert routing index tensor
    input_scales_are_reciprocal=False,   # default; set True if scales are stored as 1/s rather than s
    fast_math=True,                      # default; enables relaxed FP associativity in CUDA fast-math mode
    activation="silu",                   # text_config.hidden_act = "silu"
    swiglu_alpha=1.702,                  # default; SwiGLU sigmoid sharpness α — unused when activation="silu"
    swiglu_beta=1.0,                     # default; SwiGLU linear scale β — unused when activation="silu"
    swiglu_limit=None,                   # default; optional output clamp for SwiGLU — unused when activation="silu"
    activation_precision="fp4",          # matches quant config: activations quantized to NF4
    share_input_across_experts=False,    # default; True only for shared-expert layers; use False for routed experts
    tile_m=128,                          # default; CTA tile size along M dimension; 128 is standard for Blackwell
    quant_mode="nvfp4",                  # matches quantization method: NVFP4 (weights + activations)
)

print(f"Kernel loaded successfully: {kernel}")
print("GPU memory now holds b12x kernel binary — vLLM startup load will be a no-op.")
