#!/usr/bin/env python3
"""Set up and run the starter with the Python standard library."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent
SUPPORTED_PYTHON = (3, 12), (3, 13), (3, 14)
SUPPORTED_NODE = (22, 24)


class BootstrapError(Exception):
    """An actionable setup or development error."""


@dataclass(frozen=True)
class Layout:
    root: Path = ROOT

    @property
    def environment(self) -> Path:
        return self.root / ".venv"

    @property
    def python(self) -> Path:
        return self.environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    @property
    def frontend(self) -> Path:
        return self.root / "theme/static_src"


@dataclass(frozen=True)
class Prerequisites:
    npm: str
    installer: str
    uv: str | None


def run(command: list[str], *, cwd: Path = ROOT, capture: bool = False,
        env: dict[str, str] | None = None) -> str:
    """Run one command without a shell, stopping at the first failure."""
    if not capture:
        print(f"→ {' '.join(command)}", flush=True)
    try:
        result = subprocess.run(command, cwd=cwd, check=True, text=True, env=env,
                                stdout=subprocess.PIPE if capture else None,
                                stderr=subprocess.PIPE if capture else None)
    except FileNotFoundError as exc:
        raise BootstrapError(f"Cannot find {command[0]}. Check its installation and PATH.") from exc
    except OSError as exc:
        raise BootstrapError(f"Cannot run {command[0]}: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        # Captured diagnostic output can include local configuration; do not echo it.
        raise BootstrapError(f"{command[0]} failed with exit code {exc.returncode}. "
                             "Resolve the error and rerun the same bootstrap command.") from exc
    return result.stdout.strip() if capture else ""


def npm_override(layout: Layout) -> str | None:
    """Read the optional literal npm path without needing python-dotenv installed."""
    if "NPM_BIN_PATH" in os.environ:
        value = os.environ["NPM_BIN_PATH"]
        if not value.strip():
            raise BootstrapError("NPM_BIN_PATH must not be blank. Remove it to discover npm on PATH.")
        return value
    config = layout.root / ".env"
    if not config.is_file():
        return None
    value = None
    for line in config.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*(?:export\s+)?NPM_BIN_PATH\s*=\s*(.*)$", line)
        if match:
            value = match.group(1).strip()
            if value.startswith(("'", '"')):
                quote = value[0]
                quoted = re.match(r"^(['\"])((?:\\.|[^\\])*?)\1\s*(?:#.*)?$", value)
                if quoted is None:
                    raise BootstrapError("NPM_BIN_PATH in .env has invalid quoting.")
                value = quoted.group(2)
                escapes = {"\\": "\\", "'": "'"}
                if quote == '"':
                    escapes.update({'"': '"', "a": "\a", "b": "\b", "f": "\f",
                                    "n": "\n", "r": "\r", "t": "\t", "v": "\v"})
                value = re.sub(r"\\(.)", lambda m: escapes.get(m.group(1), m.group(0)), value)
            else:
                value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
    if value is not None:
        if not value.strip():
            raise BootstrapError("NPM_BIN_PATH must not be blank. Remove it to discover npm on PATH.")
        if "${" in value:
            raise BootstrapError("Use a literal NPM_BIN_PATH in .env, or export its resolved path "
                                 "before bootstrap; interpolation requires installed dependencies.")
    return value


def prerequisites(installer: str = "auto", *, layout: Layout = Layout()) -> Prerequisites:
    if sys.version_info[:2] not in SUPPORTED_PYTHON:
        raise BootstrapError("Use Python 3.12, 3.13, or 3.14 to run bootstrap.py.")
    node = shutil.which("node")
    if not node:
        raise BootstrapError("Node.js is missing. Install Node.js LTS 22 or 24, reopen your "
                             "terminal, and rerun this command.")
    node_version = run([node, "--version"], cwd=layout.root, capture=True)
    match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", node_version)
    version = tuple(map(int, match.groups())) if match else ()
    if not version or version[0] not in SUPPORTED_NODE or version < (22, 10, 0):
        raise BootstrapError(f"Node.js {node_version} is unsupported. Use Node.js 22.10+ or 24 LTS.")
    override = npm_override(layout)
    if override:
        override = str(Path(override).expanduser())
    if override and not Path(override).is_absolute() and ("/" in override or "\\" in override):
        override = str(layout.root / override)
    npm = shutil.which(override or "npm")
    if not npm:
        raise BootstrapError("npm is missing or NPM_BIN_PATH is invalid. Install npm 10 or "
                             "11 with Node.js and check PATH.")
    npm_version = run([npm, "--version"], cwd=layout.root, capture=True)
    match = re.match(r"^(\d+)\.", npm_version)
    if not match or not 10 <= int(match.group(1)) < 12:
        raise BootstrapError(f"npm {npm_version} is unsupported. Use npm 10 or 11.")
    uv = shutil.which("uv")
    if installer == "uv" and not uv:
        raise BootstrapError("uv was requested but is missing. Install uv or use --installer pip.")
    selected = "uv" if installer == "uv" or installer == "auto" and uv else "pip"
    return Prerequisites(npm=npm, installer=selected, uv=uv)


def require_files(layout: Layout, filenames: tuple[str, ...]) -> None:
    for filename in filenames:
        if not (layout.root / filename).is_file():
            raise BootstrapError(f"Required project file {filename} is missing. "
                                 "Restore it from the repository and rerun setup.")


def validate_environment(layout: Layout) -> None:
    """Refuse partial, moved, or incompatible environments without destroying them."""
    if not layout.python.is_file():
        raise BootstrapError(".venv exists but its Python is missing. Move .venv aside, then "
                             "rerun setup to create a new environment; existing data is preserved.")
    probe = ("import json,sys; print(json.dumps({'version':list(sys.version_info[:2]),"
             "'prefix':sys.prefix,'base_prefix':sys.base_prefix}))")
    try:
        info = json.loads(run([str(layout.python), "-I", "-c", probe],
                              cwd=layout.root, capture=True))
        valid = (tuple(info["version"]) in SUPPORTED_PYTHON
                 and Path(info["prefix"]).resolve() == layout.environment.resolve()
                 and info["prefix"] != info["base_prefix"])
    except (BootstrapError, ValueError, KeyError, TypeError):
        valid = False
    if not valid:
        raise BootstrapError(".venv is incompatible or damaged. Move it aside and rerun with "
                             "Python 3.12–3.14. Bootstrap will not delete an existing environment.")


def provision_python(layout: Layout, tools: Prerequisites) -> None:
    if tools.installer == "uv":
        require_files(layout, ("pyproject.toml", "uv.lock"))
    else:
        require_files(layout, ("requirements-dev.txt", "requirements.txt"))
    if layout.environment.exists():
        validate_environment(layout)
    else:
        # stdlib venv includes pip, so switching installers later remains possible.
        run([sys.executable, "-m", "venv", str(layout.environment)], cwd=layout.root)
        validate_environment(layout)
    if tools.installer == "uv":
        env = dict(os.environ, UV_PROJECT_ENVIRONMENT=str(layout.environment),
                   UV_PYTHON_DOWNLOADS="never")
        run([str(tools.uv), "sync", "--frozen", "--project", str(layout.root),
             "--python", str(layout.python)], cwd=layout.root, env=env)
    else:
        try:
            run([str(layout.python), "-m", "pip", "--version"], cwd=layout.root, capture=True)
        except BootstrapError:
            # Environments created with `uv sync` may deliberately omit pip.
            run([str(layout.python), "-m", "ensurepip", "--upgrade"], cwd=layout.root)
        run([str(layout.python), "-m", "pip", "install", "--require-hashes",
             "-r", str(layout.root / "requirements-dev.txt")], cwd=layout.root)


def provision_configuration(layout: Layout) -> None:
    destination = layout.root / ".env"
    if destination.exists() or destination.is_symlink():
        if not destination.is_file():
            raise BootstrapError(".env exists but is not a readable file. Fix it before setup.")
        print("Keeping existing .env and its secret.")
        return
    template = (layout.root / ".env.example").read_text(encoding="utf-8")
    content, count = re.subn(r"(?m)^DJANGO_SECRET_KEY=.*$",
                            f"DJANGO_SECRET_KEY={secrets.token_urlsafe(50)}", template)
    if count != 1:
        raise BootstrapError(".env.example must contain exactly one DJANGO_SECRET_KEY setting.")
    content, count = re.subn(r"(?m)^DJANGO_DEBUG=.*$", "DJANGO_DEBUG=True", content)
    if count != 1:
        raise BootstrapError(".env.example must contain exactly one DJANGO_DEBUG setting.")
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        # Another setup may have written the file after our initial check.
        print("Keeping .env created by another process.")
        return
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as config:
        config.write(content)
    print("Created .env with a unique local secret and debug enabled.")


def provision_frontend(layout: Layout, tools: Prerequisites) -> None:
    run([tools.npm, "ci"], cwd=layout.frontend)


def finish_setup(layout: Layout, tools: Prerequisites) -> None:
    run([str(layout.python), "manage.py", "migrate", "--noinput"], cwd=layout.root)
    run([tools.npm, "run", "build"], cwd=layout.frontend)
    run([str(layout.python), "manage.py", "check"], cwd=layout.root)


def setup(layout: Layout, tools: Prerequisites) -> None:
    # Check all inputs before creating files or installing anything.
    require_files(layout, (".env.example", "manage.py", "theme/static_src/package.json",
                           "theme/static_src/package-lock.json"))
    provision_python(layout, tools)
    provision_configuration(layout)
    provision_frontend(layout, tools)
    finish_setup(layout, tools)
    print("\nSetup complete. Start development with: python bootstrap.py dev")


class WindowsJob:
    """Keep every Windows descendant in a kill-on-close Job Object."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                        ("flags", wintypes.DWORD), ("min_working_set", ctypes.c_size_t),
                        ("max_working_set", ctypes.c_size_t), ("active_limit", wintypes.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                        ("scheduling", wintypes.DWORD)]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("basic", BasicLimits), ("io", ctypes.c_uint64 * 6),
                        ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                        ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]

        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int,
                                                     ctypes.c_void_p, wintypes.DWORD)
        self.api.SetInformationJobObject.restype = wintypes.BOOL
        self.api.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self.api.OpenProcess.restype = wintypes.HANDLE
        self.api.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        self.api.AssignProcessToJobObject.restype = wintypes.BOOL
        self.api.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.api.CloseHandle.restype = wintypes.BOOL
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits),
                                                ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def attach(self, pid: int) -> None:
        import ctypes
        # PROCESS_SET_QUOTA | PROCESS_TERMINATE are required for assignment.
        handle = self.api.OpenProcess(0x0100 | 0x0001, False, pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.api.AssignProcessToJobObject(self.handle, handle):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.api.CloseHandle(handle)

    def close(self) -> None:
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen
    job: WindowsJob | None = None


def start_process(name: str, command: list[str], cwd: Path) -> ManagedProcess:
    print(f"Starting {name}…", flush=True)
    if os.name != "nt":
        return ManagedProcess(name, subprocess.Popen(command, cwd=cwd, start_new_session=True))
    # Gate the wrapper on stdin so it cannot spawn anything until its Job Object
    # owns it. Assigning an already-running npm or autoreloader has an orphan race.
    job = WindowsJob()
    process = None
    try:
        process = subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve()), "_child"],
                                   cwd=cwd, stdin=subprocess.PIPE, text=True,
                                   creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        job.attach(process.pid)
        process.stdin.write(json.dumps(command) + "\n")
        process.stdin.close()
        return ManagedProcess(name, process, job)
    except BaseException:
        job.close()
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
        raise


