"""Disposable checkout and diagnostic helpers for the public workflow checks."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
GENERATED = (".venv", ".env", "db.sqlite3", "theme/static_src/node_modules",
             "theme/static/css/dist/styles.css", "staticfiles")


class VerificationError(RuntimeError):
    """A public starter workflow did not meet its release contract."""


def copy_checkout(source: Path, destination: Path) -> None:
    """Copy tracked source only, never the caller's environment or build outputs."""
    result = subprocess.run(["git", "ls-files", "-z"], cwd=source, check=True,
                            capture_output=True)
    destination.mkdir(parents=True)
    for filename in result.stdout.decode("utf-8").split("\0"):
        if not filename:
            continue
        relative = Path(filename)
        if relative.is_absolute() or ".." in relative.parts:
            raise VerificationError("The checkout contains an unsafe tracked path.")
        if any(relative == Path(path) or Path(path) in relative.parents for path in GENERATED):
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    for filename in GENERATED:
        if (destination / filename).exists():
            raise VerificationError(f"Fresh fixture unexpectedly contains {filename}.")


def isolated_environment(cache: Path | None = None) -> dict[str, str]:
    """Avoid a developer's active environment/configuration masking setup errors."""
    excluded = {"VIRTUAL_ENV", "PYTHONPATH", "NPM_BIN_PATH", "UV_PROJECT_ENVIRONMENT",
                "UV_ACTIVE", "PIP_REQUIRE_VIRTUALENV", "PYTHON_DOTENV_DISABLED"}
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("DJANGO_") and key not in excluded}
    environment.update(UV_PYTHON_DOWNLOADS="never", PIP_DISABLE_PIP_VERSION_CHECK="1")
    if cache is not None:
        environment.update(UV_CACHE_DIR=str(cache / "uv"), PIP_CACHE_DIR=str(cache / "pip"),
                           npm_config_cache=str(cache / "npm"))
    return environment


@dataclass
class Checkout:
    root: Path
    caller: Path
    environment: dict[str, str]

    @property
    def python(self) -> Path:
        return self.root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


@contextmanager
def disposable_checkout(source: Path = ROOT, *, cold: bool = False):
    with tempfile.TemporaryDirectory(prefix="starter-verification-") as directory:
        temporary = Path(directory).resolve()
        project = temporary / "checkout with spaces"
        copy_checkout(source, project)
        caller = temporary / "unrelated working directory"
        caller.mkdir()
        yield Checkout(project, caller, isolated_environment(temporary / "empty caches" if cold else None))


class CommandLog:
    """Keep command output, with known generated secrets removed, for CI diagnostics."""

    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        self.secrets: list[str] = []

    def redact(self, text: str) -> str:
        for secret in self.secrets:
            if secret:
                text = text.replace(secret, "[redacted]")
        return text

    def write(self, name: str, text: str) -> None:
        (self.directory / f"{name}.log").write_text(self.redact(text), encoding="utf-8")

    def run(self, name: str, command, *, cwd: Path, env: dict[str, str], timeout: int = 900):
        print(f"[{name}] Running public workflow check", flush=True)
        result = subprocess.run([str(part) for part in command], cwd=cwd, env=env,
                                capture_output=True, text=True, timeout=timeout)
        output = result.stdout + result.stderr
        self.write(name, output)
        if result.returncode:
            raise VerificationError(f"{name} failed with exit code {result.returncode}; "
                                    f"see {self.directory / (name + '.log')}")
        return result
