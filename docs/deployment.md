# Prepare a deployment

This repository supplies Django WSGI/ASGI entry points and an asset build. Your
hosting setup must supply a production application server, HTTPS, static-file
serving, persistent storage, backups and monitoring. Do not deploy `runserver`
or the development launcher as an application server.

## Configuration

Set a new high-entropy `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false` and the real
`DJANGO_ALLOWED_HOSTS`. Supply trusted CSRF origins if your deployment needs
them. Use environment/secrets management supplied by the host; do not copy the
local development `.env` into production.

Read the [configuration reference](configuration.md) before enabling proxy
trust or HSTS. Secure redirect and session/CSRF cookies default on outside
debug. HSTS policy is deliberately explicit, so default production checks
still report warnings until you configure it for your HTTPS deployment.

## Build, migrate and collect

Install runtime dependencies into a deployment virtual environment:

```bash
uv sync --frozen --no-dev
```

Alternatively, create/activate a deployment environment and run:

```bash
python -m pip install --require-hashes -r requirements.txt
```

The following commands assume `python` is that deployment environment's
interpreter and production environment variables are set. With uv, use
`uv run --no-dev python` in place of `python` to avoid adding development tools.

```bash
npm --prefix theme/static_src ci
npm --prefix theme/static_src run build
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy --fail-level WARNING
```

Build CSS **before** static collection. The collected stylesheet must match
the compiled asset. Investigate deployment warnings against your actual HTTPS
and proxy topology; do not silence them wholesale to obtain a green check.
Apply database migrations under your deployment's backup and rollout process.

Node/npm are needed in the build stage. They are not required by the running
Django process once assets are built and collected. Development browser reload
and Playwright are not part of the runtime requirements.

## Serve the application

- WSGI entry point: `Project.wsgi:application`
- ASGI entry point: `Project.asgi:application`
- Settings module: `Project.settings`
- Static URL: `/static/`; collected directory: `staticfiles/`

Select and install the production server appropriate to your host; none is
bundled or launched by the bootstrap script. Configure the web server/storage
service to serve the collected directory. Django does not serve production
static files automatically just because `collectstatic` succeeded.

SQLite remains the default database. Ensure its location is persistent and
appropriate for your workload, or configure and test a different backend.

## Release verification

Test the deployment with debug disabled, verify the stylesheet and all required
routes, and check that the browser-reload script/endpoint are absent. Confirm
the HTTPS/cookie/proxy behavior at the public boundary. CI checks a representative
configuration, not every possible hosting arrangement. Use the
[release checklist](releasing.md) and Django's
[deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).
