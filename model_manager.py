"""Portable model handles and explicit, verified downloads. No import-time network work."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from http.client import IncompleteRead
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import subprocess
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import uuid
import zipfile


MODEL_NAMES = ("Qwen3.5-4B", "Qwen3.5-9B", "Gemma4-E4B")
PROFILES = ("Automático", "Qwen3.5", "Gemma4", "Chat GGUF compatible")
CONFIG_PATH = Path(__file__).with_name("runtime.json")
CATALOG_PATH = Path(__file__).with_name("catalog.json")
_DOWNLOAD_LOCK = threading.RLock()


class ModelManagerError(RuntimeError):
    """Actionable model/configuration/download failure."""


@dataclass(frozen=True)
class ModelHandle:
    name: str
    path: Path
    profile: str = "Automático"
    source: str = "local"


def catalog() -> dict:
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ModelManagerError(f"No se puede leer el catálogo de modelos: {exc}") from exc


def _json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ModelManagerError(f"No se puede leer configuración en {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ModelManagerError(f"La configuración {path} debe contener un objeto JSON.")
    return value


def default_directories() -> tuple[Path, Path]:
    try:
        import folder_paths
        return Path(folder_paths.models_dir), Path(folder_paths.get_user_directory())
    except (ImportError, AttributeError):
        base = Path(__file__).parent
        return base / "models", base / "data"


def read_settings(config_path: Path = CONFIG_PATH) -> tuple[dict, Path]:
    """Relative paths belong to their JSON file. External local overrides never change the repo."""
    config_path = Path(config_path)
    data = _json(config_path)
    anchor = config_path.parent
    path_keys = ("llama_server", "models_dir", "runtime_dir", "downloads_dir", "logs_dir")

    def anchored(document: dict, directory: Path) -> dict:
        output = dict(document)
        for key in path_keys:
            value = output.get(key)
            if isinstance(value, str) and value.strip():
                candidate = Path(os.path.expandvars(os.path.expanduser(value)))
                output[key] = str((directory / candidate).resolve() if not candidate.is_absolute() else candidate.resolve())
        models = output.get("models")
        if isinstance(models, dict):
            output["models"] = {name: str((directory / Path(value)).resolve()) if not Path(value).is_absolute()
                                else str(Path(value).resolve()) for name, value in models.items() if isinstance(value, str)}
        return output

    data = anchored(data, anchor)
    # Explicit custom test/config paths are isolated from global user settings.
    if config_path.resolve() == CONFIG_PATH.resolve():
        _, user_directory = default_directories()
        external = os.environ.get("ARQUINOVATOS_LLM_CONFIG") or os.environ.get("ARQUINOVATOS_RUNTIME_CONFIG")
        external_path = Path(external).expanduser() if external else user_directory / "Arquinovatos_Prompt_Enhancer" / "runtime.local.json"
        if external or external_path.is_file():
            data.update(anchored(_json(external_path), external_path.resolve().parent))
        if os.environ.get("ARQUINOVATOS_LLAMA_SERVER"):
            data["llama_server"] = os.environ["ARQUINOVATOS_LLAMA_SERVER"]
        if os.environ.get("ARQUINOVATOS_MODEL_DIR"):
            data["models_dir"] = os.environ["ARQUINOVATOS_MODEL_DIR"]
    return data, anchor


def layout(config_path: Path = CONFIG_PATH) -> dict:
    settings, _ = read_settings(config_path)
    models_base, user_base = default_directories()
    model_dir = Path(settings.get("models_dir") or models_base / "LLM" / "Arquinovatos_Prompt_Enhancer").resolve()
    runtime_dir = Path(settings.get("runtime_dir") or user_base / "Arquinovatos_Prompt_Enhancer" / "runtime").resolve()
    files = catalog()["models"]
    defaults = {name: model_dir / files[name]["filename"] for name in MODEL_NAMES}
    models = settings.get("models", {})
    if not isinstance(models, dict):
        raise ModelManagerError("La configuración 'models' debe ser un objeto nombre:ruta.")
    defaults.update({name: Path(value).resolve() for name, value in models.items() if name in MODEL_NAMES})
    explicit = settings.get("llama_server")
    exe = "llama-server.exe" if os.name == "nt" else "llama-server"
    candidates = [Path(explicit).resolve()] if explicit else [runtime_dir / "bin" / exe]
    path_binary = shutil.which(exe)
    if not explicit and path_binary:
        candidates.append(Path(path_binary).resolve())
    binary = next((path for path in candidates if path.is_file()), candidates[0])
    return {"settings": settings, "models": defaults, "models_dir": model_dir, "runtime_dir": runtime_dir,
            "llama_server": binary, "downloads_dir": Path(settings.get("downloads_dir") or runtime_dir / "downloads"),
            "logs_dir": Path(settings.get("logs_dir") or runtime_dir / "logs")}


def validate_gguf(path: Path) -> Path:
    path = Path(path).resolve()
    if not path.is_file():
        raise ModelManagerError(f"Falta el modelo GGUF: {path}. Elige un archivo local existente o un modelo del catálogo en "
                                "'(Down)load LLM model by Arquinovatos'. Una ruta manual inexistente no se sustituye por una descarga.")
    if path.suffix.lower() != ".gguf":
        raise ModelManagerError(f"El modelo debe ser un archivo .gguf: {path}")
    try:
        with path.open("rb") as handle:
            if handle.read(4) != b"GGUF":
                raise ModelManagerError(f"No es un GGUF válido o la descarga está incompleta: {path}")
    except OSError as exc:
        raise ModelManagerError(f"No se puede leer el GGUF {path}: {exc}") from exc
    return path


def available_models() -> list[str]:
    """Include catalogue entries even before download, plus Comfy's registered GGUF paths."""
    locations = layout()
    roots = [locations["models_dir"]]
    try:
        import folder_paths
        for category in ("LLM", "llm", "gguf"):
            roots.extend(Path(path) for path in folder_paths.get_folder_paths(category))
        roots.append(Path(folder_paths.models_dir) / "LLM")
    except (ImportError, AttributeError, KeyError):
        pass
    paths: set[str] = set()
    for root in roots:
        if root.is_dir():
            paths.update(str(path.resolve()) for path in root.rglob("*.gguf") if path.is_file())
    return list(MODEL_NAMES) + sorted(paths, key=str.casefold)


