# DeepSeek quality comparison — thinking=off

Endpoint: `http://spark-head.internal.littlecedar.net:4000/v1`

## Scores

| benchmark | deepseek | deepseek-turbo | delta |
|:--|--:|--:|--:|
| aime | 51/90 = 56.7% | 55/90 = 61.1% | +4.4 pp |
| ARC-Challenge (0-shot) | 186/200 = 93.0% | 186/200 = 93.0% | +0.0 pp |
| gpqa | 142/198 = 71.7% | 138/198 = 69.7% | -2.0 pp |
| GSM8K (0-shot) | 194/200 = 97.0% | 197/200 = 98.5% | +1.5 pp |
| hle | 13/200 = 6.5% | 13/200 = 6.5% | +0.0 pp |
| house battery | 36/37 = 97.3% | 36/37 = 97.3% | +0.0 pp |
| humaneval | 159/164 = 97.0% | 157/164 = 95.7% | -1.2 pp |
| math500 | 191/200 = 95.5% | 188/200 = 94.0% | -1.5 pp |
| mbpp | 200/257 = 77.8% | 198/257 = 77.0% | -0.8 pp |
| mmlu_pro | 328/400 = 82.0% | 321/400 = 80.2% | -1.8 pp |

## Reply-level divergence (temperature 0)

| benchmark | identical | differing | one-sided |
|:--|--:|--:|--:|
| aime | 0 | 90 | 0 |
| ARC-Challenge (0-shot) | 198 | 2 | 0 |
| gpqa | 0 | 192 | 0 |
| GSM8K (0-shot) | 8 | 192 | 0 |
| hle | 0 | 200 | 0 |
| house battery | 36 | 1 | 0 |
| humaneval | 95 | 69 | 0 |
| math500 | 3 | 197 | 0 |
| mbpp | 186 | 71 | 0 |
| mmlu_pro | 10 | 390 | 0 |

