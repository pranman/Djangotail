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


def reserve_port():
    import socket
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    return server


def wait_until(predicate, message, *, timeout=30):
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise VerificationError(message)


def port_is_closed(port):
    import socket
    with socket.socket() as probe:
        probe.settimeout(0.2)
        return probe.connect_ex(("127.0.0.1", port)) != 0


@contextmanager
def development_server(checkout, log):
    """Run the real public launcher and verify its HTTP server stops on interruption."""
    import signal
    import sys
    from urllib.error import URLError
    from urllib.request import urlopen

    with reserve_port() as reservation:
        port = reservation.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    filename = log.directory / "development.log"
    options = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
               else {"start_new_session": True})
    with filename.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [sys.executable, str(checkout.root / "bootstrap.py"), "dev", "--port", str(port)],
            cwd=checkout.caller, env=checkout.environment, stdout=output, stderr=subprocess.STDOUT,
            **options,
        )
        try:
            def ready():
                if process.poll() is not None:
                    raise VerificationError(f"Development launcher exited early ({process.returncode}).")
                try:
                    with urlopen(base_url, timeout=1) as response:
                        return response.status == 200
                except (URLError, TimeoutError):
                    return False
            wait_until(ready, "Django did not become ready; see development.log.", timeout=60)
            yield base_url
        finally:
            if process.poll() is None:
                process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise VerificationError("Development launcher did not stop after interruption.")
            # Bootstrap's focused regression suite additionally proves its watcher
            # and server grandchildren are cleaned up on every supported OS.
            wait_until(lambda: port_is_closed(port), "Django still responds after launcher cleanup.")
    log.write("development", filename.read_text(encoding="utf-8"))


def verify_lifecycle(checkout, log, browser_check=None):
    import json
    import sys
    with reserve_port() as busy:
        port = busy.getsockname()[1]
        result = subprocess.run(
            [sys.executable, str(checkout.root / "bootstrap.py"), "dev", "--port", str(port)],
            cwd=checkout.caller, env=checkout.environment, capture_output=True, text=True, timeout=30,
        )
        log.write("occupied-port", result.stdout + result.stderr)
        if result.returncode != 1 or "Cannot bind" not in result.stderr:
            raise VerificationError("An occupied port did not cause an actionable launcher failure.")
        if "Starting Django" in result.stdout or "Starting CSS watcher" in result.stdout:
            raise VerificationError("The launcher started children despite an occupied port.")
    with development_server(checkout, log) as base_url:
        source = checkout.root / "theme/static_src/src/styles.css"
        compiled = checkout.root / "theme/static/css/dist/styles.css"
        original = source.read_bytes()
        try:
            with source.open("a", encoding="utf-8") as output:
                output.write("\n.ci-watcher-probe { --starter-watch-check: 12345; }\n")
            wait_until(lambda: "--starter-watch-check" in compiled.read_text(encoding="utf-8"),
                       "The public launcher's CSS watcher did not rebuild changed source.")
        finally:
            source.write_bytes(original)
        if browser_check is not None:
            browser_check(base_url)

    # Trigger a real npm watcher failure in the disposable fixture, then ensure
    # the actual Django process is also stopped by the public launcher.
    package_file = checkout.root / "theme/static_src/package.json"
    original = package_file.read_bytes()
    package = json.loads(original)
    package["scripts"]["dev"] = 'node -e "process.exit(7)"'
    with reserve_port() as reservation:
        port = reservation.getsockname()[1]
    try:
        package_file.write_text(json.dumps(package), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(checkout.root / "bootstrap.py"), "dev", "--port", str(port)],
            cwd=checkout.caller, env=checkout.environment, capture_output=True, text=True, timeout=60,
        )
        log.write("watcher-failure", result.stdout + result.stderr)
        if result.returncode != 1 or "CSS watcher exited with code" not in result.stderr:
            raise VerificationError("A failed CSS watcher did not stop the development launcher.")
        wait_until(lambda: port_is_closed(port), "Django survived a failed CSS watcher.")
    finally:
        package_file.write_bytes(original)
    print("Development readiness, watching, occupied ports, interruption and failure verified.", flush=True)
