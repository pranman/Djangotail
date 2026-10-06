# Changelog

This file records changes to the starter template. Applying a template update to
an existing application requires reviewing its code, configuration, and data
migrations; there is no automatic application upgrade command.

## Unreleased — 0.1.0 candidate

The first release remains gated by the
[release checklist](docs/releasing.md) and
[readiness issue #9](https://github.com/pranman/django-tailwind-daisyui-template/issues/9).
These notes do not mean that a tag has been published or that an unfinished
verification gate has passed.

### Setup and development

- A root `bootstrap.py` provides setup, `dev`, and read-only `check` commands.
  Setup manages `.venv`, uses frozen uv dependencies or hashed pip requirements,
  installs frontend dependencies, applies migrations, builds CSS, and runs
  Django checks. Existing configuration and database records are preserved.
- Local configuration uses explicit `DJANGO_*` settings and a generated unique
  secret. Invalid settings fail with actionable errors. npm discovery supports
  PATH and an optional `NPM_BIN_PATH`.
- The development launcher builds initial CSS, supervises Django and the CSS
  watcher, preserves Python autoreload, and stops their process trees on
  interruption or failure. It reports occupied development ports before launch.
- The demo includes accessible controls and deterministic light, dark, and
  cupcake themes. Browser refresh integrates with the development environment.

### Dependencies and assets

- Django moves from the legacy 4.2 baseline to the 5.2 LTS series. Python 3.12,
  3.13, and 3.14 are the supported interpreter versions.
- Tailwind CSS 4 and daisyUI 5 share one npm project in `theme/static_src` with a
  committed lockfile. Theme configuration and template scanning live in
  `theme/static_src/src/styles.css`.
- Frontend tooling requires Node.js 22.10+ within 22.x or Node.js 24.x, with npm
  10 or 11. Linux, macOS, and Windows are covered by the release verification
  matrix, which must pass on the release commit.
- Production configuration includes a static collection destination and
  explicit security settings. Building CSS and collecting static files remain
  separate steps from configuring a production web server.

### Repository and maintenance

- Repository branding identifies Django, Tailwind CSS, and daisyUI, with setup,
  customization, deployment, troubleshooting, and dependency documentation.
- Verification covers cold installation, both Python installers, safe reruns,
  generated styling, browser behavior, process cleanup, and production checks.
- Issue and PR templates capture requirements and verification evidence.
  Security reports use GitHub's private reporting route. Dependabot checks uv,
  npm, and GitHub Actions monthly; Python exports must stay synchronized.
- The existing MIT-or-GPL-3.0 license choice is preserved.

### Moving from the unversioned starter

- Back up local configuration and data before adapting an existing application.
  Review Django's upgrade requirements and your application's migrations; the
  bootstrap command is not a Django-version migration tool.
- The development environment is `.venv`. Manual activation is unnecessary for
  bootstrap commands. The old instructions to run npm in `theme/` are replaced
  by the root setup command or npm commands in `theme/static_src/`.
- An existing `.env` is preserved exactly. Add the required `DJANGO_*` settings
  from `.env.example`, including your own secret; bootstrap will not silently
  replace an old file that only contains npm configuration.
- Move custom Tailwind/daisyUI configuration from the legacy JavaScript config
  to the Tailwind 4 CSS entry point. Review custom components for daisyUI 5
  markup changes and rebuild the stylesheet.

### Limits

- The release is source for a starter application, not a PyPI project generator.
  Node.js/npm remain necessary to build or watch frontend assets.
- Development mode is local tooling. Production deployments still require a
  production application server, static-file serving, HTTPS, and deployment
  configuration appropriate to the application.
- Repository checks validate the supplied demo and supported matrix. They do
  not establish an accessibility certification or validate modifications made
  in downstream applications.
