"""Arquinovatos_Prompt_Enhancer: local, CUDA-backed prompt rewriting."""

from .nodes import ArquinovatosPromptEnhancer, ArquinovatosModelLoader, ArquinovatosModelDownloader

NODE_CLASS_MAPPINGS = {"Arquinovatos_Prompt_Enhancer": ArquinovatosPromptEnhancer,
                       "Arquinovatos_Model_Loader": ArquinovatosModelLoader,
                       "Arquinovatos_Model_Downloader": ArquinovatosModelDownloader}
NODE_DISPLAY_NAME_MAPPINGS = {name: name for name in NODE_CLASS_MAPPINGS}
WEB_DIRECTORY = "./web"
__version__ = "0.0.02"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
