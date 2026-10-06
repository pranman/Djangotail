# Support

This repository is a Django application starter. Copy it using GitHub's template
button or clone a release, then use the setup command in the
[README](../README.md). It is not currently an installable project-generator
package on PyPI.

## Runtime and release scope

| Component | Supported range |
| --- | --- |
| Python | 3.12, 3.13, or 3.14, using a current patch release |
| Django | 5.2 LTS, pinned by `uv.lock` and the requirements exports |
| Node.js | 22.10 or newer within 22.x, or 24.x |
| npm | 10.x or 11.x |
| Platforms | Linux, macOS, and Windows; release gates require the documented CI matrix |
| Frontend | Tailwind CSS 4 and daisyUI 5, pinned by the npm lockfile |

The latest published release line and `main` are the maintenance targets.
Older minor release lines do not receive separate backports. A template copy is
your own application: review upstream changes and apply them deliberately to
your project, preserving its configuration and data.

## Getting help

Run `python bootstrap.py check` from the repository root for prerequisite and
configuration diagnostics. If it reports an unsupported runtime or missing
tool, install a supported version and reopen the terminal. Bootstrap does not
install system Python or Node.js for you.

For setup failures, keep the first failing command and error output. Rerunning
`python bootstrap.py` retries installation, preserves an existing `.env`, and
applies outstanding migrations. If `.venv` is damaged or incompatible, move it
aside and rerun setup; never remove `.env` or your database as a troubleshooting
shortcut.

Use a [bug report](https://github.com/pranman/django-tailwind-daisyui-template/issues/new?template=bug_report.yml)
for a reproducible problem. Include the release or commit, OS and shell, runtime
versions, working directory, commands, and expected versus actual behavior.
Attach only relevant, redacted logs. Do not upload `.env`, credentials, or a
database. Use a
[requirement issue](https://github.com/pranman/django-tailwind-daisyui-template/issues/new?template=requirement.yml)
for a proposed change with observable acceptance criteria.

Security problems belong in the [private reporting route](../SECURITY.md), not a
public bug report. Support is best effort; no response-time commitment or
individual deployment support is promised.

## License

The starter preserves the existing choice of the [MIT license](../LICENSE) or
the [GPL-3.0 license](../LICENSE.GPL). Keep the relevant notices when adapting or
redistributing it and read the chosen license's terms.
