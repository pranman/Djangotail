# Configuration

Django reads `.env` from the repository root, regardless of the current working
directory. Exported environment variables take precedence. Bootstrap creates
the file from `.env.example` with a unique secret and debug enabled for local
development. An existing file is preserved, including any invalid values;
correct those values rather than expecting setup to overwrite them.

| Variable | Default without `.env` | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Required | Unique secret for this deployment; never commit it |
| `DJANGO_DEBUG` | `false` | Enable only for local development |
| `DJANGO_ALLOWED_HOSTS` | Empty; required outside debug | Comma-separated hostnames without schemes or ports |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Empty | Comma-separated HTTP(S) origins; optional port, no path/trailing slash |
| `DJANGO_SECURE_SSL_REDIRECT` | `not DEBUG` | Redirect HTTP requests to HTTPS |
| `DJANGO_SESSION_COOKIE_SECURE` | `not DEBUG` | Send session cookies only over HTTPS |
| `DJANGO_CSRF_COOKIE_SECURE` | `not DEBUG` | Send CSRF cookies only over HTTPS |
| `DJANGO_SECURE_HSTS_SECONDS` | `0` | HSTS duration; enable after verifying HTTPS |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | `false` | Apply HSTS to every subdomain |
| `DJANGO_SECURE_HSTS_PRELOAD` | `false` | Add the HSTS preload directive |
| `DJANGO_TRUST_X_FORWARDED_PROTO` | `false` | Trust the HTTPS indicator supplied by your reverse proxy |
| `NPM_BIN_PATH` | Discover on PATH | Optional npm executable, including `npm.cmd` on Windows |

Booleans accept true/false, 1/0, yes/no and on/off, ignoring case. Lists trim
entries but reject empty entries and embedded whitespace. HSTS duration must
be a nonnegative integer. Invalid values fail with an actionable configuration
error rather than silently selecting another value.

Only trust `X-Forwarded-Proto` when your proxy strips incoming client values and
sets its own, and Django is not directly reachable by clients. HSTS has lasting
browser effects: begin with a short duration and enable subdomain/preload
policies only when your entire deployment meets their requirements.

## Npm overrides

Normally no override is needed. If npm is installed in a nonstandard location,
use a literal path, quoted when necessary:

```dotenv
NPM_BIN_PATH="/path with spaces/to/npm"
```

On Windows an example is `NPM_BIN_PATH='C:\Program Files\nodejs\npm.cmd'`.
Relative paths, including `./npm`, resolve from the repository root. `~` expands
to the user's home directory. Bootstrap reads this one value before Python
dependencies are installed, so `${VARIABLE}` interpolation inside this value
is not supported; use a literal path or export an already resolved value.
Leave the variable unset when npm is on PATH. A blank override is an error.

## Storage and local defaults

SQLite uses `db.sqlite3` in the repository root. Built CSS lives under
`theme/static/css/dist/`; Django's app static finder discovers it. Production
collection writes to `staticfiles/`. These generated files are ignored by Git.
Changing the production database or storage backend is application-specific
work; this starter does not provision either service.

See [deployment](deployment.md) for the production sequence and
[troubleshooting](troubleshooting.md) for diagnostics.
