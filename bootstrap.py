#!/usr/bin/env python3
"""Set up and run the starter with the Python standard library."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
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


def run(command: list[str], *, cwd: Path = ROOT, capture: bool = False) -> str:
    """Run one command without a shell, stopping at the first failure."""
    if not capture:
        print(f"→ {' '.join(command)}", flush=True)
    try:
        result = subprocess.run(command, cwd=cwd, check=True, text=True,
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
    match = re.match(r"^v?(\d+)\.", node_version)
    if not match or int(match.group(1)) not in SUPPORTED_NODE:
        raise BootstrapError(f"Node.js {node_version} is unsupported. Use Node.js LTS 22 or 24.")
    npm_override = os.environ.get("NPM_BIN_PATH")
    npm = shutil.which(npm_override or "npm")
    if not npm:
        raise BootstrapError("npm is missing or NPM_BIN_PATH is invalid. Install npm 10 or "
                             "newer with Node.js and check PATH.")
    npm_version = run([npm, "--version"], cwd=layout.root, capture=True)
    match = re.match(r"^(\d+)\.", npm_version)
    if not match or int(match.group(1)) < 10:
        raise BootstrapError(f"npm {npm_version} is unsupported. Use npm 10 or newer.")
    uv = shutil.which("uv")
    if installer == "uv" and not uv:
        raise BootstrapError("uv was requested but is missing. Install uv or use --installer pip.")
    selected = "uv" if installer == "uv" or installer == "auto" and uv else "pip"
    return Prerequisites(npm=npm, installer=selected, uv=uv)


def diagnostics(layout: Layout, tools: Prerequisites) -> None:
    print(f"Project: {layout.root}")
    print(f"Python: {sys.version_info.major}.{sys.version_info.minor}")
    print(f"Installer: {tools.installer}")
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
        else:
            raise BootstrapError("Setup and development provisioning are not implemented yet.")
    except BootstrapError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted. You can safely rerun the same command.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
