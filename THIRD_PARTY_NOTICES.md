# Third-party components

The custom-node source is covered by the MIT license in this repository. Downloaded artifacts are separate works and keep their own terms. This repository does not include model weights or compiled engines.

| Artifact | Upstream license/source |
|---|---|
| Qwen3.5-4B and Qwen3.5-9B | Apache-2.0; [official Qwen model](https://huggingface.co/Qwen/Qwen3.5-4B) and [9B model](https://huggingface.co/Qwen/Qwen3.5-9B). GGUF quantizations are supplied by [LM Studio community](https://huggingface.co/lmstudio-community). |
| Gemma4-E4B official QAT GGUF | Apache-2.0; [official Google artifact](https://huggingface.co/google/gemma-4-E4B-it-qat-q4_0-gguf). |
| llama.cpp | MIT; [upstream license](https://github.com/ggml-org/llama.cpp/blob/b11433/LICENSE). |
| NVIDIA CUDA runtime DLLs inside the official llama.cpp CUDA runtime archive | NVIDIA's separate CUDA terms; [CUDA EULA](https://docs.nvidia.com/cuda/eula/index.html). The node's MIT license does not relicense NVIDIA components. |

Fixed artifact revisions, hashes and the exact engine release are recorded in `catalog.json`. Users are responsible for respecting the upstream licenses when redistributing downloaded artifacts.
