# Optimize Qwen3.8-27B Inference Performance on the llama.cpp ROCm Backend

## overview

- Model: Qwen3.8-27B, Q4_K_M GGUF
- Model architecture: 27.32B parameters, Dense model
- Hardware: AMD Radeon PRO W7900D
- ROCm environment: ROCm 10.1
- Vulkan environment: Mesa 26.0.8 RADV in the same container, with `KHR_coopmat` support

With identical hardware, model, and command-line parameters, the ROCm backend delivers lower throughput than Vulkan in the following benchmarks:

| Case | Key Parameters | Vulkan | ROCm | ROCm Slowdown |
| --- | --- | ---: | ---: | ---: |
| 1 | `tg128, d=2048, fa=0` | 34.21 ± 0.19 t/s | **30.47 ± 0.31 t/s** | **12.3%** |
| 1 | `tg128, d=8192, fa=0` | 32.27 ± 0.12 t/s | **26.94 ± 0.25 t/s** | **19.8%** |
| 1 | `tg128, d=32768, fa=0` | 26.62 ± 0.03 t/s | **18.04 ± 0.10 t/s** | **47.6%** |
| 2 | `pp4096, ubatch=128, fa=1` | 637.43 ± 0.48 t/s | **528.05 ± 0.85 t/s** | **20.7%** |
| 2 | `pp4096, ubatch=256, fa=1` | 687.88 ± 1.01 t/s | **753.43 ± 0.77 t/s** | **-8.7%** |

## Task

Optimize the llama.cpp/ggml ROCm backend to improve throughput in the five benchmark entries of the following two `llama-bench` commands without changing the model file, quantization type, benchmark parameters, or computational semantics.

```bash
export MODEL=Qwen3.8-27B-Q4_K_M.gguf

# Case 1: Long-context decoding with Flash Attention disabled
llama-bench -m $MODEL -dev ROCm0 -p 0 -n 128 -d 2048,8192,32768 -fa 0 -r 5

# Case 2: Prefill with a small ubatch
llama-bench -m $MODEL -dev ROCm0 -p 4096 -n 0 -ub 128,256 -fa 1 -r 10
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
**ROCm throughput ranking**: Ranking is based on the geomean of repeated-run statistics across the five benchmark entries above. Higher throughput and lower variance receive a higher ranking.

## Accuracy Validation

Correctness is checked with `llama-perplexity` on the wikitext-2 test set (`wiki.test.raw`). For every run below, the perplexity must be within ±5% of the perplexity of the unmodified ROCm build in the same environment. Each run evaluates a fixed number of chunks (30% of the test set at that context size); `modelbot problems llamacpp-navi3-p1` shows the chunk counts and the reference perplexities.

```bash
# Case 1
llama-perplexity -m $MODEL -dev ROCm0 -ngl 99 -f wiki.test.raw -c 32768 -b 2048 -ub 512 -fa 0 --chunks <chunks>

# Case 2
llama-perplexity -m $MODEL -dev ROCm0 -ngl 99 -f wiki.test.raw -c 4096 -b 4096 -ub 128 -fa 1 --chunks <chunks>
llama-perplexity -m $MODEL -dev ROCm0 -ngl 99 -f wiki.test.raw -c 4096 -b 4096 -ub 256 -fa 1 --chunks <chunks>
```

## Environment

| Item | Value |
| --- | --- |
| GPU | AMD Radeon PRO W7900D (gfx1100 / RDNA3, 48 GB, single GPU) |
| Container image | `rocm/pytorch:rocm10.1.0_ubuntu26.04_py3.14_pytorch_release_2.14.0` |
| Vulkan | Mesa RADV 26.0.8, `KHR_coopmat` |
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

| File | Hugging Face Repository | Bytes |
| --- | --- | ---: |
| `Qwen3.8-27B-Q4_K_M.gguf` | `bartowski/Qwen3.8-27B-GGUF` | 17442399968 |

Download command:

```bash
huggingface-cli download bartowski/Qwen3.8-27B-GGUF \
  Qwen3.8-27B-Q4_K_M.gguf \
  --local-dir /your/path --local-dir-use-symlinks False
```
