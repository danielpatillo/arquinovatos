"""Exercise offline handles, safe extraction and atomic downloads with temporary files."""
import hashlib
import io
import importlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from test_runtime import PACKAGE_NAME
manager = importlib.import_module(PACKAGE_NAME + ".model_manager")
nodes = importlib.import_module(PACKAGE_NAME + ".nodes")


class ModelManagerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="arquinovatos_models_test_")
        self.base = Path(self.directory.name)
        self.model = self.base / "existing.gguf"
        self.model.write_bytes(b"GGUFtest-existing-local-model")
        self.config = self.base / "runtime.json"
        self.data = {"models_dir": "models", "runtime_dir": "runtime", "models": {"Qwen3.5-4B": str(self.model)}}
        self.config.write_text(json.dumps(self.data), encoding="utf-8")

    def tearDown(self):
        self.directory.cleanup()

    def artifact(self, data=b"GGUFsmall-file"):
        return {"size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                "download_url": "https://huggingface.co/example/resolve/pinned/model.gguf", "filename": "model.gguf"}

    def test_loader_manual_and_catalogue_are_lazy_offline(self):
        with patch.object(manager, "urlopen", side_effect=AssertionError("No network allowed")):
            first = manager.load_model("Qwen3.5-4B", config_path=self.config)
            second = manager.load_model("unused", str(self.model), "Chat GGUF compatible", self.config)
        self.assertEqual(first.path, second.path)
        self.assertEqual(second.profile, "Chat GGUF compatible")
        with self.assertRaisesRegex(manager.ModelManagerError, "absoluta"):
            manager.load_model("unused", "relative.gguf", config_path=self.config)

    def test_portable_relative_paths_and_external_override(self):
        configured = manager.layout(self.config)
        self.assertEqual(configured["models_dir"], self.base / "models")
        self.assertEqual(configured["runtime_dir"], self.base / "runtime")
        local = self.base / "runtime.local.json"
        local.write_text(json.dumps({"models_dir": "shared-models", "llama_server": "engine/llama-server.exe"}))
        with patch.dict(os.environ, {"ARQUINOVATOS_LLM_CONFIG": str(local)}, clear=False):
            defaults = manager.layout()
        self.assertEqual(defaults["models_dir"], self.base / "shared-models")
        self.assertEqual(defaults["llama_server"], self.base / "engine" / "llama-server.exe")
        self.assertNotIn("llama_server", json.loads(manager.CONFIG_PATH.read_text()))

    def test_download_atomic_verification_and_cached_no_network(self):
        data = b"GGUFsmall-file"
        target = self.base / "new" / "model.gguf"
        progress = []
        with patch.object(manager, "urlopen", return_value=io.BytesIO(data)) as network:
            path, fresh = manager.download_verified(self.artifact(data), target,
                                                  lambda current, total: progress.append((current, total)))
            self.assertTrue(fresh)
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(progress[-1], (len(data), len(data)))
            _, fresh = manager.download_verified(self.artifact(data), target)
            self.assertFalse(fresh)
            self.assertEqual(network.call_count, 1)
        self.assertEqual(list(target.parent.glob("*.part")), [])

    def test_wrong_sha_incomplete_and_oversize_never_published(self):
        data = b"GGUFsmall-file"
        for response in (b"GGUFshort", b"GGUFbad-checks", data + b"extra"):
            with self.subTest(response=response), patch.object(manager, "urlopen", return_value=io.BytesIO(response)):
                target = self.base / "bad.gguf"
                with self.assertRaises(manager.ModelManagerError):
                    manager.download_verified(self.artifact(data), target)
                self.assertFalse(target.exists())
                self.assertEqual(list(self.base.glob("*.part")), [])

    def test_invalid_preexisting_file_is_preserved(self):
        before = self.model.read_bytes()
        with patch.object(manager, "urlopen", side_effect=AssertionError("No network allowed")):
            with self.assertRaisesRegex(manager.ModelManagerError, "no se sobrescribió"):
                manager.download_verified(self.artifact(), self.model)
        self.assertEqual(self.model.read_bytes(), before)

    def test_unsafe_download_url_fails_before_network(self):
        for url in ("http://huggingface.co/a", "https://evil.invalid/a", "file:///model.gguf"):
            artifact = self.artifact()
            artifact["download_url"] = url
            with self.subTest(url=url), patch.object(manager, "urlopen") as network:
                with self.assertRaisesRegex(manager.ModelManagerError, "HTTPS"):
                    manager.download_verified(artifact, self.base / "new.gguf")
                network.assert_not_called()

    def test_zip_traversal_absolute_windows_paths_and_symlinks_rejected(self):
        for name in ("../escape.exe", "/escape.exe", "C:/escape.exe", "nested\\..\\escape.exe", "link"):
            archive = self.base / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as package:
                info = zipfile.ZipInfo(name)
                if name == "link":
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                package.writestr(info, "escape")
            with self.subTest(name=name), self.assertRaises(manager.ModelManagerError):
                manager.extract_safe(archive, self.base / "engine")
            self.assertFalse((self.base / "engine").exists())
        self.assertFalse((self.base / "escape.exe").exists())

    def test_safe_zip_extracts_and_engine_reuses_external_binary(self):
        archive = self.base / "safe.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("bin/llama-server.exe", "fake executable")
        manager.extract_safe(archive, self.base / "engine")
        self.data["llama_server"] = "engine/bin/llama-server.exe"
        self.config.write_text(json.dumps(self.data))
        with patch.object(manager, "download_verified", side_effect=AssertionError("No download allowed")):
            binary, installed = manager.install_engine(self.config)
        self.assertFalse(installed)
        self.assertTrue(binary.is_file())

    def test_existing_model_download_reuses_and_preserves_sha(self):
        artifact = self.artifact(self.model.read_bytes())
        fake_catalog = manager.catalog()
        fake_catalog["models"]["Qwen3.5-4B"] = artifact
        with patch.object(manager, "catalog", return_value=fake_catalog), patch.object(manager, "urlopen") as network:
            handle, metadata = manager.download_model("Qwen3.5-4B", False, self.config)
        self.assertEqual(handle.path, self.model)
        self.assertFalse(metadata["downloaded"])
        self.assertFalse(metadata["engine_installed"])
        network.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Automatic CUDA binary installer targets Windows")
    def test_engine_install_is_atomic_and_contains_matching_runtime_files(self):
        def zipped(name, contents):
            archive = self.base / name
            with zipfile.ZipFile(archive, "w") as package:
                for filename, value in contents.items():
                    package.writestr(filename, value)
            return archive

        binary_zip = zipped("binary.zip", {"folder/llama-server.exe": b"fake engine", "folder/ggml-cuda.dll": b"cuda"})
        cuda_zip = zipped("runtime.zip", {"cudart64_13.dll": b"runtime"})
        fake_catalog = manager.catalog()
        fake_catalog["runtime"] = {"binary": {"filename": "binary.zip"}, "cuda_runtime": {"filename": "runtime.zip"}}
        with patch.object(manager, "catalog", return_value=fake_catalog), \
             patch.object(manager, "download_verified", side_effect=[(binary_zip, False), (cuda_zip, False)]), \
             patch.object(manager.shutil, "which", side_effect=lambda name: "nvidia-smi.exe" if name == "nvidia-smi" else None), \
             patch.object(manager.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "GPU 0: NVIDIA test", "")):
            binary, installed = manager.install_engine(self.config)
        self.assertTrue(installed)
        self.assertEqual(binary.read_bytes(), b"fake engine")
        self.assertEqual((binary.parent / "cudart64_13.dll").read_bytes(), b"runtime")
        self.assertEqual(list((self.base / "runtime").glob("install_*")), [])

    def test_node_contract_compatibility_and_blank_optional_defaults(self):
        schema = nodes.ArquinovatosPromptEnhancer.INPUT_TYPES()
        self.assertEqual(list(schema["required"]), ["prompt_positivo", "instrucciones", "modelo"])
        self.assertEqual(schema["optional"]["modelo_input"][0], "ARQUINOVATOS_LLM_MODEL")
        for name in ("formato_prompt", "estilo", "lente_mm", "hora_dia", "composicion", "iluminacion", "paleta_color"):
            self.assertEqual(schema["optional"][name][1]["default"], "")
        self.assertEqual(nodes.ArquinovatosPromptEnhancer.RETURN_TYPES, ("STRING", "STRING", "STRING"))
        for node in (nodes.ArquinovatosModelLoader, nodes.ArquinovatosModelDownloader):
            self.assertEqual(node.RETURN_TYPES, ("ARQUINOVATOS_LLM_MODEL", "STRING"))
            self.assertTrue(node.OUTPUT_NODE)

    def test_unified_node_schema_has_only_selector_required_and_exact_display_name(self):
        schema = nodes.ArquinovatosLLMModel.INPUT_TYPES()
        self.assertEqual(list(schema["required"]), ["modelo_archivo"])
        self.assertEqual(list(schema["optional"]), ["ruta_modelo", "perfil"])
        self.assertEqual(schema["optional"]["ruta_modelo"][1]["default"], "")
        self.assertIn("descargará automáticamente al ejecutar", nodes.ArquinovatosLLMModel.DESCRIPTION)
        self.assertEqual(nodes.ArquinovatosLLMModel.RETURN_TYPES, ("ARQUINOVATOS_LLM_MODEL", "STRING"))
        source = Path(nodes.__file__).with_name("__init__.py")
        spec = importlib.util.spec_from_file_location(PACKAGE_NAME + ".pack_contract", source)
        module = importlib.util.module_from_spec(spec)
        module.__package__ = PACKAGE_NAME
        spec.loader.exec_module(module)
        self.assertEqual(module.NODE_DISPLAY_NAME_MAPPINGS["Arquinovatos_LLM_Model"], "(Down)load LLM model by Arquinovatos")
        self.assertTrue({"Arquinovatos_LLM_Model", "Arquinovatos_Model_Loader", "Arquinovatos_Model_Downloader"}
                        <= set(module.NODE_CLASS_MAPPINGS))

    def test_prepare_existing_catalogue_and_engine_reuses_without_network(self):
        engine = self.base / "runtime" / "bin" / "llama-server.exe"
        engine.parent.mkdir(parents=True)
        engine.write_bytes(b"fake finite test engine; never run")
        with patch.object(manager, "urlopen", side_effect=AssertionError("No network allowed")), \
             patch.object(manager, "download_model", side_effect=AssertionError("No model download allowed")):
            handle, metadata = manager.prepare_model("Qwen3.5-4B", config_path=self.config)
        self.assertEqual(handle.path, self.model)
        self.assertFalse(metadata["downloaded"])
        self.assertFalse(metadata["engine_installed"])
        self.assertEqual(metadata["llama_server"], str(engine))

    def test_prepare_absent_catalogue_downloads_once_with_existing_engine(self):
        name = "Qwen3.5-9B"
        target = self.base / "absent-model.gguf"
        self.data["models"][name] = str(target)
        self.config.write_text(json.dumps(self.data))
        engine = self.base / "runtime" / "bin" / "llama-server.exe"
        engine.parent.mkdir(parents=True)
        engine.write_bytes(b"fake test engine; never run")
        contents = b"GGUFtiny verified download fixture"
        catalogue = manager.catalog()
        catalogue["models"][name] = self.artifact(contents)
        with patch.object(manager, "catalog", return_value=catalogue), \
             patch.object(manager, "urlopen", return_value=io.BytesIO(contents)) as network:
            handle, first = manager.prepare_model(name, profile="Qwen3.5", config_path=self.config)
            _, second = manager.prepare_model(name, config_path=self.config)
        self.assertTrue(first["downloaded"])
        self.assertFalse(first["engine_installed"])
        self.assertFalse(second["downloaded"])
        self.assertEqual(network.call_count, 1)
        self.assertEqual(handle.path.read_bytes(), contents)
        self.assertEqual(handle.profile, "Qwen3.5")

    def test_prepare_existing_or_manual_model_installs_only_missing_engine(self):
        expected_engine = self.base / "fresh-engine" / "llama-server.exe"
        with patch.object(manager, "install_engine", return_value=(expected_engine, True)) as install, \
             patch.object(manager, "download_model", side_effect=AssertionError("No model download allowed")):
            handle, metadata = manager.prepare_model("Qwen3.5-4B", str(self.model),
                                                     "Chat GGUF compatible", self.config)
        self.assertEqual(handle.path, self.model)
        self.assertEqual(handle.profile, "Chat GGUF compatible")
        self.assertFalse(metadata["downloaded"])
        self.assertTrue(metadata["engine_installed"])
        self.assertEqual(metadata["source_mode"], "GGUF local/manual")
        install.assert_called_once_with(self.config, None)

    def test_prepare_invalid_manual_or_corrupt_existing_file_never_falls_back(self):
        for path in (str(self.base / "missing.gguf"), "relative.gguf"):
            with self.subTest(path=path), patch.object(manager, "install_engine") as engine, \
                 patch.object(manager, "download_model") as download:
                with self.assertRaises(manager.ModelManagerError):
                    manager.prepare_model("Qwen3.5-4B", path, config_path=self.config)
                engine.assert_not_called()
                download.assert_not_called()
        self.model.write_bytes(b"NOTGGUF")
        with patch.object(manager, "install_engine") as engine, patch.object(manager, "download_model") as download:
            with self.assertRaisesRegex(manager.ModelManagerError, "GGUF válido"):
                manager.prepare_model("Qwen3.5-4B", config_path=self.config)
            engine.assert_not_called()
            download.assert_not_called()

    def test_public_pack_import_never_downloads_or_starts_a_process(self):
        source = Path(nodes.__file__).with_name("__init__.py")
        spec = importlib.util.spec_from_file_location("arquinovatos_import_no_network", source,
                                                     submodule_search_locations=[str(source.parent)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        with patch("urllib.request.urlopen", side_effect=AssertionError("No network allowed")), \
             patch("subprocess.Popen", side_effect=AssertionError("No process allowed")), \
             patch("subprocess.run", side_effect=AssertionError("No process allowed")):
            spec.loader.exec_module(module)
        self.assertEqual(module.__version__, "0.0.03")


if __name__ == "__main__":
    unittest.main(verbosity=2)
