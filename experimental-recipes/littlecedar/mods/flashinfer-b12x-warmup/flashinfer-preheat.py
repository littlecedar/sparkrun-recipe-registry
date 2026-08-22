import flashinfer.fused_moe.cute_dsl.blackwell_sm12x.moe_dispatch as md

# trigger _get_dynamic_kernel for the known shape
md._get_dynamic_kernel(512, 4096, 256, 10)

print('b12x kernel loaded into GPU memory successfully')
