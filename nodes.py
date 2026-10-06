"""One portable ComfyUI pack: explicit downloader, lazy GGUF loader and prompt editor."""

from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from .runtime import CONFIG_PATH, MODEL_NAMES, RUNTIME, VERSION
from .runtime import FORMAT_NAMES, OPTION_NAMES
from .model_manager import PROFILES, available_models, load_model, download_model


DEFAULT_INSTRUCTIONS = (
    "Mejora este prompt para generar una imagen: conserva el sujeto y la escena, "
    "las cantidades exactas y la relación entre cada sujeto y sus colores o atributos. "
    "Incluye por escrito todas las exclusiones originales (por ejemplo: sin personas, "
    "sin texto, sin logotipos), sin omitirlas ni añadir exclusiones nuevas. "
    "Describe composición, iluminación, materiales y estilo con precisión. "
    "Evita contradicciones y elementos nuevos que cambien la intención. "
    "Devuelve solo el prompt mejorado, en el mismo idioma, en un párrafo de 80 a 140 palabras."
)


def _save_evidence(prompt: str, instructions: str, improved: str, metadata: dict) -> tuple[str | None, str | None]:
    try:
        import folder_paths
    except ImportError:
        return None, "Evidencia no guardada: folder_paths solo está disponible dentro de ComfyUI."
    try:
        directory = Path(folder_paths.get_output_directory()) / "Arquinovatos_Prompt_Enhancer"
        directory.mkdir(parents=True, exist_ok=True)
        basename = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ_") + uuid.uuid4().hex[:12]
        path = directory / (basename + ".json")
        path.write_text(json.dumps({"timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "prompt_positivo": prompt, "instrucciones": instructions, "prompt_mejorado": improved,
            "metadata": metadata}, ensure_ascii=False, indent=2), encoding="utf-8")
        directory.joinpath(basename + ".txt").write_text(improved + "\n", encoding="utf-8")
        return str(path), None
    except OSError as exc:
        return None, "El prompt se generó, pero no se pudo guardar evidencia: " + str(exc)


class ArquinovatosPromptEnhancer:
    CATEGORY = "Arquinovatos/LLM"
    FUNCTION = "enhance"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("prompt_mejorado", "informacion", "prompt_utilizado")
    OUTPUT_NODE = True
    DESCRIPTION = "Mejora un prompt con uno de tres LLM locales CUDA. v" + VERSION

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "prompt_positivo": ("STRING", {"multiline": True, "default": "",
                "display_name": "Prompt positivo a mejorar", "tooltip": "Tu escena original; se conserva completa."}),
            "instrucciones": ("STRING", {"multiline": True, "default": DEFAULT_INSTRUCTIONS,
                "display_name": 'Prompt para que el LLM mejore el "prompt a mejorar"',
                "tooltip": "Indica idioma, estilo, detalle y longitud deseados."}),
            "modelo": (list(MODEL_NAMES), {"default": MODEL_NAMES[0], "display_name": "Selección de modelo",
                "tooltip": "Un solo modelo se carga en CUDA; la VRAM se libera al terminar."}),
        }, "optional": {
            "modelo_input": ("ARQUINOVATOS_LLM_MODEL", {"tooltip": "Conecta el Loader o Downloader para usar un GGUF local. Tiene prioridad sobre el selector."}),
            "formato_prompt": (list(FORMAT_NAMES), {"default": "", "tooltip": "Vacío conserva tus instrucciones. Qwen 2511 usa el preset de edición Qwen-Image-Edit-2511."}),
            "estilo": ("STRING", {"default": "", "tooltip": "Opcional: artístico, realista, caricatura, acuarela…"}),
            "lente_mm": ("STRING", {"default": "", "tooltip": "Opcional: 24, 35, 50, 85 mm…"}),
            "hora_dia": ("STRING", {"default": "", "tooltip": "Opcional: amanecer, mediodía, atardecer, noche…"}),
            "composicion": ("STRING", {"default": "", "tooltip": "Opcional: plano general, primer plano, simetría…"}),
            "iluminacion": ("STRING", {"default": "", "tooltip": "Opcional: luz suave, contraluz, luz de estudio…"}),
            "paleta_color": ("STRING", {"default": "", "tooltip": "Opcional: tonos cálidos, pastel, monocromático…"}),
        }}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # The user explicitly queues a new LLM take; do not replay stale timings.
        return float("nan")

    def enhance(self, prompt_positivo: str, instrucciones: str, modelo: str,
                modelo_input=None, formato_prompt: str = "", estilo: str = "", lente_mm: str = "",
                hora_dia: str = "", composicion: str = "", iluminacion: str = "", paleta_color: str = ""):
        options = {"formato_prompt": formato_prompt, "estilo": estilo, "lente_mm": lente_mm,
                   "hora_dia": hora_dia, "composicion": composicion, "iluminacion": iluminacion, "paleta_color": paleta_color}
        improved, metadata = RUNTIME.generate(prompt_positivo, instrucciones, modelo, CONFIG_PATH,
                                              model_handle=modelo_input, options=options)
        evidence, warning = _save_evidence(prompt_positivo, instrucciones, improved, metadata)
        if evidence:
            metadata["evidence_path"] = evidence
        if warning:
            metadata["evidence_warning"] = warning
        usage = metadata.get("usage", {})
        information = (
            f"Arquinovatos_Prompt_Enhancer v{VERSION} | {metadata['model']}\n"
            f"Carga: {metadata['startup_seconds']:.3f} s | Generación: {metadata['generation_seconds']:.3f} s | "
            f"Total: {metadata['total_seconds']:.3f} s\n"
            f"Velocidad: {metadata['tokens_per_second']:.2f} tokens/s | "
            f"Tokens de salida: {usage.get('completion_tokens', '?')}\n"
            f"Servidor/VRAM: {'liberado' if metadata['server_released'] else 'modelo caliente en memoria'}"
        )
        if evidence:
            information += "\nEvidencia: " + evidence
        if warning:
            information += "\n" + warning
        if metadata.get("format_note"):
            information += "\n" + metadata["format_note"]
        for adjustment in metadata.get("output_adjustments", []):
            information += "\nAjuste literal: " + adjustment["value"] + " (lente elegida omitida por el LLM)."
        used = metadata["effective_prompt"]
        return {"ui": {"text": [improved], "info": [information], "used_prompt": [used],
                       "prompt_utilizado": [used], "metadata": [metadata]},
                "result": (improved, information, used)}