def stop_processes(processes: list[ManagedProcess], grace: float = 5.0) -> None:
    """Stop entire groups even if a direct child has already exited."""
    for child in processes:
        try:
            if os.name == "nt":
                if child.process.poll() is None:
                    child.process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(child.process.pid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
    deadline = time.monotonic() + grace
    for child in processes:
        try:
            child.process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    for child in processes:
        if child.job is not None:
            child.job.close()  # Includes children whose direct parent already exited.
        else:
            try:
                os.killpg(child.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        child.process.wait()


def supervise(commands: list[tuple[str, list[str], Path]]) -> None:
    children: list[ManagedProcess] = []
    previous_term = signal.getsignal(signal.SIGTERM)
    previous_int = signal.getsignal(signal.SIGINT)
    previous_break = signal.getsignal(signal.SIGBREAK) if os.name == "nt" else None
    stopping = False

    def interrupted(signum: int, frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    if os.name == "nt":
        signal.signal(signal.SIGBREAK, interrupted)
    try:
        for name, command, cwd in commands:
            if stopping:
                raise KeyboardInterrupt
            try:
                children.append(start_process(name, command, cwd))
            except OSError as exc:
                raise BootstrapError(f"Cannot start {name}: {exc}") from exc
        print("Development processes are running. Press Ctrl+C to stop both.", flush=True)
        while True:
            if stopping:
                raise KeyboardInterrupt
            for child in children:
                code = child.process.poll()
                if code is not None:
                    raise BootstrapError(f"{child.name} exited with code {code}; stopping development.")
            time.sleep(0.1)
    finally:
        # A second Ctrl+C must not interrupt cleanup and leave managed descendants.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if os.name == "nt":
            signal.signal(signal.SIGBREAK, signal.SIG_IGN)
        try:
            stop_processes(children)
        finally:
            signal.signal(signal.SIGINT, previous_int)
            signal.signal(signal.SIGTERM, previous_term)
            if os.name == "nt":
                signal.signal(signal.SIGBREAK, previous_break)


def ensure_port_available(host: str, port: int) -> None:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            if os.name == "nt":
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((host, port))
    except OSError as exc:
        raise BootstrapError(f"Cannot bind {host}:{port}: {exc}. Stop the other server or "
                             "choose --host and --port for an available local address.") from exc


def dev(layout: Layout, tools: Prerequisites, host: str, port: int) -> None:
    if not layout.environment.exists() or not (layout.root / ".env").is_file():
        raise BootstrapError("The project is not set up. Run python bootstrap.py first.")
    validate_environment(layout)
    if not (layout.frontend / "node_modules").is_dir():
        raise BootstrapError("Frontend dependencies are missing. Run python bootstrap.py first.")
    ensure_port_available(host, port)
    run([str(layout.python), "manage.py", "check"], cwd=layout.root)
    run([tools.npm, "run", "build"], cwd=layout.frontend)
    address = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
    django = [str(layout.python), "manage.py", "runserver", address]
    if ":" in host:
        django.append("--ipv6")
    supervise([("Django", django, layout.root),
               ("CSS watcher", [tools.npm, "run", "dev"], layout.frontend)])


def child_wrapper() -> int:
    """Internal Windows gate; a closed pipe means the parent could not attach us."""
    line = sys.stdin.readline()
    if not line:
        return 1
    try:
        return subprocess.call(json.loads(line), stdin=subprocess.DEVNULL)
    except KeyboardInterrupt:
        return 130


def diagnostics(layout: Layout, tools: Prerequisites) -> None:
    print(f"Project: {layout.root}")
    print(f"Python: {sys.version_info.major}.{sys.version_info.minor}")
    print(f"Installer: {tools.installer}")
    if layout.environment.exists():
        validate_environment(layout)
        print("Managed .venv: compatible")
    else:
        print("Managed .venv: absent; run python bootstrap.py to create it")
    print("Local .env: " + ("present (values hidden)" if (layout.root / ".env").is_file()
                            else "absent; setup will create it"))
    print("Frontend dependencies: " + ("present" if (layout.frontend / "node_modules").is_dir()
                                       else "absent; setup will install them"))
    if layout.python.is_file() and (layout.root / ".env").is_file():
        run([str(layout.python), "-B", "manage.py", "check"], cwd=layout.root, capture=True)
        print("Django configuration: valid")
    print("Prerequisites are supported. No project files were changed.")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("command", choices=("setup", "dev", "check"), default="setup", nargs="?",
                        help="setup (default), development server, or read-only diagnostics")
    result.add_argument("--installer", choices=("auto", "uv", "pip"), default="auto",
                        help="prefer uv when available, otherwise pip (setup only)")
    result.add_argument("--host", default="127.0.0.1", help="development bind address")
    result.add_argument("--port", type=int, default=8000, help="development port (default: 8000)")
    return result


def main(argv: list[str] | None = None) -> int:
    if (sys.argv[1:] if argv is None else argv) == ["_child"]:
        return child_wrapper()
    args = parser().parse_args(argv)
    try:
        if not 1 <= args.port <= 65535:
            raise BootstrapError("--port must be between 1 and 65535.")
        layout = Layout()
        tools = prerequisites(args.installer, layout=layout)
        if args.command == "check":
            diagnostics(layout, tools)
        elif args.command == "setup":
            setup(layout, tools)
        else:
            dev(layout, tools, args.host, args.port)
    except BootstrapError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: {exc}. Check file permissions and rerun the same command.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted. You can safely rerun the same command.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
