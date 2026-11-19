# Optimize Qwen3-Next-80B Inference Performance on the llama.cpp ROCm Backend

## Overview

- Model: Qwen3-Next-80B-A3B-Instruct, IQ2_XXS GGUF
- Model architecture: 79.67B parameters, 512 experts with 10 active experts, and a 48-layer hybrid linear-attention architecture
- Hardware: Single AMD Radeon PRO W7900D (gfx1100 / RDNA3, 48 GB)
- ROCm environment: `rocm/pytorch:rocm10.1.0_ubuntu26.04_py3.14_pytorch_release_2.14.0`
- Vulkan environment: Mesa RADV in the same container, with `KHR_coopmat` support

With identical hardware, model, and command-line parameters, Vulkan delivers higher throughput than the ROCm backend:

| Case | Key Parameters | Vulkan | ROCm | ROCm Slowdown |
| --- | --- | ---: | ---: | ---: |
| 1 | `pp128, fa=1` | 890.02 ± 18.92 t/s | **359.35 ± 5.87 t/s** | **147.7%** |
| 2 | `pp512, fa=1` | 1646.29 ± 18.38 t/s | **700.46 ± 4.02 t/s** | **135.0%** |
| 3 | `pp4096, fa=1` | 1631.34 ± 6.09 t/s | **698.74 ± 6.71 t/s** | **133.5%** |
| 4 | `pp4096, ubatch=128, fa=1` | 898.38 ± 3.89 t/s | **369.12 ± 1.40 t/s** | **143.4%** |
| 4 | `pp4096, ubatch=256, fa=1` | 1252.33 ± 4.90 t/s | **526.78 ± 1.69 t/s** | **137.7%** |
| 4 | `pp4096, ubatch=512, fa=1` | 1631.86 ± 12.65 t/s | **695.14 ± 2.80 t/s** | **134.8%** |

## Task

Optimize the llama.cpp/ggml ROCm backend to improve throughput in the six benchmark entries of the following four `llama-bench` commands without changing the model file, quantization type, benchmark parameters, or computational semantics.

```bash
export MODEL=Qwen_Qwen3-Next-80B-A3B-Instruct-IQ2_XXS.gguf

# Case 1: Prefill with a short prompt
llama-bench -m $MODEL -dev ROCm0 -p 128 -n 0 -fa 1 -r 20

# Case 2: Standard prefill
llama-bench -m $MODEL -dev ROCm0 -p 512 -n 0 -fa 1 -r 10

# Case 3: Prefill with a long prompt
llama-bench -m $MODEL -dev ROCm0 -p 4096 -n 0 -fa 1 -r 5

# Case 4: ubatch sweep
llama-bench -m $MODEL -dev ROCm0 -p 4096 -n 0 \
  -ub 128,256,512 -fa 1 -r 10
```

For the Vulkan baseline, replace only the device parameter and keep all other parameters identical:

```bash
-dev Vulkan0
```

The same physical GPU must be explicitly selected for all evaluations; splitting the model across multiple GPUs is not allowed. After moving to another machine, verify the ROCm-to-Vulkan device mapping using the PCI bus.

## Evaluation Criteria

### Mandatory Requirements

Submissions must satisfy all of the following requirements to qualify for bonus-point evaluation:

1. **Correctness**: All checks in the Accuracy Validation section below must pass.
2. **Performance exceeding Vulkan**: In the standardized evaluation environment, ROCm throughput for every benchmark listed above must exceed the Vulkan baseline on the same GPU.

### Bonus Criteria

Submissions that satisfy all mandatory requirements will be evaluated holistically based on the following criteria:
**ROCm throughput ranking**: Ranking is based on the geomean of repeated-run statistics across the six benchmark entries above. Higher throughput and lower variance receive a higher ranking.

## Accuracy Validation

Correctness is checked with `llama-perplexity` on the wikitext-2 test set (`wiki.test.raw`). For every run below, the perplexity must be within ±5% of the perplexity of the unmodified ROCm build in the same environment. Each run evaluates a fixed number of chunks (30% of the test set at that context size); `modelbot problems llamacpp-navi3-p2` shows the chunk counts and the reference perplexities.

```bash
# ubatch 512: Cases 1-3 and Case 4
llama-perplexity -m $MODEL -dev ROCm0 -ngl 99 -f wiki.test.raw -c 4096 -b 4096 -ub 512 -fa 1 --chunks <chunks>

# ubatch 128 and 256: Case 4
llama-perplexity -m $MODEL -dev ROCm0 -ngl 99 -f wiki.test.raw -c 4096 -b 4096 -ub 128 -fa 1 --chunks <chunks>
llama-perplexity -m $MODEL -dev ROCm0 -ngl 99 -f wiki.test.raw -c 4096 -b 4096 -ub 256 -fa 1 --chunks <chunks>
```

## Environment

| Item | Value |
| --- | --- |
| GPU | AMD Radeon PRO W7900D (gfx1100 / RDNA3, 48 GB, single GPU) |
| Container image | `rocm/pytorch:rocm10.1.0_ubuntu26.04_py3.14_pytorch_release_2.14.0` |
| Vulkan | Mesa RADV, `KHR_coopmat` |
| llama.cpp | `aa39d7a3e145a88202793a89462d65e94a5fc25f` |

The ROCm and Vulkan backends must be built from the same llama.cpp commit using identical build configurations and the same `llama-bench` logic. Key options for building the ROCm backend:

```bash
-DGGML_HIP=ON \
-DGPU_TARGETS=gfx1100 \
-DAMDGPU_TARGETS=gfx1100
```

The Vulkan backend uses:

```bash
-DGGML_VULKAN=ON
```

## Model

| File | Hugging Face Repository | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `Qwen_Qwen3-Next-80B-A3B-Instruct-IQ2_XXS.gguf` | `bartowski/Qwen_Qwen3-Next-80B-A3B-Instruct-GGUF` | 19298972128 | `d132df15f4594724ce059b342efe360085e0aa8c8094b219600cfab53d4e8ac7` |

Hugging Face repository commit: `c07b9268d97d8ba09d0529980627f3bd70f5f90a`.

Download command:

```bash
huggingface-cli download \
  bartowski/Qwen_Qwen3-Next-80B-A3B-Instruct-GGUF \
  Qwen_Qwen3-Next-80B-A3B-Instruct-IQ2_XXS.gguf \
  --local-dir /your/path --local-dir-use-symlinks False

sha256sum \
  /your/path/Qwen_Qwen3-Next-80B-A3B-Instruct-IQ2_XXS.gguf
```
