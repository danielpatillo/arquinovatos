"""Arquinovatos_Prompt_Enhancer: local, CUDA-backed prompt rewriting."""

from .nodes import ArquinovatosPromptEnhancer, ArquinovatosModelLoader, ArquinovatosModelDownloader, ArquinovatosLLMModel

NODE_CLASS_MAPPINGS = {"Arquinovatos_Prompt_Enhancer": ArquinovatosPromptEnhancer,
                       "Arquinovatos_LLM_Model": ArquinovatosLLMModel,
                       "Arquinovatos_Model_Loader": ArquinovatosModelLoader,
                       "Arquinovatos_Model_Downloader": ArquinovatosModelDownloader}
NODE_DISPLAY_NAME_MAPPINGS = {name: name for name in NODE_CLASS_MAPPINGS}
NODE_DISPLAY_NAME_MAPPINGS["Arquinovatos_LLM_Model"] = "(Down)load LLM model by Arquinovatos"
WEB_DIRECTORY = "./web"
__version__ = "0.0.03"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
