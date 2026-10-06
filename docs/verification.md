# Verification and release gates

The [Verify starter workflow](https://github.com/pranman/django-tailwind-daisyui-template/actions/workflows/verify.yml) exercises the public `bootstrap.py` commands in disposable copies of tracked source. Each copy starts without `.venv`, `.env`, a database, frontend dependencies, collected static files, or compiled CSS. The copy has spaces in its path, and commands run from a different working directory.

## Local reproduction

Use a supported Python (3.12–3.14), Node.js (22.10+ within 22, or 24), and npm (10 or 11). Install uv to exercise the uv route. These commands do not change your working project's environment, configuration, database, or stylesheet:

Run checkout verification from a Git checkout with Git on PATH: the verifier uses
`git ls-files` to copy tracked source. The public bootstrap commands also work
from an extracted source archive and do not require Git.

```bash
python scripts/verify_starter.py --installer uv --cold
python scripts/verify_starter.py --installer pip --cold
python scripts/verify_starter.py --installer pip --cold --browser
```

`--cold` puts uv, pip, and npm caches in new empty temporary directories. It requires access to the package registries. The browser option installs the locked Playwright Chromium build and, on Linux, its system dependencies; Playwright may use sudo to install those system packages. The browser suite runs against the disposable application's actual development launcher.

For a narrower check after normal project setup, use the managed environment's Python:

```bash
python manage.py test --verbosity 2
python scripts/check_dependencies.py --exports-only
npm --prefix theme/static_src test
```

The lock/export check additionally requires uv on PATH. The browser suite also has its own isolated runner: `python scripts/check_browser.py`. See that command's `--help` before pointing it at another server; `--check-reload` temporarily edits the supplied project's template and stylesheet, so use a disposable copy.

## Hosted matrix

| Lane | Runner | Python | Node.js | Installer | Extra coverage |
| --- | --- | --- | --- | --- | --- |
| `linux-py312-node22-uv` | Ubuntu 24.04 | 3.12 | 22 | uv | Empty caches, lock/export consistency |
| `linux-py314-node24-pip-browser` | Ubuntu 24.04 | 3.14 | 24 | pip | Empty caches, Chromium rendering, themes, accessibility, reload |
| `macos-py313-node24-uv` | macOS 15 | 3.13 | 24 | uv | macOS launcher and process trees |
| `windows-py313-node22-pip` | Windows Server 2025 | 3.13 | 22 | pip | Windows launcher and Job Object cleanup |

All lanes run the same setup, safe-rerun, focused regression, real launcher, stylesheet-response, and production checks. This matrix covers both installers, every advertised Python/Node version family, and all three operating systems without asserting that every possible combination is separately tested. Actual Chromium rendering runs on Linux; this is not a Safari, Firefox, or every-platform browser compatibility claim.

Actions are pinned to immutable commits, workflow access is limited to read-only repository contents, checkout credentials are not retained, and dependency caches are not restored by workflow actions. The uv executable is pinned to 0.12.6; Python/Node lanes select the latest available patch within each declared version family. Runtime installers may reuse hosted runner tool installations. The cold lanes still have no previously installed project dependencies or package-cache contents.

## Required evidence

Before release, require the aggregate **Starter verification** check to succeed on the exact chosen commit. Its four **Starter (...)** jobs must all succeed; a failure, cancellation, or skipped matrix does not pass the aggregate gate. A tag push reruns the matrix on that tag's commit. Local success alone does not establish Windows or Linux success.

The checks prove that:

- The public root setup command installs locked dependencies, creates a unique local secret, applies migrations, and compiles CSS.
- A second setup preserves every byte of the existing configuration and a sentinel database record.
- The real development launcher serves Django, rebuilds changed CSS, rejects occupied ports, and shuts down after interruption or a watcher failure. Focused process-tree tests also prove that failing server/watcher parents do not leave their sibling or grandchildren running.
- The homepage serves the real compiled stylesheet once. Chromium checks representative utility/component computed styles, light/dark/cupcake themes, keyboard/mobile behavior, accessibility, and real CSS/template browser reload.
- A production CSS build is collected without changing its bytes in a separate environment installed from hashed `requirements.txt`, with Playwright and browser-reload absent; an explicit representative HTTPS configuration passes `check --deploy --fail-level WARNING`; WSGI starts with Node/npm absent from PATH. Deployment infrastructure and database suitability still require the application's own deployment decisions.

## Development readiness

Before the lifecycle check edits source CSS, the verifier requires both an HTTP
200 response from Django and successful completion of the CSS watcher's initial
build. An HTTP response alone is insufficient: Django can begin serving while
Tailwind is still reading its initial input or installing filesystem watches.
The production build performed before the launcher starts its children is also
not evidence that the separate watcher is ready.

The verifier enables `DEBUG=tailwindcss` only for its development subprocesses.
For the pinned CLI, it requires a successful `Done in` message and the specific
`[@tailwindcss/cli] (initial build)` completion diagnostic after
`Starting CSS watcher...`. This distinguishes the watcher's completed startup
from the preceding production build and from incremental/no-op callbacks.
ANSI colors and Windows line endings are accepted. The application and normal
bootstrap commands do not need this diagnostic environment variable.

`development-readiness.log` records the two readiness conditions or names the
condition that timed out. A managed child or launcher exit is reported with its
exit code when available; inspect `development.log` for the underlying error.
A startup timeout does not cause the verifier to edit CSS early or skip checks.
If a Tailwind CLI update changes its diagnostics, update the readiness parser
and regression fixtures together; retain the requirement for actual watcher
startup completion.

After startup, the suite still performs a real CSS edit and restoration and
waits for both compiled results. It then drains pending browser-reload events
before inspecting rendered styles. `browser-readiness.log` describes that
separate reload-stream check. The later browser test still makes and verifies
new template and CSS edits.

Focused regressions use a real HTTP process with a watcher completion gate to
exercise HTTP-first startup, delayed initial compilation, no-op callbacks,
early exit, and timeout without using a fixed startup delay. These tests support
the hosted matrix; local results do not replace successful checks on every
platform lane for the release commit.

## Diagnostics

Each run writes named step logs under `verification-artifacts/`. GitHub retains these as `starter-<lane>` artifacts for seven days, including browser screenshots and traces when produced. On failure, start with the log whose step name appears in the error, then the development log or browser artifacts. `browser-readiness.log` records the startup reload events drained before Chromium begins inspecting the page; the suite still tests real later template/CSS reloads. Reproduce the failing lane's Python, Node, installer, and command locally.

Only the diagnostics directory is uploaded. The disposable checkout, `.env`, SQLite database, dependency directories, and credentials are not uploaded. Generated secret values are removed from logs, including failure logs. Avoid adding environment dumps or copying the whole temporary project into artifacts when extending these checks.
