# MoE Tuning Report

Generated: 2026-09-30T17:20:06-04:00

## Configuration

| Parameter | Value |
|-----------|-------|
| Model | `bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard` |
| TP size | 6 |
| Container | sparkrun_9df1420922c5f0b7_84275660db7e_node_0 |
| Total time | 55s |

## Results

| Batch Size | Status | Time |
|--------------------|--------|------|
| 256 | ❌ Failed | 55s |

## Summary

- **Succeeded:** 0/1
- **Failed:** 1/1 (256)

## Re-run failed

```bash
./tune-moe.sh bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard --tp 6 --dtype fp8_w8a8 --batch-size 256
```
