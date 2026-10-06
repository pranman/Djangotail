# Dependency maintenance

The starter supports Python 3.12–3.14; `.python-version` selects Python 3.13
for uv by default. Use a current patch release. Django stays on the supported
5.2 LTS series. Frontend requirements are declared in
`theme/static_src/package.json`.

`pyproject.toml` declares Python dependencies and `uv.lock` resolves their exact
versions. This repository is an application template, not an installable Python
package. Development dependencies are in the `dev` dependency group.

After deliberately changing dependencies, run:

```bash
uv lock
uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file requirements.txt
uv export --frozen --no-emit-project --format requirements-txt --output-file requirements-dev.txt
```

Commit the manifest, lock and both exports together. Use `uv lock --upgrade`
for a deliberate update within the declared version ranges, then regenerate
the exports and run the checks. Do not edit generated requirements by hand.

`uv sync --frozen` installs the development environment. The equivalent pip
installation, in an activated virtual environment, is:

```bash
python -m pip install --require-hashes -r requirements-dev.txt
```

For production dependencies use `uv sync --frozen --no-dev`, or install the
hashed `requirements.txt` export. Production settings must not enable the
development-only browser reload integration.
