# Security policy

Report suspected vulnerabilities through
[GitHub's private vulnerability reporting form](https://github.com/pranman/django-tailwind-daisyui-template/security/advisories/new).
Private vulnerability reporting is enabled for this repository. Do not put
vulnerability details, credentials, production data, or working exploits in a
public issue.

Include the affected release or commit, the relevant configuration with secrets
removed, reproduction steps, expected impact, and any suggested mitigation.
The report can be discussed privately before a fix and disclosure are ready.
There is no guaranteed response time or paid support agreement.

If the form is unavailable, open a public issue asking for a private reporting
route **without disclosing vulnerability details**.
[GitHub documents the private reporting process](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately).

## Supported versions

Security fixes target `main` and the latest published release line. Older minor
release lines do not have separate maintenance branches. Before the first
release, report against the current `main` commit. After a release is available,
include whether the problem also occurs on that release.

The template's Django dependency stays within the 5.2 LTS series. Updates to
Python, Django, Node.js, npm, and frontend dependencies still need to be applied
and verified in applications created from this template; copying the starter
does not provide automatic updates to those applications.

## Deployment responsibility

The generated `.env` is for local development. Production deployments need their
own secret, debug disabled, explicit allowed hosts, HTTPS configuration, and a
static-file serving arrangement. Follow the deployment guide and Django's
deployment checks for the environment you operate. The development server and
browser reload integration are not production services.

The repository's existing choice of the [MIT license](LICENSE) or
[GPL-3.0 license](LICENSE.GPL) remains unchanged. This policy does not change
either license or add a security warranty.
