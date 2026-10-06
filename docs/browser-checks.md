# Browser and accessibility checks

After installing the development dependencies and frontend packages, activate
`.venv` and install the browser once:

```sh
python -m playwright install chromium
python scripts/check_browser.py
```

On Linux CI, `python -m playwright install --with-deps chromium` also installs
Chromium's operating-system dependencies. Browser binaries are separate from the
Python dependency lock; Playwright selects its matching browser revision.

The default check creates a disposable project in a path containing spaces,
compiles CSS, starts Django and the CSS watcher, and runs Chromium. It modifies
only the disposable template and CSS source to prove automatic browser refresh,
then stops the processes and removes the copy. It uses the installed packages;
run `npm --prefix theme/static_src ci` first. No CDN or external image service is
needed by the demo or the accessibility audit.

Screenshots, a JSON report, process logs, and a Playwright trace are written to
`test-results/browser/`, which is ignored by Git. To also save a verified light
preview for documentation:

```sh
python scripts/check_browser.py --screenshot docs/images/preview.png
```

An existing disposable development instance can be checked with:

```sh
python scripts/check_browser.py --base-url http://127.0.0.1:8000 \
  --project-root "/path/to/disposable project" --check-reload \
  --artifacts test-results/browser
```

Wait for its first CSS build before running the checks. With `--check-reload`, the
script temporarily edits and restores that project's home template and CSS;
pass a disposable copy. Omitting `--check-reload` performs the browser checks
without source edits.

## Coverage

The suite checks CSS loading and real component dimensions; distinct computed
light, dark, and cupcake palettes; theme persistence; the local form preview;
keyboard theme selection, skip navigation, and visible focus; no horizontal
overflow at 320, 390, and 768 CSS pixels; a safe no-JavaScript fallback; and actual
template and compiled-CSS browser refresh. Local, locked axe-core audits every
advertised theme for WCAG 2 A/AA, WCAG 2.1 A/AA, and best-practice violations.
The check fails on any reported violation, including color contrast.

The stock dark theme's primary foreground is adjusted to white so small text on
its primary background meets AA contrast. The hero uses a colored underline,
keeping its text legible in cupcake as well as light and dark.

## Repeatable visual review

- Tab from the address bar: reveal “Skip to content,” follow it, and check the
  visible focus indicator on links, the theme selector, input, and buttons.
- Select each theme with the keyboard. Confirm its colors change and persist
  after refresh. Enter a name, update the preview, then reset it.
- Check all themes at desktop width and at 320 CSS pixels. Text and controls
  should wrap without horizontal scrolling. Also review browser zoom at 200%.
- Disable JavaScript: documentation links remain usable, the explanatory message
  appears, and the interactive controls are disabled rather than submitting data.
- With development running, change template text and a CSS rule. Confirm the
  page refreshes after the watcher rebuilds. Undo the edits.

The initial Chromium review on 6 October 2026 passed all automated checks with
zero axe findings, and desktop/theme/mobile screenshots were inspected. These
smoke checks do not replace broader assistive-technology testing for a product
built from this starter.

## Reload behavior

`django-browser-reload` is enabled only with `DJANGO_DEBUG=true`. It refreshes
HTML after Python, template, and static-file changes; Tailwind first rebuilds CSS
from template or stylesheet edits. Keep Django's normal autoreloader enabled
(do not pass `runserver --noreload`). Only the most recently loaded browser tab
refreshes. Development refresh needs the dev dependencies, JavaScript, and a
browser with SharedWorker and EventSource support.

Production omits the reload app, middleware, route, and injected script.
`python -m unittest tests.test_browser_reload` verifies both configurations in
fresh Django processes.
