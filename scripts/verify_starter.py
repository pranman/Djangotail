"""Exercise public setup in a disposable checkout; never alter local user data."""

from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys
import subprocess

from starter_checks import CommandLog, VerificationError, disposable_checkout, verify_lifecycle


def verify_setup(checkout, installer, log):
    command = [sys.executable, checkout.root / "bootstrap.py", "--installer", installer]
    log.run("setup", command, cwd=checkout.caller, env=checkout.environment)
    configuration = checkout.root / ".env"
    if not configuration.is_file():
        raise VerificationError("Setup did not create local configuration.")
    for line in configuration.read_text(encoding="utf-8").splitlines():
        if line.startswith("DJANGO_SECRET_KEY="):
            log.secrets.append(line.partition("=")[2])
    if not log.secrets or not log.secrets[-1]:
        raise VerificationError("Setup did not generate a nonempty local secret.")
    with configuration.open("a", encoding="utf-8") as output:
        output.write("\n# Retain caller customization when setup runs again.\nSTARTER_VERIFICATION_SENTINEL=preserved\n")
    original_configuration = configuration.read_bytes()
    database = checkout.root / "db.sqlite3"
    if not database.is_file():
        raise VerificationError("Setup did not create the local database.")
    with sqlite3.connect(database) as connection:
        if not connection.execute("SELECT count(*) FROM django_migrations").fetchone()[0]:
            raise VerificationError("Setup did not apply Django migrations.")
        connection.execute("CREATE TABLE workflow_sentinel (value TEXT NOT NULL)")
        connection.execute("INSERT INTO workflow_sentinel VALUES ('preserved')")
    css = checkout.root / "theme/static/css/dist/styles.css"
    if not css.is_file() or css.stat().st_size == 0:
        raise VerificationError("Setup did not compile a stylesheet.")
    log.run("setup-rerun", command, cwd=checkout.caller, env=checkout.environment)
    if configuration.read_bytes() != original_configuration:
        raise VerificationError("Repeated setup changed existing configuration or its secret.")
    with sqlite3.connect(database) as connection:
        if connection.execute("SELECT value FROM workflow_sentinel").fetchall() != [("preserved",)]:
            raise VerificationError("Repeated setup changed existing database records.")
    log.run("python-regressions", [checkout.python, "-m", "unittest", "discover", "-v"],
            cwd=checkout.root, env=checkout.environment)
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    log.run("frontend-regressions", [npm, "test"], cwd=checkout.root / "theme/static_src",
            env=checkout.environment)
    print("Setup and repetition preserved configuration, secret, and database records.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", choices=("uv", "pip"), required=True)
    parser.add_argument("--cold", action="store_true", help="use new empty uv, pip and npm caches")
    parser.add_argument("--artifacts", type=Path, default=Path("verification-artifacts"))
    args = parser.parse_args()
    log = CommandLog(args.artifacts.resolve())
    try:
        with disposable_checkout(cold=args.cold) as checkout:
            verify_setup(checkout, args.installer, log)
            verify_lifecycle(checkout, log)
    except (VerificationError, OSError, sqlite3.Error, subprocess.TimeoutExpired) as error:
        print(f"Starter verification failed: {log.redact(str(error))}", file=sys.stderr)
        return 1
    print("Starter workflow verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
