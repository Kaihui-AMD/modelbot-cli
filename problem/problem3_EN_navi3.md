# Optimize Kimi-Linear Decoding Performance on the llama.cpp ROCm Backend

## Overview

- Model: Kimi-Linear-48B-A3B-Instruct, IQ4_XS GGUF (`bartowski/moonshotai_Kimi-Linear-48B-A3B-Instruct-GGUF`)
- Model architecture: 20 KDA linear-attention layers and 7 MLA full-attention layers, with 256 experts and 8 active experts
- Hardware: AMD Radeon PRO W7900D (gfx1100 / RDNA3, 48 GB)
- ROCm environment: `rocm/pytorch:rocm10.1.0_ubuntu26.04_py3.14_pytorch_release_2.14.0`
- Vulkan environment: Mesa 26.0.8 RADV in the same container, with `KHR_coopmat` support

With identical hardware, model, and command-line parameters, Vulkan delivers higher throughput than the ROCm backend:

| Case | Key Parameters | Vulkan | ROCm | ROCm Slowdown |
| --- | --- | ---: | ---: | ---: |
| 1 | `tg128, fa=1` | 136.93 ± 0.26 t/s | **97.15 ± 0.35 t/s** | **40.9%** |
| 2 | `tg128, d=2048, fa=1` | 133.39 ± 2.36 t/s | **98.81 ± 1.41 t/s** | **35.0%** |
| 2 | `tg128, d=8192, fa=1` | 125.79 ± 2.46 t/s | **96.15 ± 1.61 t/s** | **30.8%** |
| 2 | `tg128, d=32768, fa=1` | 102.05 ± 1.26 t/s | **87.29 ± 1.12 t/s** | **16.9%** |

## Task

Optimize the llama.cpp/ggml ROCm backend to improve throughput in the four benchmark entries of the following two `llama-bench` commands without changing the model file, quantization type, benchmark parameters, or computational semantics, and without sacrificing existing prefill performance.

```bash
export MODEL=moonshotai_Kimi-Linear-48B-A3B-Instruct-IQ4_XS.gguf

# Case 1: Baseline decoding
llama-bench -m $MODEL -dev ROCm0 -p 0 -n 128 -fa 1 -r 10

# Case 2: Decoding at different context depths
llama-bench -m $MODEL -dev ROCm0 -p 0 -n 128 -d 2048,8192,32768 -fa 1 -r 5
```

For the Vulkan baseline, replace only the device parameter and keep all other parameters identical:

```bash
-dev Vulkan0
```

## Evaluation Criteria

### Mandatory Requirements

Submissions must satisfy all of the following requirements to qualify for bonus-point evaluation:

1. **Correctness**: All checks in the Accuracy Validation section below must pass.
2. **Performance exceeding Vulkan**: In the standardized evaluation environment, ROCm throughput for every benchmark listed above must exceed the Vulkan baseline on the same GPU.

### Bonus Criteria

Submissions that satisfy all mandatory requirements will be evaluated holistically based on the following criteria:
**ROCm throughput ranking**: Ranking is based on the geomean of repeated-run statistics across the four benchmark entries above. Higher throughput and lower variance receive a higher ranking.

## Accuracy Validation

Correctness is checked with `llama-perplexity` on the wikitext-2 test set (`wiki.test.raw`). For every run below, the perplexity must be within ±5% of the perplexity of the unmodified ROCm build in the same environment. Each run evaluates a fixed number of chunks (30% of the test set at that context size); `modelbot problems llamacpp-navi3-p3` shows the chunk counts and the reference perplexities.

```bash
# Case 1
llama-perplexity -m $MODEL -dev ROCm0 -ngl 99 -f wiki.test.raw -c 4096 -b 4096 -ub 512 -fa 1 --chunks <chunks>

# Case 2
llama-perplexity -m $MODEL -dev ROCm0 -ngl 99 -f wiki.test.raw -c 32768 -b 2048 -ub 512 -fa 1 --chunks <chunks>
```

## Environment

| Item | Value |
| --- | --- |
| GPU | AMD Radeon PRO W7900D |
| Container image | `rocm/pytorch:rocm10.1.0_ubuntu26.04_py3.14_pytorch_release_2.14.0` |
| ROCm | 10.1 |
| Vulkan | Mesa RADV 26.0.8, `KHR_coopmat`, wave64 |
| llama.cpp | `aa39d7a3e145a88202793a89462d65e94a5fc25f` |
| ggml | 0.24.0 |

The ROCm and Vulkan backends must be built into their corresponding `llama-bench` binaries while keeping the parent repository, ggml version, build options, and benchmark logic identical. The same physical GPU must be explicitly selected for all evaluations; splitting the model across multiple GPUs is not allowed.

## Model

| Item | Value |
| --- | --- |
| Hugging Face Repository | `bartowski/moonshotai_Kimi-Linear-48B-A3B-Instruct-GGUF` |
| Repository Commit | `228dbe476e5a02091624a19068f4c962caa8a1c5` |
| File Name | `moonshotai_Kimi-Linear-48B-A3B-Instruct-IQ4_XS.gguf` |
| Bytes | `26464880288` |
| SHA-256 | `96e3c084c31382539f334b0f18d3a2c1f3713492cfa4d3f7aa61d1e1340da8a8` |

Download command:

```bash
huggingface-cli download \
  bartowski/moonshotai_Kimi-Linear-48B-A3B-Instruct-GGUF \
  moonshotai_Kimi-Linear-48B-A3B-Instruct-IQ4_XS.gguf \
  --local-dir . --local-dir-use-symlinks False

sha256sum moonshotai_Kimi-Linear-48B-A3B-Instruct-IQ4_XS.gguf
```