def load_model(model_file: str, manual_path: str = "", profile: str = "Automático",
               config_path: Path = CONFIG_PATH) -> ModelHandle:
    if profile not in PROFILES:
        raise ModelManagerError("Perfil desconocido. Selecciona un perfil del nodo.")
    if manual_path.strip():
        candidate = Path(manual_path.strip().strip('"')).expanduser()
        if not candidate.is_absolute():
            raise ModelManagerError("La ruta manual del PC debe ser absoluta (por ejemplo C:/modelos/modelo.gguf).")
        name, source = candidate.stem, "ruta manual"
    elif model_file in MODEL_NAMES:
        candidate = layout(config_path)["models"][model_file]
        name, source = model_file, "catálogo/local"
    else:
        candidate = Path(model_file)
        if not candidate.is_absolute():
            raise ModelManagerError("Selecciona un GGUF disponible o escribe su ruta absoluta.")
        name, source = candidate.stem, "GGUF local"
    return ModelHandle(name, validate_gguf(candidate), profile, source)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_verified(artifact: dict, target: Path, progress=None) -> tuple[Path, bool]:
    """Never replace a preexisting invalid file; atomically publish only size/SHA-verified data."""
    target = Path(target)
    expected_size, expected_hash = artifact["size_bytes"], artifact["sha256"]
    with _DOWNLOAD_LOCK:
        try:
            if target.is_file():
                if target.stat().st_size == expected_size and sha256(target) == expected_hash:
                    return target, False
                raise ModelManagerError(f"El archivo existente no coincide con el SHA256 del catálogo: {target}. "
                                        "Muévelo o elimínalo manualmente antes de descargar; no se sobrescribió.")
            parsed = urlparse(artifact["download_url"])
            if parsed.scheme != "https" or parsed.hostname not in ("huggingface.co", "github.com"):
                raise ModelManagerError("La URL del catálogo debe ser HTTPS de Hugging Face o GitHub.")
            target.parent.mkdir(parents=True, exist_ok=True)
            free = shutil.disk_usage(target.parent).free
            if free < expected_size + 64 * 1024 * 1024:
                raise ModelManagerError(f"No hay espacio suficiente para descargar {target.name} ({expected_size} bytes).")
            temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".part")
            digest, received = hashlib.sha256(), 0
            try:
                request = Request(artifact["download_url"], headers={"User-Agent": "Arquinovatos-Prompt-Enhancer/0.0.02"})
                with urlopen(request, timeout=60) as response, temporary.open("xb") as output:
                    for block in iter(lambda: response.read(4 * 1024 * 1024), b""):
                        received += len(block)
                        if received > expected_size:
                            raise ModelManagerError("La descarga supera el tamaño fijado en el catálogo.")
                        output.write(block)
                        digest.update(block)
                        if progress:
                            progress(received, expected_size)
                    output.flush()
                    os.fsync(output.fileno())
                if received != expected_size or digest.hexdigest() != expected_hash:
                    raise ModelManagerError(f"Descarga incompleta o SHA256 incorrecto de {target.name}; no se instaló.")
                # Atomic rename with no overwrite on Windows; lock also protects same-process callers.
                if target.exists():
                    raise ModelManagerError(f"Apareció otro archivo durante la descarga: {target}; no se sobrescribió.")
                if os.name == "nt":
                    temporary.rename(target)
                else:
                    # link() atomically fails if another process creates target; rename() may overwrite on POSIX.
                    os.link(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            return target, True
        except HTTPError as exc:
            raise ModelManagerError(f"Descarga rechazada HTTP {exc.code}. Revisa acceso/licencia del repositorio {artifact['download_url']}.") from exc
        except (URLError, TimeoutError, IncompleteRead) as exc:
            raise ModelManagerError(f"No se pudo completar la descarga; comprueba la conexión y vuelve a ejecutar el Downloader: {exc}") from exc
        except OSError as exc:
            raise ModelManagerError(f"No se puede escribir o leer {target}. Revisa permisos, espacio y antivirus: {exc}") from exc


def extract_safe(archive: Path, directory: Path) -> None:
    """Reject traversal, Windows drive paths, symlinks and unexpectedly large archives before extracting."""
    base = Path(directory).resolve()
    try:
        with zipfile.ZipFile(archive) as package:
            members = package.infolist()
            if len(members) > 10000 or sum(item.file_size for item in members) > 4 * 1024 ** 3:
                raise ModelManagerError("El ZIP excede los límites permitidos.")
            targets = []
            for item in members:
                normalized = item.filename.replace("\\", "/")
                parts = PurePosixPath(normalized)
                if parts.is_absolute() or ".." in parts.parts or ":" in normalized or stat.S_ISLNK(item.external_attr >> 16):
                    raise ModelManagerError(f"Ruta peligrosa dentro del ZIP: {item.filename}")
                destination = (base / Path(*parts.parts)).resolve()
                if not destination.is_relative_to(base):
                    raise ModelManagerError("El ZIP intenta escribir fuera del directorio del motor.")
                targets.append((item, destination))
            base.mkdir(parents=True, exist_ok=True)
            for item, destination in targets:
                if item.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with package.open(item) as source, destination.open("wb") as output:
                        shutil.copyfileobj(source, output, 1024 * 1024)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ModelManagerError(f"No se pudo extraer el motor de {archive}: {exc}") from exc


def install_engine(config_path: Path = CONFIG_PATH, progress=None) -> tuple[Path, bool]:
    with _DOWNLOAD_LOCK:
        locations = layout(config_path)
        if locations["llama_server"].is_file():
            return locations["llama_server"], False
        if locations["settings"].get("llama_server"):
            raise ModelManagerError(f"La ruta llama_server configurada no existe: {locations['llama_server']}. "
                                    "Corrige la ruta o elimina el override para instalar el motor automático.")
        if os.name != "nt" or platform.machine().lower() not in ("amd64", "x86_64"):
            raise ModelManagerError("La instalación automática del motor está preparada para Windows x64 + NVIDIA CUDA. "
                                    "En otros sistemas instala llama.cpp compatible y configura llama_server en runtime.local.json.")
        nvidia_smi = shutil.which("nvidia-smi")
        if not nvidia_smi:
            raise ModelManagerError("No se detectó el controlador NVIDIA (nvidia-smi). Instala el controlador NVIDIA antes de descargar el motor CUDA.")
        try:
            device_check = subprocess.run([nvidia_smi, "-L"], capture_output=True, text=True, timeout=15, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ModelManagerError(f"No se pudo comprobar la GPU NVIDIA antes de descargar: {exc}") from exc
        if device_check.returncode != 0 or "GPU " not in device_check.stdout:
            raise ModelManagerError("nvidia-smi no detectó una GPU NVIDIA activa; no se descargó el motor CUDA.")
        runtime = catalog()["runtime"]
        staging = locations["runtime_dir"] / ("install_" + uuid.uuid4().hex)
        binary_dir = locations["runtime_dir"] / "bin"
        if binary_dir.exists():
            raise ModelManagerError(f"Ya existe {binary_dir} pero falta llama-server. Muévelo manualmente antes de instalar un motor completo.")
        try:
            for artifact in (runtime["binary"], runtime["cuda_runtime"]):
                archive, _ = download_verified(artifact, locations["downloads_dir"] / artifact["filename"], progress)
                extract_safe(archive, staging)
            server = next(staging.rglob("llama-server.exe"), None)
            if server is None:
                raise ModelManagerError("El ZIP no contiene llama-server.exe.")
            # Flatten official archives while rejecting duplicate DLL basenames with different bytes.
            source_files = [path for path in staging.rglob("*") if path.is_file()]
            flat = staging / "flat"
            flat.mkdir()
            for source in source_files:
                if not source.is_file():
                    continue
                destination = flat / source.name
                if destination.exists() and sha256(source) != sha256(destination):
                    raise ModelManagerError(f"El motor contiene un archivo en conflicto: {destination}. No se sobrescribió.")
                if not destination.exists():
                    shutil.copy2(source, destination)
            flat.rename(binary_dir)
            return binary_dir / "llama-server.exe", True
        finally:
            # Staging is a freshly generated child of the validated runtime directory.
            if staging.exists() and staging.resolve().is_relative_to(locations["runtime_dir"].resolve()):
                shutil.rmtree(staging)


def download_model(name: str, install_runtime: bool = True, config_path: Path = CONFIG_PATH,
                   progress=None) -> tuple[ModelHandle, dict]:
    if name not in MODEL_NAMES:
        raise ModelManagerError("Selecciona uno de los tres modelos del catálogo.")
    if type(install_runtime) is not bool:
        raise ModelManagerError("instalar_motor debe ser verdadero o falso.")
    with _DOWNLOAD_LOCK:
        locations = layout(config_path)
        engine_installed = False
        if install_runtime:
            _, engine_installed = install_engine(config_path, progress)
        artifact = catalog()["models"][name]
        model, downloaded = download_verified(artifact, locations["models"][name], progress)
        handle = ModelHandle(name, validate_gguf(model), "Automático", "catálogo SHA256 verificado")
        return handle, {"downloaded": downloaded, "engine_installed": engine_installed, "sha256": artifact["sha256"],
                        "model_path": str(handle.path), "llama_server": str(layout(config_path)["llama_server"])}


def prepare_model(model_file: str, manual_path: str = "", profile: str = "Automático",
                  config_path: Path = CONFIG_PATH, progress=None) -> tuple[ModelHandle, dict]:
    """Prepare a lazy handle; auto-download only an absent catalogue model and missing engine."""
    if not isinstance(model_file, str) or not isinstance(manual_path, str):
        raise ModelManagerError("Selecciona un modelo o escribe una ruta GGUF local como texto.")
    if profile not in PROFILES:
        raise ModelManagerError("Perfil desconocido. Selecciona un perfil del nodo.")
    with _DOWNLOAD_LOCK:
        locations = layout(config_path)
        selected_catalogue = not manual_path.strip() and model_file in MODEL_NAMES
        if selected_catalogue and not locations["models"][model_file].exists():
            handle, metadata = download_model(model_file, True, config_path, progress)
            if handle.profile != profile:
                handle = ModelHandle(handle.name, handle.path, profile, handle.source)
            metadata["source_mode"] = "catálogo"
            return handle, metadata
        # A manual/local path is always validated before any engine installation, with no fallback.
        # Existing catalogue files also fail explicitly if corrupt; they are never silently replaced.
        handle = load_model(model_file, manual_path, profile, config_path)
        engine, installed = install_engine(config_path, progress)
        return handle, {"downloaded": False, "engine_installed": installed,
                        "model_path": str(handle.path), "llama_server": str(engine),
                        "source_mode": "catálogo" if selected_catalogue else "GGUF local/manual"}
