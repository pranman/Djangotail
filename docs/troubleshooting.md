# Troubleshooting

Start with `python bootstrap.py check`. It checks supported runtimes and, when
the managed environment and local configuration exist, validates Django. It
does not install packages or change project files, and it hides configuration
values. Use the same supported Python interpreter you used for setup.

## Python, Node or npm is missing

Install a supported version from the official Python/Node distribution, reopen
the terminal and rerun setup. Node must be 22.10+ in the 22 series or 24 LTS;
npm must be 10 or 11. Bootstrap does not install system runtimes. On Windows,
`py -3.13 bootstrap.py` selects Python 3.13; macOS/Linux commonly use `python3`.

uv is optional. Force a path with `--installer uv` or `--installer pip`.
An existing compatible uv-created environment can be reused with pip; setup
adds pip to that environment if necessary.

## Npm is installed but cannot be found

First check the terminal's PATH. If needed, set a literal `NPM_BIN_PATH` in
`.env`; see [configuration](configuration.md#npm-overrides) for Windows,
relative paths and spaces. Remove a blank override to use normal discovery.
Do not copy a machine-specific path from another computer.

## An install was interrupted or failed

Read the first failing command, resolve the network/runtime/permissions problem,
then rerun `python bootstrap.py`. The script stops on failures and preserves
existing configuration and data. `npm ci` recreates frontend dependencies from
the committed lock; it does not require manual edits to node_modules.

If `.venv` is damaged or was moved from another machine, move it aside and rerun
setup. Bootstrap deliberately refuses to delete an incompatible environment.
Do not delete `.env` or `db.sqlite3` to repair a package installation.

## Secret or configuration errors

Bootstrap only generates `.env` when it is absent. An existing file with a blank
secret or invalid boolean/list remains unchanged, so correct the reported value
using `.env.example` and the [configuration reference](configuration.md).
Exported environment variables override `.env`; check the calling shell if a
file edit appears to have no effect. Restart the development command after
configuration changes. Never post `.env` or secret values in a bug report.

Bootstrap diagnostics hide captured command output. To see Django's specific
configuration error locally, run `uv run python manage.py check`. Without uv,
use `.venv/bin/python manage.py check` on macOS/Linux or
`.venv\Scripts\python.exe manage.py check` on Windows. Review and redact any
local details before including terminal output in a public report.

## Port 8000 is occupied

Stop the previous development command with Ctrl+C, or choose another port:

```bash
python bootstrap.py dev --port 8001
```

The launcher refuses an occupied port and cleans up its managed processes on
exit. The address printed by Django should match the URL you open.

## CSS is missing or stale

Run setup and keep `python bootstrap.py dev` running while editing. There is one
npm package, in `theme/static_src`; installing from `theme/` is obsolete.

Check that `/static/css/dist/styles.css` loads successfully and that new source
directories are included by `@source`. Use complete class names in templates.
If the browser stays stale, check terminal build errors first, then reload the
page. Browser refresh is enabled only when debug mode is on. The
[frontend build reference](../theme/static_src/README.md) has low-level commands.

If a theme appears in the selector but has no effect, update all three parts:
the CSS plugin configuration, selector options and JavaScript allowlist. Follow
[customization](customization.md) rather than restoring a Tailwind 3 config file.

## A browser test cannot launch Chromium

Browser tests require the locked development dependencies and a separate browser
download: `uv run python -m playwright install chromium`. Linux machines may
need Playwright's documented system dependencies (`install --with-deps chromium`
in a suitable build environment). Normal application setup does not need a
browser download. See [browser checks](browser-checks.md).

## Deployment checks fail

Use the runtime environment and actual production variables. Build CSS before
running `collectstatic`. Configure the required secret, hosts and HTTPS policy;
the development `.env` intentionally does not satisfy deployment checks. See
[deployment](deployment.md), and do not silence warnings without understanding
the corresponding responsibility at your host/proxy boundary.
