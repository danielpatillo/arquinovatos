"""Meaningful local-HTTP tests; do not load a model or launch llama.cpp."""

import importlib.util
import importlib
import types
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "runtime.py"
PACKAGE_NAME = "arquinovatos_backend_tests"
if PACKAGE_NAME not in sys.modules:
    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(SOURCE.parent)]
    sys.modules[PACKAGE_NAME] = package
SPEC = importlib.util.spec_from_file_location(PACKAGE_NAME + ".runtime", SOURCE)
runtime = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runtime
SPEC.loader.exec_module(runtime)


class FakeProcess:
    instances = []
    mode = "normal"
    chat_requests = []
    all_requests = []

    def __init__(self, arguments, **kwargs):
        self.arguments = arguments
        self.kwargs = kwargs
        self.returncode = None
        self.terminated = False
        self.model_path = arguments[arguments.index("-m") + 1]
        self.alias = arguments[arguments.index("--alias") + 1]
        self.key = arguments[arguments.index("--api-key") + 1]
        port = int(arguments[arguments.index("--port") + 1])
        process = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def respond(self, data, status=200):
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                FakeProcess.all_requests.append(self.path)
                if self.path != "/health" and self.headers.get("Authorization") != "Bearer " + process.key:
                    self.respond({"error": {"message": "wrong owner"}}, 401)
                elif self.path == "/health":
                    self.respond({"status": "ok"})
                elif self.path == "/props":
                    self.respond({"model_path": process.model_path if FakeProcess.mode != "wrong_model" else "/wrong/model.gguf"})
                elif self.path == "/v1/models":
                    self.respond({"data": [{"id": process.alias if FakeProcess.mode != "wrong_owner" else "stranger"}]})
                else:
                    self.respond({"error": "missing endpoint"}, 404)

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                FakeProcess.all_requests.append(self.path)
                if self.headers.get("Authorization") != "Bearer " + process.key:
                    self.respond({"error": {"message": "wrong owner"}}, 401)
                elif self.path == "/apply-template":
                    self.respond({"prompt": json.dumps(payload["messages"], ensure_ascii=False)})
                elif self.path == "/tokenize":
                    self.respond({"tokens": [1] * (len(payload["content"]) // 4)})
                elif self.path == "/v1/chat/completions":
                    FakeProcess.chat_requests.append(payload)
                    if FakeProcess.mode == "http_error":
                        self.respond({"error": {"message": "insufficient context"}}, 400)
                        return
                    content = "Un templo mexicano al amanecer, luz cálida y composición cinematográfica."
                    if payload.get("response_format"):
                        schema = payload["response_format"]["schema"]
                        if schema["properties"][schema["required"][0]]["type"] == "array":
                            document = {field: [] for field in schema["required"]}
                            document.update({"subjects": ["yellow_robot", "exactly_two_purple_tulips"],
                                             "actions": ["robot_watering_tulips"], "scene": ["white_balcony", "sunrise"],
                                             "exclusions": ["no_people", "no_lettering"]})
                            if FakeProcess.mode == "booru_no_action":
                                document.update({"subjects": ["mountain"], "actions": [],
                                                 "scene": ["sunrise"], "exclusions": []})
                            content = json.dumps(document)
                        else:
                            content = json.dumps({key: "Templo mexicano conservado" if index == 0 else ""
                                                  for index, key in enumerate(schema["required"])})
                    if FakeProcess.mode == "invalid_json":
                        content = "Here is prose, not JSON"
                    if FakeProcess.mode == "selected_es_lens_missing":
                        content = ("Un robot amarillo riega exactamente dos tulipanes morados en un balcón blanco al amanecer, "
                                   "estilo acuarela, con una composición de primer plano, iluminación de luz suave y una paleta "
                                   "de colores pastel, al amanecer, sin personas ni letras.")
                    if FakeProcess.mode == "empty":
                        content = "   "
                    if FakeProcess.mode == "thinking":
                        content = "<think>hidden chain</think>prompt"
                    self.respond({"choices": [{"message": {"content": content},
                                              "finish_reason": "length" if FakeProcess.mode == "length" else "stop"}],
                                  "usage": {"prompt_tokens": 130, "completion_tokens": 32, "total_tokens": 162},
                                  "timings": {"predicted_per_second": 80.5}})
                else:
                    self.respond({"error": "missing endpoint"}, 404)

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        FakeProcess.instances.append(self)

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.server.shutdown()
        self.server.server_close()
        self.returncode = 0

    def wait(self, timeout=None):
        self.thread.join(timeout)
        return self.returncode

    def kill(self):
        self.terminate()


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="arquinovatos_test_")
        self.base = Path(self.directory.name)
        self.binary = self.base / "llama-server.exe"
        self.binary.write_bytes(b"fake executable; never run")
        self.models = {}
        for name in runtime.MODEL_NAMES:
            path = self.base / (name + ".gguf")
            path.write_bytes(b"GGUFunit-test-data")
            self.models[name] = str(path)
        self.config_path = self.base / "runtime.json"
        self.data = {"llama_server": str(self.binary), "models": self.models,
                     "context_size": 4096, "max_tokens": 512, "temperature": 0.4,
                     "server_timeout": 5, "request_timeout": 5,
                     "release_after_generation": True, "logs_dir": str(self.base / "logs")}
        self.write_config()
        FakeProcess.instances = []
        FakeProcess.mode = "normal"
        FakeProcess.chat_requests = []
        FakeProcess.all_requests = []
        self.device_patch = patch.object(runtime.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "Available devices:\n  CUDA0: NVIDIA Test GPU", ""))
        self.process_patch = patch.object(runtime.subprocess, "Popen", FakeProcess)
        self.devices = self.device_patch.start()
        self.process_patch.start()
        self.manager = runtime.LlamaRuntime()

    def tearDown(self):
        self.manager.stop()
        self.process_patch.stop()
        self.device_patch.stop()
        self.directory.cleanup()

    def write_config(self):
        self.config_path.write_text(json.dumps(self.data), encoding="utf-8")

    def generate(self, prompt="Templo mexicano al amanecer", instructions="Mejora sin cambiar sujeto, en español.", model=None):
        return self.manager.generate(prompt, instructions, model or runtime.MODEL_NAMES[0], self.config_path)

    def test_unicode_input_preserved_http_metrics_and_release(self):
        prompt = "  templo, café, 日本語\nNo cambiar el sujeto.  "
        instructions = "  Mejora la luz\ny conserva español.  "
        text, metadata = self.generate(prompt, instructions)
        self.assertIn("templo", text)
        request = FakeProcess.chat_requests[0]
        self.assertIn("\n" + prompt + "\n", request["messages"][1]["content"])
        self.assertIn("\n" + instructions + "\n", request["messages"][1]["content"])
        self.assertEqual(request["reasoning_effort"], "none")
        self.assertFalse(request["chat_template_kwargs"]["enable_thinking"])
        self.assertEqual(metadata["tokens_per_second"], 80.5)
        self.assertTrue(metadata["server_released"])
        self.assertTrue(FakeProcess.instances[0].terminated)
        self.assertEqual(self.manager._process, None)
        self.assertEqual(FakeProcess.all_requests[:3], ["/health", "/props", "/v1/models"])
        self.assertIn("--no-context-shift", FakeProcess.instances[0].arguments)
        self.assertIn("--offline", FakeProcess.instances[0].arguments)

    def test_empty_inputs_and_allowlist_fail_before_process_launch(self):
        for prompt, instructions, model in [("  ", "Improve", runtime.MODEL_NAMES[0]),
                                            ("cat", "\n", runtime.MODEL_NAMES[0]),
                                            ("cat", "Improve", "arbitrary_file.gguf")]:
            with self.subTest(prompt=prompt, model=model), self.assertRaises(runtime.EnhancerError):
                self.manager.generate(prompt, instructions, model, self.config_path)
        self.assertEqual(FakeProcess.instances, [])
        self.devices.assert_not_called()

    def test_overflow_rejected_without_generation_or_truncation(self):
        with self.assertRaisesRegex(runtime.EnhancerError, "No se ha truncado"):
            self.generate("escena larga " * 3000)
        self.assertEqual(FakeProcess.chat_requests, [])
        self.assertTrue(FakeProcess.instances[0].terminated)

    def test_http_failure_closes_server_even_in_warm_mode(self):
        self.data["release_after_generation"] = False
        self.write_config()
        FakeProcess.mode = "http_error"
        with self.assertRaisesRegex(runtime.EnhancerError, "HTTP 400"):
            self.generate()
        self.assertTrue(FakeProcess.instances[0].terminated)
        self.assertIsNone(self.manager._process)

    def test_validation_failure_releases_previously_warm_model(self):
        self.data["release_after_generation"] = False
        self.write_config()
        self.generate()
        self.assertIsNotNone(self.manager._process)
        with self.assertRaisesRegex(runtime.EnhancerError, "Prompt positivo"):
            self.generate(prompt="   ")
        self.assertTrue(FakeProcess.instances[0].terminated)
        self.assertIsNone(self.manager._process)

    def test_warm_reuse_and_model_switch_release_previous_process(self):
        self.data["release_after_generation"] = False
        self.write_config()
        _, first = self.generate()
        _, second = self.generate()
        self.assertFalse(first["server_released"])
        self.assertEqual(second["startup_seconds"], 0)
        self.assertEqual(len(FakeProcess.instances), 1)
        _, third = self.generate(model=runtime.MODEL_NAMES[1])
        self.assertTrue(FakeProcess.instances[0].terminated)
        self.assertEqual(len(FakeProcess.instances), 2)
        self.assertEqual(third["model"], runtime.MODEL_NAMES[1])
        self.manager.stop()
        self.assertTrue(FakeProcess.instances[1].terminated)

    def test_wrong_model_and_wrong_owner_never_receive_user_prompt(self):
        for mode in ("wrong_model", "wrong_owner"):
            FakeProcess.mode = mode
            with self.subTest(mode=mode), self.assertRaises(runtime.EnhancerError):
                self.generate()
            self.assertTrue(FakeProcess.instances[-1].terminated)
        self.assertEqual(FakeProcess.chat_requests, [])

    def test_missing_cuda_fails_clearly_without_cpu_fallback(self):
        self.devices.return_value = subprocess.CompletedProcess([], 0, "Available devices:\n CPU", "")
        with self.assertRaisesRegex(runtime.EnhancerError, "no detectó un dispositivo CUDA"):
            self.generate()
        self.assertEqual(FakeProcess.instances, [])

    def test_non_gguf_download_rejected(self):
        Path(self.models[runtime.MODEL_NAMES[0]]).write_text("version https://git-lfs.github.com/spec/v1", encoding="utf-8")
        with self.assertRaisesRegex(runtime.EnhancerError, "no es GGUF válido"):
            self.generate()
        self.assertEqual(FakeProcess.instances, [])

    def test_incomplete_empty_or_reasoning_responses_rejected_and_released(self):
        for mode, expected in (("length", "incompleta"), ("empty", "texto vacío"), ("thinking", "razonamiento")):
            FakeProcess.mode = mode
            with self.subTest(mode=mode), self.assertRaisesRegex(runtime.EnhancerError, expected):
                self.generate()
            self.assertTrue(FakeProcess.instances[-1].terminated)

    def test_invalid_config_and_missing_model_are_actionable(self):
        self.data["temperature"] = True
        self.write_config()
        with self.assertRaisesRegex(runtime.EnhancerError, "temperature"):
            self.generate()
        self.data["temperature"] = 0.4
        self.write_config()
        Path(self.models[runtime.MODEL_NAMES[0]]).unlink()
        with self.assertRaisesRegex(runtime.EnhancerError, "Falta el modelo"):
            self.generate()
        self.assertEqual(FakeProcess.instances, [])

    def test_concurrent_requests_are_serialized_with_single_warm_process(self):
        self.data["release_after_generation"] = False
        self.write_config()
        results = []
        failures = []

        def generate_one(index):
            try:
                results.append(self.generate(prompt=f"Templo mexicano {index}"))
            except Exception as exc:
                failures.append(exc)

        threads = [threading.Thread(target=generate_one, args=(index,)) for index in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        self.assertEqual(failures, [])
        self.assertEqual(len(results), 3)
        self.assertEqual(len(FakeProcess.instances), 1)
        self.assertEqual(len(FakeProcess.chat_requests), 3)

    def test_blank_options_are_byte_identical_and_explicit_choices_only(self):
        blank = {"formato_prompt": "", **{name: "  " for name in runtime.OPTION_NAMES}}
        self.assertEqual(runtime.make_messages("cat", "Improve"), runtime.make_messages("cat", "Improve", blank))
        chosen = runtime.make_messages("cat", "Improve", {"estilo": "acuarela", "lente_mm": "85"})
        self.assertIn("Visual style: acuarela", chosen[1]["content"])
        self.assertIn("Lens focal length in millimeters: 85", chosen[1]["content"])
        self.assertNotIn("Time of day:", chosen[1]["content"])

    def test_json_formats_are_schema_constrained_valid_and_auditable(self):
        for selected_format, expected in (("JSON estructurado", {"prompt"}),
            ("MiniMax H3", {"integrated_multimodal_description", "overall_soundscape", "non_diegetic_music"})):
            improved, metadata = self.manager.generate("Templo mexicano", "Mejora", runtime.MODEL_NAMES[0],
                                                       self.config_path, options={"formato_prompt": selected_format})
            self.assertEqual(set(json.loads(improved)), expected)
            self.assertEqual(json.loads(metadata["effective_prompt"]), FakeProcess.chat_requests[-1]["messages"])
            self.assertEqual(metadata["selected_options"], {"formato_prompt": selected_format})
            self.assertTrue(metadata["server_released"])

    def test_selected_attributes_require_explicit_lens_units_and_every_chosen_value(self):
        selected = {"estilo": "acuarela", "lente_mm": "35", "hora_dia": "amanecer",
                    "composicion": "primer plano", "iluminacion": "luz suave", "paleta_color": "pastel"}
        messages = runtime.make_messages("Un robot amarillo regando exactamente dos tulipanes morados.",
                                         "Mejora sin cambiar sujetos ni cantidades.", selected)
        self.assertIn("35 mm", messages[1]["content"])
        self.assertIn("MUST be explicitly written", messages[0]["content"])
        for value in selected.values():
            self.assertIn(value, messages[1]["content"])
        self.assertIn("silently check every chosen optional", messages[0]["content"])

    def test_invalid_json_closes_warm_process(self):
        self.data["release_after_generation"] = False
        self.write_config()
        FakeProcess.mode = "invalid_json"
        with self.assertRaisesRegex(runtime.EnhancerError, "JSON válido"):
            self.manager.generate("cat", "Improve", runtime.MODEL_NAMES[0], self.config_path,
                                  options={"formato_prompt": "JSON estructurado"})
        self.assertIsNone(self.manager._process)

    def test_custom_model_handle_is_lazy_and_does_not_modify_config_file(self):
        custom = self.base / "my-model.gguf"
        custom.write_bytes(b"GGUFcustom-data")
        handle = runtime.ModelHandle("My model", custom, "Chat GGUF compatible", "ruta manual")
        original = self.config_path.read_bytes()
        improved, metadata = self.manager.generate("cat", "Improve", runtime.MODEL_NAMES[0], self.config_path,
                                                  model_handle=handle)
        self.assertEqual(metadata["model"], "My model")
        self.assertEqual(metadata["model_path"], str(custom))
        self.assertEqual(metadata["model_profile"], "Chat GGUF compatible")
        self.assertEqual(original, self.config_path.read_bytes())
        self.assertTrue(metadata["server_released"])

    def test_invalid_handle_or_options_fail_before_gpu_loading(self):
        for extra in ({"model_handle": "file.gguf"}, {"options": {"estilo": 2}},
                      {"options": {"formato_prompt": "Unknown"}}, {"options": {"unsupported": "x"}}):
            with self.subTest(extra=extra), self.assertRaises(runtime.EnhancerError):
                self.manager.generate("cat", "Improve", runtime.MODEL_NAMES[0], self.config_path, **extra)
        self.assertEqual(FakeProcess.instances, [])

    def test_missing_selected_numeric_lens_is_preserved_without_second_generation(self):
        FakeProcess.mode = "selected_es_lens_missing"
        selected = {"estilo": "acuarela", "lente_mm": "35 mm", "hora_dia": "amanecer",
                    "composicion": "primer plano", "iluminacion": "luz suave", "paleta_color": "pastel"}
        improved, metadata = self.manager.generate("Un robot amarillo riega exactamente dos tulipanes morados.",
                         "Mejora sin cambiar sujetos ni cantidades.", runtime.MODEL_NAMES[0], self.config_path, options=selected)
        self.assertIn("35 mm", improved)
        self.assertEqual(len(FakeProcess.chat_requests), 1)
        self.assertEqual(metadata["output_adjustments"][0]["field"], "lente_mm")
        self.assertNotIn("35 mm", metadata["model_output_before_adjustments"])
        self.assertTrue(metadata["server_released"])

    def test_numeric_lens_adjustment_is_format_aware_and_does_not_match_other_counts(self):
        for selected_format in ("", "Booru tags", "JSON estructurado", "MiniMax H3", "Qwen Image 2511"):
            plain = "35 robots, 135 mm props"
            original = plain
            if selected_format == "JSON estructurado":
                original = json.dumps({"prompt": plain})
            elif selected_format == "MiniMax H3":
                original = json.dumps({"integrated_multimodal_description": plain, "overall_soundscape": "", "non_diegetic_music": ""})
            improved, adjustments = runtime.preserve_selected_numeric_lens(original,
                                            {"lente_mm": "35", "formato_prompt": selected_format})
            self.assertEqual(adjustments[0]["value"], "35 mm")
            if selected_format in ("JSON estructurado", "MiniMax H3"):
                self.assertEqual(set(json.loads(improved)), set(json.loads(original)))
            if selected_format == "Booru tags":
                self.assertIn("35mm_lens", improved)
            else:
                self.assertIn("35 mm", improved)

    def test_numeric_lens_adjustment_is_idempotent_and_blank_or_nonnumeric_does_nothing(self):
        for already_present in ("A robot, 35 mm lens.", "35mm_lens, robot", "robot, 35_mm_lens"):
            improved, adjustments = runtime.preserve_selected_numeric_lens(already_present, {"lente_mm": "35 mm"})
            self.assertEqual(improved, already_present)
            self.assertEqual(adjustments, [])
        for value in ("", "wide-angle", "35 mm macro", "0", "-35"):
            improved, adjustments = runtime.preserve_selected_numeric_lens("A robot.", {"lente_mm": value})
            self.assertEqual(improved, "A robot.")
            self.assertEqual(adjustments, [])
        improved, first = runtime.preserve_selected_numeric_lens("A robot.", {"lente_mm": "24-70 mm"})
        repeated, second = runtime.preserve_selected_numeric_lens(improved, {"lente_mm": "24-70"})
        self.assertEqual(first[0]["value"], "24-70 mm")
        self.assertEqual(repeated, improved)
        self.assertEqual(second, [])

    def test_decimal_numeric_lens_accepts_decimal_dot_or_comma_without_duplication(self):
        for selected in ("35.5", "35,5 mm"):
            for present in ("A robot, 35.5 mm lens.", "A robot, 35,5mm lens."):
                improved, adjustments = runtime.preserve_selected_numeric_lens(present, {"lente_mm": selected})
                self.assertEqual(improved, present)
                self.assertEqual(adjustments, [])

    def test_booru_actions_and_h3_exclusions_have_explicit_format_preservation_contract(self):
        original = "A yellow robot watering exactly two purple tulips. No people or lettering."
        booru = runtime.make_messages(original, "Improve without changing the scene.", {"formato_prompt": "Booru tags"})
        self.assertIn("action verb", booru[0]["content"])
        self.assertIn("not merely its tool", booru[0]["content"])
        h3 = runtime.make_messages(original, "Improve without changing the scene.",
                                   {"formato_prompt": "MiniMax H3", "lente_mm": "35"})
        self.assertIn("All visual exclusions MUST appear explicitly inside integrated_multimodal_description", h3[0]["content"])
        self.assertIn("not in the sound or music fields", h3[0]["content"])
        for messages in (booru, h3):
            self.assertIn("Unless explicitly changed by the editing instructions", messages[0]["content"])

    def test_booru_uses_one_structured_inference_and_audits_internal_transport(self):
        improved, metadata = self.manager.generate("A yellow robot watering exactly two purple tulips. No people or lettering.",
                            "Improve the scene without changing details.", runtime.MODEL_NAMES[0], self.config_path,
                            options={"formato_prompt": "Booru tags"})
        self.assertEqual(len(FakeProcess.chat_requests), 1)
        request = FakeProcess.chat_requests[0]
        schema = request["response_format"]["schema"]
        self.assertEqual(schema["required"], list(runtime.BOORU_FIELDS))
        self.assertTrue(all(value["type"] == "array" for value in schema["properties"].values()))
        self.assertIn("robot_watering_tulips", improved)
        self.assertIn("no_people", improved)
        self.assertNotIn("{", improved)
        self.assertEqual(metadata["response_format"], request["response_format"])
        self.assertEqual(metadata["serialized_booru_prompt"], improved)
        self.assertEqual(json.loads(metadata["internal_model_output"])["actions"], ["robot_watering_tulips"])
        self.assertTrue(metadata["server_released"])

    def test_booru_serializer_allows_no_action_without_inserting_an_action(self):
        FakeProcess.mode = "booru_no_action"
        improved, metadata = self.manager.generate("A mountain at sunrise.", "Improve without adding actions.",
                            runtime.MODEL_NAMES[0], self.config_path, options={"formato_prompt": "Booru tags"})
        self.assertEqual(improved, "mountain, sunrise")
        self.assertEqual(json.loads(metadata["internal_model_output"])["actions"], [])
        self.assertEqual(len(FakeProcess.chat_requests), 1)

    def test_booru_serializer_strict_schema_and_deterministic_category_order(self):
        valid = {"subjects": ["robot"], "actions": ["watering tulips"], "visual_attributes": ["watercolor", "35 mm"],
                 "scene": ["sunrise", "robot"], "exclusions": ["no people"]}
        self.assertEqual(runtime.serialize_booru(valid), "robot, watering tulips, watercolor, 35 mm, sunrise, no people")
        self.assertEqual(runtime.normalize_output(json.dumps(valid), "Booru tags"), runtime.serialize_booru(valid))
        for invalid in ({}, {**valid, "unknown": []}, {**valid, "actions": "watering"},
                        {**valid, "actions": [None]}, {**valid, "scene": [""]},
                        {field: [] for field in runtime.BOORU_FIELDS}):
            with self.subTest(invalid=invalid), self.assertRaises(runtime.EnhancerError):
                runtime.serialize_booru(invalid)

    def test_booru_exclusion_category_always_serializes_with_explicit_negation(self):
        categories = {"subjects": ["yellow robot", "two purple tulips"], "actions": ["watering"],
                      "visual_attributes": ["yellow", "purple", "white"], "scene": ["balcony", "sunrise"],
                      "exclusions": ["people", "lettering"]}
        improved = runtime.serialize_booru(categories)
        self.assertEqual(improved, "yellow robot, two purple tulips, watering, yellow, purple, white, balcony, sunrise, no people, no lettering")
        self.assertEqual(categories["exclusions"], ["people", "lettering"])

    def test_booru_explicit_negative_markers_are_not_duplicated_and_internal_commas_are_safe(self):
        exclusions = ["No people", "sin_texto", "without-logos", "exclude cars", "excluding watermarks",
                      "people, lettering", "no trees, houses", "no_(birds, dogs)"]
        categories = {field: [] for field in runtime.BOORU_FIELDS}
        categories["subjects"] = ["robot"]
        categories["exclusions"] = exclusions
        improved = runtime.serialize_booru(categories)
        self.assertIn("No people", improved)
        self.assertNotIn("no No people", improved)
        self.assertIn("sin_texto", improved)
        self.assertIn("without-logos", improved)
        self.assertIn("exclude cars", improved)
        self.assertIn("no people or lettering", improved)
        self.assertIn("no trees or houses", improved)
        self.assertIn("no_(birds or dogs)", improved)
        for tag in improved.split(", ")[1:]:
            self.assertRegex(tag.lower(), r"^(no|sin|without|exclude|excluding)[ _-]")

    def test_per_execution_advanced_settings_are_effective_and_never_write_config(self):
        original = self.config_path.read_bytes()
        settings = {"max_tokens": 128, "temperature": 0.15, "context_size": 8192}
        _, metadata = self.manager.generate("A temple.", "Improve the lighting.", runtime.MODEL_NAMES[0],
                                            self.config_path, generation_settings=settings)
        self.assertEqual(metadata["generation_settings"], settings)
        self.assertTrue(metadata["advanced_settings_enabled"])
        self.assertEqual(FakeProcess.chat_requests[-1]["max_tokens"], 128)
        self.assertEqual(FakeProcess.chat_requests[-1]["temperature"], 0.15)
        self.assertEqual(FakeProcess.instances[-1].arguments[FakeProcess.instances[-1].arguments.index("-c") + 1], "8192")
        self.assertEqual(self.config_path.read_bytes(), original)
        self.assertTrue(metadata["server_released"])
        _, default = self.generate()
        self.assertEqual(default["generation_settings"], {"max_tokens": 512, "temperature": 0.4, "context_size": 4096})
        self.assertFalse(default["advanced_settings_enabled"])

    def test_invalid_advanced_settings_fail_before_load_and_release_a_previous_warm_model(self):
        invalid = ({"max_tokens": 127}, {"max_tokens": 2049}, {"max_tokens": True},
                   {"temperature": -0.1}, {"temperature": 1.1}, {"temperature": False},
                   {"context_size": 2047}, {"context_size": 8193}, {"context_size": True},
                   {"max_tokens": 2048, "context_size": 2048}, {"unknown": 1})
        for settings in invalid:
            with self.subTest(settings=settings), self.assertRaises(runtime.EnhancerError):
                self.manager.generate("A temple.", "Improve.", runtime.MODEL_NAMES[0], self.config_path,
                                      generation_settings=settings)
        self.assertEqual(FakeProcess.instances, [])
        self.data["release_after_generation"] = False
        self.write_config()
        self.generate()
        with self.assertRaises(runtime.EnhancerError):
            self.manager.generate("A temple.", "Improve.", runtime.MODEL_NAMES[0], self.config_path,
                                  generation_settings={"max_tokens": 2048, "context_size": 2048})
        self.assertTrue(FakeProcess.instances[-1].terminated)
        self.assertIsNone(self.manager._process)

    def test_node_advanced_toggle_off_ignores_values_and_on_applies_them(self):
        nodes = importlib.import_module(PACKAGE_NAME + ".nodes")
        with patch.object(nodes, "RUNTIME", self.manager), patch.object(nodes, "CONFIG_PATH", self.config_path):
            node = nodes.ArquinovatosPromptEnhancer()
            off = node.enhance("A temple.", "Improve.", runtime.MODEL_NAMES[0], ajustes_avanzados=False,
                               tokens_maximos="ignored", creatividad=9.5, contexto=-2)
            on = node.enhance("A temple.", "Improve.", runtime.MODEL_NAMES[0], ajustes_avanzados=True,
                              tokens_maximos=128, creatividad=0.15, contexto=8192)
        self.assertFalse(off["ui"]["metadata"][0]["advanced_settings_enabled"])
        self.assertEqual(off["ui"]["metadata"][0]["max_tokens"], 512)
        self.assertEqual(on["ui"]["metadata"][0]["generation_settings"],
                         {"max_tokens": 128, "temperature": 0.15, "context_size": 8192})
        self.assertTrue(on["ui"]["metadata"][0]["server_released"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
