"""Check real styling, accessibility, keyboard use and development browser reload."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def stop_process(process):
    if os.name == "nt":
        if process.poll() is None:
            subprocess.run(["taskkill", "/pid", str(process.pid), "/T", "/F"],
                           check=True, capture_output=True, timeout=15)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    process.wait(timeout=15)


@contextmanager
def isolated_server(artifacts):
    """Edit only a disposable checkout; reuse the already installed npm packages."""
    with tempfile.TemporaryDirectory(prefix="starter browser ") as temporary:
        project = Path(temporary) / "project with spaces"
        shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns(
            ".git", ".venv", "venv", "node_modules", ".env", "*.sqlite3",
            "__pycache__", "staticfiles", "test-results", "playwright-report"))
        modules = ROOT / "theme/static_src/node_modules"
        if not modules.is_dir():
            raise RuntimeError("Run npm --prefix theme/static_src ci first.")
        destination = project / "theme/static_src/node_modules"
        if os.name == "nt":
            # A junction does not need Windows developer-mode symlink privileges.
            subprocess.run(["cmd", "/c", "mklink", "/J", str(destination), str(modules)],
                           check=True, capture_output=True)
        else:
            destination.symlink_to(modules, target_is_directory=True)
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("DJANGO_") and key != "NPM_BIN_PATH"}
        env.update(DJANGO_SECRET_KEY=secrets.token_urlsafe(64), DJANGO_DEBUG="true",
                   DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1", PYTHON_DOTENV_DISABLED="1")
        subprocess.run([sys.executable, "manage.py", "tailwind", "build"],
                       cwd=project, env=env, check=True)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        processes = []
        try:
            for name, command in (
                ("watcher", ["tailwind", "start"]),
                ("server", ["runserver", f"127.0.0.1:{port}"]),
            ):
                with (artifacts / f"{name}.log").open("w", encoding="utf-8") as log:
                    processes.append(subprocess.Popen(
                        [sys.executable, "manage.py", *command], cwd=project, env=env,
                        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                        start_new_session=os.name != "nt",
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                    ))
                if name == "watcher":
                    for _ in range(150):
                        if "Done in" in (artifacts / "watcher.log").read_text(encoding="utf-8"):
                            break
                        if processes[-1].poll() is not None:
                            raise RuntimeError("CSS watcher exited before its first build")
                        time.sleep(0.1)
                    else:
                        raise RuntimeError("CSS watcher did not finish its initial build")
            url = f"http://127.0.0.1:{port}"
            for _ in range(150):
                if any(process.poll() is not None for process in processes):
                    raise RuntimeError(f"Development process exited; inspect {artifacts} logs.")
                try:
                    with urlopen(url, timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Development server did not become ready.")
            yield url, project
        finally:
            for process in reversed(processes):
                stop_process(process)


def check_reload(page, project):
    template = project / "MainApp/templates/MainApp/home.html"
    stylesheet = project / "theme/static_src/src/styles.css"
    original_template = template.read_bytes()
    original_stylesheet = stylesheet.read_bytes()
    marker = "browser-reload-" + secrets.token_hex(6)
    try:
        page.evaluate("window.__reloadProbe = 'template'")
        template.write_text(original_template.decode().replace(
            "{% endblock %}", f'<p id="{marker}">Template reload verified.</p>\n{{% endblock %}}'),
            encoding="utf-8")
        expect(page.locator(f"#{marker}")).to_have_text("Template reload verified.", timeout=20_000)
        assert page.evaluate("window.__reloadProbe === undefined"), "Template edit did not reload the page"
        # A source-CSS edit must reach the compiler, served CSS and then browser.
        page.evaluate("window.__reloadProbe = 'css'")
        stylesheet.write_bytes(original_stylesheet + b"\n@layer utilities { #preview-heading { outline: 7px solid rgb(1, 2, 3); } }\n")
        page.wait_for_function("""() => {
            const style = getComputedStyle(document.getElementById('preview-heading'));
            return style.outlineWidth === '7px' && style.outlineColor === 'rgb(1, 2, 3)'
                && window.__reloadProbe === undefined;
        }""", timeout=20_000)
    finally:
        template.write_bytes(original_template)
        stylesheet.write_bytes(original_stylesheet)


def check_browser(base_url, project, artifacts, reload):
    report = {"themes": {}, "accessibility": {}, "checks": []}
    errors = []
    external_requests = []
    origin = urlsplit(base_url).netloc
    axe = ROOT / "theme/static_src/node_modules/axe-core/axe.min.js"
    if not axe.is_file():
        raise RuntimeError("Run npm --prefix theme/static_src ci to install the locked axe-core check.")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1080}, reduced_motion="reduce")
        context.tracing.start(screenshots=True, snapshots=True)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: external_requests.append(request.url)
                if urlsplit(request.url).scheme in ("http", "https")
                and urlsplit(request.url).netloc != origin else None)
        try:
            with page.expect_response(lambda response: "/static/css/dist/styles.css" in response.url) as stylesheet:
                response = page.goto(base_url, wait_until="load")
            assert response.status == 200
            assert stylesheet.value.status == 200, "Compiled stylesheet did not load"
            expect(page).to_have_title("Django + Tailwind CSS + daisyUI Starter Template")
            assert page.locator(".card").first.evaluate("el => getComputedStyle(el).display") == "flex"
            assert page.get_by_role("button", name="Update preview").evaluate(
                "el => parseFloat(getComputedStyle(el).height)") >= 36
            report["checks"].append("compiled stylesheet and component dimensions")

            page.keyboard.press("Tab")
            skip = page.get_by_role("link", name="Skip to content")
            expect(skip).to_be_focused()
            expect(skip).to_be_visible()
            page.keyboard.press("Enter")
            expect(page.locator("main")).to_be_focused()
            selector = page.get_by_label("Color theme")
            selector.select_option("light")
            selector.focus()
            page.keyboard.press("d")
            page.keyboard.press("Enter")
            expect(selector).to_have_value("dark")
            focus = selector.evaluate("el => { const s = getComputedStyle(el); return [s.outlineStyle, s.outlineWidth]; }")
            assert focus[0] != "none" and float(focus[1].removesuffix("px")) >= 2, focus
            report["checks"].append("keyboard theme selection, skip link and visible focus")

            for theme in ("light", "dark", "cupcake"):
                selector.select_option(theme)
                expect(page.locator("html")).to_have_attribute("data-theme", theme)
                report["themes"][theme] = page.evaluate("""() => ({
                    background: getComputedStyle(document.body).backgroundColor,
                    foreground: getComputedStyle(document.body).color,
                    primary: getComputedStyle(document.querySelector('button.btn-primary')).backgroundColor,
                })""")
                page.add_script_tag(path=str(axe))
                findings = page.evaluate("""async () => (await axe.run(document, {
                    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'] }
                })).violations""")
                report["accessibility"][theme] = findings
                page.screenshot(path=str(artifacts / f"{theme}-desktop.png"), full_page=True)
                assert not findings, json.dumps({"theme": theme, "violations": findings}, indent=2)
            assert len({values["background"] for values in report["themes"].values()}) == 3
            assert len({values["primary"] for values in report["themes"].values()}) == 3
            report["checks"].append("three distinct computed palettes and zero axe findings")
            page.reload(wait_until="load")
            expect(selector).to_have_value("cupcake")
            expect(page.locator("html")).to_have_attribute("data-theme", "cupcake")
            page.get_by_label("Display name").fill("Ada <script>")
            page.get_by_role("button", name="Update preview").click()
            expect(page.locator("#preview-heading")).to_have_text("Hello, Ada <script>.")
            assert urlsplit(page.url).query == "", "Local preview submitted data to the server"
            page.get_by_role("button", name="Reset", exact=True).click()
            expect(page.locator("#preview-heading")).to_have_text("Hello, maker.")
            expect(page.get_by_label("Display name")).to_have_value("")
            report["checks"].append("theme persistence and safe local form preview")

            for width in (320, 390, 768):
                page.set_viewport_size({"width": width, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), f"Horizontal overflow at {width}px"
                expect(selector).to_be_visible()
                expect(page.get_by_role("button", name="Update preview")).to_be_visible()
                page.screenshot(path=str(artifacts / f"mobile-{width}.png"), full_page=True)
            report["checks"].append("responsive layouts at 320, 390 and 768 CSS pixels")
            if reload:
                check_reload(page, project)
                report["checks"].append("actual template and compiled-CSS browser reload")
            assert not errors, errors
            assert not external_requests, external_requests
            report["checks"].append("no page errors or external image/script requests")
            no_js = browser.new_context(java_script_enabled=False)
            fallback = no_js.new_page()
            fallback.goto(base_url, wait_until="load")
            expect(fallback.get_by_label("Color theme")).to_be_disabled()
            expect(fallback.get_by_role("button", name="Update preview")).to_be_disabled()
            expect(fallback.locator("noscript")).to_be_visible()
            no_js.close()
            report["checks"].append("usable no-JavaScript fallback without form submission")
        except Exception:
            page.screenshot(path=str(artifacts / "failure.png"), full_page=True)
            raise
        finally:
            report["page_errors"] = errors
            report["external_requests"] = external_requests
            (artifacts / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            context.tracing.stop(path=str(artifacts / "trace.zip"))
            browser.close()
    print("Browser checks passed: " + "; ".join(report["checks"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="Use an already running development server instead of a disposable copy")
    parser.add_argument("--project-root", type=Path, help="Disposable project served at --base-url, needed for --check-reload")
    parser.add_argument("--check-reload", action="store_true", help="Edit and restore source files to test real browser reload")
    parser.add_argument("--artifacts", type=Path, default=ROOT / "test-results/browser")
    parser.add_argument("--screenshot", type=Path, help="Also save the verified light-theme desktop screenshot here")
    args = parser.parse_args()
    if args.base_url and args.check_reload and not args.project_root:
        parser.error("--check-reload with --base-url requires --project-root pointing to a disposable checkout")
    artifacts = args.artifacts.resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    if args.base_url:
        check_browser(args.base_url, args.project_root, artifacts, args.check_reload)
    else:
        with isolated_server(artifacts) as (url, project):
            check_browser(url, project, artifacts, True)

    if args.screenshot:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(artifacts / "light-desktop.png", args.screenshot)


if __name__ == "__main__":
    main()
