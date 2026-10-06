# Validation and limits — v0.0.02

Validation environment: Windows x64, RTX 5090 Laptop with approximately 24 GB VRAM, Python 3.12.10, Torch 2.13.0+cu130, ComfyUI 0.39.0 and frontend 1.53.10. CUDA llama.cpp b11433. The default is Qwen3.5-4B Q4_K_M.

## Confirmed checks

- 39 standard-library backend unit tests cover model handles, empty options, schemas, download integrity/atomicity, safe staged engine installation, input limits, numeric-lens preservation and one-call categorized Booru serialization with negative exclusion semantics.
- 14 Chromium DOM checks cover text resizing, buttons, clipboard, detail expansion without canvas event propagation, ancestor-only queue construction and queue restoration.
- A new Qwen3.5-4B GGUF was downloaded into an empty folder using the pack's actual verified download function: 2,707,513,696 bytes, exact catalogue SHA256, valid GGUF magic and no leftover partial file. The transfer took approximately 739 seconds on the test connection.
- The newly downloaded file was selected by manual path in the real Loader → Enhancer Comfy queue. Output preserved the tested subjects, colors, count and exclusions; the inference process was released afterward.
- The actual engine installer installed 55 files into an empty isolated runtime from the two hash-verified official cached ZIPs. `--version` confirmed build 11433 and `--list-devices` detected CUDA on the RTX 5090 Laptop. Both finite verification processes exited.
- A real click on **Mejorar prompt** generated the example through Comfy's queue in 3.807 seconds total (138.03 tokens/s generation). The copy button produced exactly the displayed result. These numbers are one local measurement, not a performance guarantee.
- 18/18 live ComfyUI API cases passed automatic checks and independent content review: 14 real generations, three cached Downloader runs and one expected missing-file error. The matrix covers all three models, manual-path model override, formats, optional attributes, selected time override and lenses in structured formats. Median measured generation speed was 136.53 tokens/s and total duration 3.461 seconds in that matrix.
- Real ComfyUI text areas grew with 24 input rows and shrank after their removal. The final UI exposed exact system/user messages, expanded details without opening a canvas menu and copied the generated result correctly. Machine-specific full reports and earlier failed attempts are retained locally outside the public source archive.
- The public GitHub commit ZIP was downloaded anonymously, without a credential or cookie. All 25 source blobs matched the reviewed package and all 39 backend tests passed from the downloaded folder.

## Scope and practical limits

Downloaded artifacts use pinned revisions and hashes. They are not converted or redistributed in this source package. Automatic engine installation targets Windows x64/NVIDIA; a working CUDA llama-server is required for inference.

Supported model choices were tested locally. A manual GGUF must be a compatible text-chat model with a suitable embedded chat template. Loading an arbitrary GGUF handle does not prove that its architecture or template can generate useful text.

An LLM can still omit or invent details in a new prompt. Review its output before using it. Numeric-lens preservation is explicitly recorded and does not guarantee arbitrary semantic fidelity. The format presets do not invoke Qwen Image or MiniMax H3 generators. The Enhancer only returns text and never examines a reference image.

Booru uses one schema-constrained internal generation with separate subjects, actions, visual attributes, scene and exclusions arrays. Python joins all returned categories into the final tag line without a second LLM compression. The internal response and schema are saved in metadata; this improves structure without promising universal semantic accuracy.

Blank options add no extra selected attributes or format instructions. Selected options can intentionally replace an original attribute, such as changing dawn to night. Context overflow and incomplete/invalid JSON responses are reported as errors rather than silently accepting a truncated output.

Run backend checks with `python -m unittest discover -s tests -v` from the pack folder. Generation and download behavior are explicit; importing the package does not perform either action.
