"""Exercise offline handles, safe extraction and atomic downloads with temporary files."""
import hashlib
import io
import importlib
import json
import os
from pathlib import Path
import stat
import subprocess
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
