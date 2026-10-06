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

## Dependency maintenance

[Dependabot configuration](../.github/dependabot.yml) checks the root uv project,
`theme/static_src` npm project, and GitHub Actions monthly. Minor and patch
updates are grouped by ecosystem; major updates remain separate. Each ecosystem
has a limit of three open version-update PRs. Updates require review and passing
CI; this configuration does not enable automatic merging.

The `uv` ecosystem is supported by
[Dependabot](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
and maintains `uv.lock`, as described in
[Astral's integration guide](https://docs.astral.sh/uv/guides/integration/dependabot/).
The hashed `requirements.txt` and `requirements-dev.txt` files are generated
exports, not independent manifests to update with a second pip bot. After each
Python update, regenerate both exports using the commands in
[dependency maintenance](dependencies.md) and commit them on that update's PR.
Run `python scripts/check_dependencies.py --exports-only` before the full CI
gate. An export mismatch must block the update until corrected.

Frontend updates must commit `package.json` and `package-lock.json` together and
pass `npm ci`, the CSS build, and browser checks. Keep GitHub Actions pinned as
specified by the workflow; review action changes and rerun the full matrix.
Changes to the documented runtime ranges or framework major/LTS line need a
tracked requirement, matching documentation, and validation before merge.

## License

The starter preserves the existing choice of the [MIT license](../LICENSE) or
the [GPL-3.0 license](../LICENSE.GPL). Keep the relevant notices when adapting or
redistributing it and read the chosen license's terms.