class ArquinovatosModelLoader:
    CATEGORY = "Arquinovatos/LLM"
    FUNCTION = "load"
    RETURN_TYPES = ("ARQUINOVATOS_LLM_MODEL", "STRING")
    RETURN_NAMES = ("modelo_llm", "informacion")
    OUTPUT_NODE = True
    DESCRIPTION = "Selecciona un GGUF instalado o una ruta manual del PC; no descarga ni ocupa VRAM. v" + VERSION

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "modelo_archivo": (available_models(), {"default": MODEL_NAMES[0], "tooltip": "Modelos del catálogo y GGUF existentes en ComfyUI/models/LLM; recarga la página para actualizar."}),
            "ruta_modelo": ("STRING", {"default": "", "tooltip": "Ruta absoluta opcional del GGUF; tiene prioridad sobre el selector."}),
            "perfil": (list(PROFILES), {"default": "Automático", "tooltip": "El modelo debe soportar chat de texto y tener una plantilla GGUF compatible con llama.cpp CUDA."}),
        }}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def load(self, modelo_archivo: str, ruta_modelo: str = "", perfil: str = "Automático"):
        handle = load_model(modelo_archivo, ruta_modelo, perfil)
        info = f"{handle.name}\nGGUF local: {handle.path}\nPerfil: {handle.profile}\nListo para conectar; VRAM sin cargar."
        return {"ui": {"info": [info]}, "result": (handle, info)}


class ArquinovatosModelDownloader:
    CATEGORY = "Arquinovatos/LLM"
    FUNCTION = "download"
    RETURN_TYPES = ("ARQUINOVATOS_LLM_MODEL", "STRING")
    RETURN_NAMES = ("modelo_llm", "informacion")
    OUTPUT_NODE = True
    DESCRIPTION = "Al ejecutarlo descarga el GGUF ausente y verifica SHA256; opcionalmente instala llama.cpp Windows CUDA. v" + VERSION

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "modelo": (list(MODEL_NAMES), {"default": MODEL_NAMES[0]}),
            "instalar_motor": ("BOOLEAN", {"default": True, "tooltip": "Instala llama.cpp CUDA Windows x64 solo si no hay motor configurado; no carga el modelo en VRAM."}),
        }}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def download(self, modelo: str, instalar_motor: bool = True):
        progress = None
        try:
            from comfy.utils import ProgressBar
            bar = ProgressBar(1000)
            progress = lambda current, total: bar.update_absolute(min(1000, int(current * 1000 / total)), 1000)
        except ImportError:
            pass
        handle, metadata = download_model(modelo, instalar_motor, progress=progress)
        info = (f"{handle.name}\n{'Descargado' if metadata['downloaded'] else 'Reutilizado'} y SHA256 verificado: {handle.path}\n"
                f"Motor: {metadata['llama_server']} ({'instalado' if metadata['engine_installed'] else 'reutilizado o instalación no solicitada'})\n"
                "Listo para conectar; VRAM sin cargar.")
        return {"ui": {"info": [info], "metadata": [metadata]}, "result": (handle, info)}
