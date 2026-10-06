"""Small, explicit parsers for the project environment contract."""

import os
from pathlib import Path
import shutil
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


def load_environment(base_dir):
    """Read only this project's .env; exported variables always win."""
    load_dotenv(base_dir / ".env", override=False)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ImproperlyConfigured(
        f"{name} must be true or false (also accepts 1/0, yes/no, on/off)."
    )


def env_list(name):
    """Parse comma-separated values, rejecting accidental empty entries."""
    value = os.environ.get(name, "").strip()
    if not value:
        return []
    values = [item.strip() for item in value.split(",")]
    if any(not item or any(char.isspace() for char in item) for item in values):
        raise ImproperlyConfigured(
            f"{name} must be a comma-separated list without empty entries "
            "or whitespace inside a value."
        )
    return values


def env_required(name):
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise ImproperlyConfigured(
            f"{name} is required. Set it in the environment or the project-root .env "
            "file; use the root bootstrap script for local development."
        )
    return value


def env_nonnegative_int(name, default=0):
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        raise ImproperlyConfigured(f"{name} must be a nonnegative integer.") from None
    if value < 0:
        raise ImproperlyConfigured(f"{name} must be a nonnegative integer.")
    return value


def csrf_origins():
    name = "DJANGO_CSRF_TRUSTED_ORIGINS"
    origins = env_list(name)
    for origin in origins:
        try:
            parsed = urlsplit(origin)
            valid = (
                parsed.scheme in {"http", "https"}
                and parsed.hostname
                and not parsed.username
                and not parsed.password
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
            )
            # Accessing port checks malformed/non-numeric/out-of-range values.
            parsed.port
        except ValueError:
            valid = False
        if not valid:
            raise ImproperlyConfigured(
                f"{name} entries must be origins such as https://example.com "
                "(optional port, no path, query or credentials)."
            )
    return origins


def npm_executable(base_dir):
    """Resolve npm lazily: Django can serve prebuilt CSS without Node installed."""
    if "NPM_BIN_PATH" in os.environ:
        override = env_required("NPM_BIN_PATH")
        path = Path(override).expanduser()
        # Keep bare executable names on PATH. Resolve relative paths against the
        # repository, matching .env loading regardless of the caller's directory.
        if path.is_absolute():
            return str(path)
        if path.parent != Path("."):
            return str(base_dir / path)
        return override
    executable = "npm.cmd" if os.name == "nt" else "npm"
    return shutil.which(executable) or executable
