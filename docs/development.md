# Development

Run setup from the repository root, then start both development processes:

```bash
python bootstrap.py
python bootstrap.py dev
```

Use a supported Python interpreter (`python3` or `py -3.13` where appropriate).
The script invokes `.venv` directly. It builds initial CSS before serving,
starts Django with its normal Python autoreloader, and starts the Tailwind
watcher. Ctrl+C stops both process trees; a child failure stops the other child
and returns a failure status. Use `--port 8001` if the default port is occupied.

## What reloads

With `DJANGO_DEBUG=true`, `django-browser-reload` refreshes the browser after
template and compiled CSS changes. Tailwind watches the stylesheet and scanned
source files. Django restarts its server after Python changes. Restart the
development command after changing `.env`, and rerun setup after dependency
changes. New source directories may require an explicit CSS `@source` entry.

The combined command works through the root launcher on Windows too. The
upstream Honcho-based `manage.py tailwind dev` command is not the supported
cross-platform entry point for this starter.

## Project layout

```text
bootstrap.py                         setup, diagnostics and development lifecycle
Project/settings.py                  Django settings
Project/configuration.py             environment parsing and npm discovery
Project/urls.py                      URL routing
MainApp/views.py                     home view
templates/base.html                  shared layout and extension blocks
MainApp/templates/MainApp/home.html  demo page
MainApp/static/MainApp/js/demo.js    local demo interactions
theme/static_src/src/styles.css      Tailwind sources and daisyUI themes
theme/static_src/package.json        the only npm manifest
tests/                              configuration and launcher regressions
scripts/                            dependency, browser and integration checks
```

There is one shared `base.html`. Keep application templates namespaced so adding
an app does not silently replace another app's template.

## Django commands and tests

With uv installed:

```bash
uv run python manage.py check
uv run python manage.py test
uv run python manage.py createsuperuser
```

Creating an administrator account is optional. Setup does not create one.
Without uv, replace `uv run python` with `.venv/bin/python` on macOS/Linux or
`.venv\Scripts\python.exe` on Windows; no activation is needed.

Frontend regressions use real compiler and watcher processes:

```bash
npm --prefix theme/static_src test
```

See [browser checks](browser-checks.md) and [verification](verification.md) for
the browser and clean-checkout suites used by CI. Run Django tests through
`manage.py test` so settings and request-test fixtures are initialized.

## Local files and dependencies

`.env`, `.venv`, `node_modules`, compiled CSS, `staticfiles/`, test artifacts and
SQLite databases are ignored by Git. Keep secrets local. Setup can be rerun; it
does not overwrite an existing `.env` or delete application records.

The `dev` dependency group contains browser-reload and browser-test tooling.
[Dependency maintenance](dependencies.md) explains locks, hashed pip exports
and deliberate updates. For low-level CSS commands see the
[frontend build reference](../theme/static_src/README.md).
