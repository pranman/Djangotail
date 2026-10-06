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
import subprocess
import sys


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
    npm_override = os.environ.get("NPM_BIN_PATH")
    npm = shutil.which(npm_override or "npm")
    if not npm:
        raise BootstrapError("npm is missing or NPM_BIN_PATH is invalid. Install npm 10 or "
                             "newer with Node.js and check PATH.")
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


def setup(layout: Layout, tools: Prerequisites) -> None:
    # Check all inputs before creating files or installing anything.
    require_files(layout, (".env.example", "manage.py", "theme/static_src/package.json",
                           "theme/static_src/package-lock.json"))
    provision_python(layout, tools)
    provision_configuration(layout)
    provision_frontend(layout, tools)


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
    print("Prerequisites are supported. No project files were changed.")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("command", choices=("setup", "dev", "check"), default="setup", nargs="?",
                        help="setup (default), development server, or read-only diagnostics")
    result.add_argument("--installer", choices=("auto", "uv", "pip"), default="auto",
                        help="prefer uv when available, otherwise pip (setup only)")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        layout = Layout()
        tools = prerequisites(args.installer, layout=layout)
        if args.command == "check":
            diagnostics(layout, tools)
        elif args.command == "setup":
            setup(layout, tools)
        else:
            raise BootstrapError("Development supervision is not implemented yet.")
    except BootstrapError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted. You can safely rerun the same command.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
