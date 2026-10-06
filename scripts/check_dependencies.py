"""Verify exports and clean uv/pip installs without changing the checkout."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import venv

ROOT = Path(__file__).resolve().parents[1]


def run(args, *, cwd=ROOT, env=None, capture=False):
    return subprocess.run(
        [str(arg) for arg in args], cwd=cwd, env=env, check=True,
        text=True, stdout=subprocess.PIPE if capture else None,
    )


def check_exports(uv):
    run([uv, "lock", "--check"])
    for filename, flags in (("requirements.txt", ["--no-dev"]),
                            ("requirements-dev.txt", [])):
        result = run([uv, "export", "--frozen", *flags, "--no-emit-project",
                      "--format", "requirements-txt", "--no-header"], capture=True)
        # The generated command header depends on stdout vs --output-file.
        expected = "\n".join(line for line in (ROOT / filename).read_text().splitlines()
                             if not line.startswith("# This file")
                             and not line.startswith("#    uv export"))
        if result.stdout.strip() != expected.strip():
            raise RuntimeError(f"{filename} is stale; regenerate the dependency exports.")
    print("Dependency lock and pip exports are synchronized.")


def installed_packages(python, project, env):
    result = run([python, "-c", "import importlib.metadata as m,json; "
                  "print(json.dumps({d.metadata['Name'].lower().replace('_','-'):d.version "
                  "for d in m.distributions() if d.metadata['Name'].lower() "
                  "not in ('pip','setuptools','wheel')}))"],
                 cwd=project, env=env, capture=True)
    return json.loads(result.stdout)


def verify_install(installer, uv, directory):
    project = directory / installer
    shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns(
        ".git", ".venv", "venv", "node_modules", ".env", "*.sqlite3",
        "__pycache__", "staticfiles", "test-results", "playwright-report"))
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env.update(DJANGO_SECRET_KEY=secrets.token_urlsafe(64), DJANGO_DEBUG="true",
               DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,testserver")
    environment = project / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if installer == "uv":
        run([uv, "sync", "--frozen", "--python", sys.executable], cwd=project, env=env)
        run([uv, "pip", "check", "--python", python], cwd=project, env=env)
    else:
        venv.EnvBuilder(with_pip=True).create(environment)
        run([python, "-m", "pip", "install", "--disable-pip-version-check",
             "--require-hashes", "-r", "requirements-dev.txt"], cwd=project, env=env)
        run([python, "-m", "pip", "check"], cwd=project, env=env)
    run([python, "manage.py", "check"], cwd=project, env=env)
    run([python, "manage.py", "migrate", "--noinput"], cwd=project, env=env)
    return installed_packages(python, project, env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", choices=("uv", "pip", "both"), default="both")
    parser.add_argument("--check-exports", action="store_true")
    parser.add_argument("--exports-only", action="store_true")
    args = parser.parse_args()
    uv = shutil.which("uv")
    if (args.installer != "pip" or args.check_exports or args.exports_only) and not uv:
        parser.error("uv must be on PATH for uv installation or export checks")
    if args.check_exports or args.exports_only:
        check_exports(uv)
    if args.exports_only:
        return
    installers = ("uv", "pip") if args.installer == "both" else (args.installer,)
    with tempfile.TemporaryDirectory(prefix="starter-dependencies-") as temp:
        inventories = [verify_install(name, uv, Path(temp)) for name in installers]
    if len(inventories) == 2 and inventories[0] != inventories[1]:
        raise RuntimeError(f"uv and pip resolved different environments: {inventories}")
    print(f"Verified {', '.join(installers)} on Python {sys.version.split()[0]}.")


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, RuntimeError) as error:
        print(f"Dependency verification failed: {error}", file=sys.stderr)
        sys.exit(1)
