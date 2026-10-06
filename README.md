# Arquinovatos_Prompt_Enhancer

**v0.0.02** — local LLM prompt editing, GGUF loading and verified downloads in one ComfyUI pack. Python package version: `0.0.2`.

## Install

Clone into ComfyUI's `custom_nodes` folder and restart ComfyUI:

```sh
git clone https://github.com/danielpatillo/arquinovatos ComfyUI/custom_nodes/Arquinovatos_Prompt_Enhancer
```

The Python backend uses only the standard library. Manager's **Install via Git URL** also accepts the repository URL. Public Manager search requires separate registration; see [publication status](docs/PUBLICATION.md).

Automatic engine installation targets **Windows x64 with NVIDIA CUDA** and downloads pinned official llama.cpp binaries. Other platforms require a suitable local llama-server; this release requires a working CUDA backend. Integration is tested on a Windows RTX 5090 Laptop with 24 GB VRAM. No image/video generator is included.

## Three nodes

| Node | Function |
|---|---|
| `Arquinovatos_Model_Loader` | Select an installed text-chat GGUF or supply an absolute path from your PC. Returns a model handle without occupying VRAM. |
| `Arquinovatos_Model_Downloader` | Download an absent recommended model, verify SHA256 and optionally install a missing engine. |
| `Arquinovatos_Prompt_Enhancer` | Improve the original positive prompt using your editing instructions and the selected/connected local model. |

Connect `modelo_llm` to the Enhancer's `modelo_input`. A connected model overrides the Enhancer's selector. The standalone selector remains available for existing workflows.

The Loader finds GGUF files under ComfyUI's `models/LLM` folders. Its manual path takes priority. The GGUF must be a text LLM with a chat template compatible with llama.cpp; diffusion GGUF weights cannot serve as a text LLM. Loader profiles describe compatibility and do not convert an unsupported model.

The Downloader works only when executed, including as an ancestor of an executed Enhancer. There are no import-time downloads. Existing incorrect files are preserved with an actionable error. New artifacts are published atomically after size/hash verification. Prefer **Loader → Enhancer** for everyday use; run the Downloader separately when needed to avoid rehashing several GB on every improvement.

## Models

| Selection | Download |
|---|---|
| **Qwen3.5-4B** — default for speed | Q4_K_M, about 2.52 GiB |
| Qwen3.5-9B | Q4_K_M, about 5.24 GiB |
| Gemma4-E4B | Official QAT Q4_0, about 4.80 GiB |

[`catalog.json`](catalog.json) records fixed revisions, URLs, sizes and hashes. The weights stay on Hugging Face. These are practical recommendations for prompt editing, not a universal ranking.

## Prompt controls

Enter the original prompt and instructions, then click **Mejorar prompt**. This queues only the Enhancer and its ancestors, excluding downstream image/video generation. **Copiar prompt mejorado** copies the current result. Text areas and node height grow and shrink with text and wrapping. Execution information and exact LLM messages expand separately.

All optional controls start **empty** and add no instruction until filled: format, style, lens focal length, time of day, composition, lighting and color palette. Attributes accept your own text, such as `realista`, `35 mm`, `atardecer`, `simetría`, `luz suave` or `tonos cálidos`.

If the LLM omits a selected numeric lens, a small final adjustment preserves its exact focal length. This uses no second generation and is recorded in execution information/evidence with the model's original response. Empty lens fields add nothing.

Formats:

- **Qwen Image 2511:** natural-language instructions for [Qwen-Image-Edit-2511](https://huggingface.co/Qwen/Qwen-Image-Edit-2511). This node does not inspect or invent a reference image. The separate text-to-image release is Qwen-Image-2512.
- **MiniMax H3:** JSON fields `integrated_multimodal_description`, `overall_soundscape`, `non_diegetic_music`, following the [official writing guide](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing). Unrequested sound/music remain empty.
- **JSON estructurado:** this pack's own validated schema, `{"prompt": "complete improved prompt"}`.
- **Booru tags:** a comma-separated tag line. One schema-constrained internal JSON generation separates subjects, actions, visual attributes, scene and exclusions; Python joins the categories without a second LLM call. The internal response/schema are audited in metadata. Vocabulary suitability depends on the target image model.
- **Lenguaje natural:** fluent prose. Empty format and **Sin formato específico** add no format instruction.

## Outputs and local processing

Three connectable strings: `prompt_mejorado`, `informacion`, `prompt_utilizado`. The last is the exact system/user messages sent to the local LLM. Results and evidence are saved under ComfyUI's `output/Arquinovatos_Prompt_Enhancer`.

Prompts remain on loopback; network access is limited to explicit artifact downloads. By default llama-server closes after each generation and on errors, returning its VRAM. It inherits ComfyUI's console and leaves no persistent hidden terminal.

## Reuse your own engine/model files

Machine settings belong outside the repository in `ComfyUI/user/Arquinovatos_Prompt_Enhancer/runtime.local.json`, or in a JSON file named by `ARQUINOVATOS_LLM_CONFIG`. Relative paths are resolved against that settings file.

```json
{
  "llama_server": "C:/llama/bin/llama-server.exe",
  "models": {
    "Qwen3.5-4B": "C:/models/Qwen3.5-4B-Q4_K_M.gguf",
    "Qwen3.5-9B": "C:/models/Qwen3.5-9B-Q4_K_M.gguf",
    "Gemma4-E4B": "C:/models/gemma-4-E4B_q4_0-it.gguf"
  },
  "release_after_generation": true
}
```

A new installation needs no local override: the Downloader uses ComfyUI's model/user folders. Never commit private settings or keys.

## Workflows, validation and licenses

Drag a visual JSON from [`workflows`](workflows) into ComfyUI. API equivalents are included. No other custom-node pack is needed.

Backend checks: `python -m unittest discover -s tests -v`. Tested release and limits: [`docs/VALIDATION.md`](docs/VALIDATION.md).

Source license: MIT. Models and engine/runtime components keep their own licenses; see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). The next user-requested iteration is **v0.0.03**.
