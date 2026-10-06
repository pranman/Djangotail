"""Configuration regressions checked in isolated, freshly copied projects."""

import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured

from Project.configuration import csrf_origins, env_bool, env_list, env_nonnegative_int


ROOT = Path(__file__).resolve().parent.parent


class EnvironmentParserTests(unittest.TestCase):
    def test_explicit_false_values_do_not_enable_debug(self):
        for value in ("false", "FALSE", "0", "no", " off "):
            with self.subTest(value=value), patch.dict(os.environ, {"FLAG": value}):
                self.assertFalse(env_bool("FLAG", default=True))

    def test_invalid_boolean_fails_without_echoing_its_value(self):
        with patch.dict(os.environ, {"FLAG": "mistyped-value"}):
            with self.assertRaisesRegex(ImproperlyConfigured, "FLAG must be true or false") as error:
                env_bool("FLAG")
            self.assertNotIn("mistyped-value", str(error.exception))

    def test_lists_trim_entries_but_reject_empty_entries_and_embedded_whitespace(self):
        with patch.dict(os.environ, {"HOSTS": " localhost, 127.0.0.1, [::1] "}):
            self.assertEqual(env_list("HOSTS"), ["localhost", "127.0.0.1", "[::1]"])
        for value in ("localhost,", "localhost,,example.com", "localhost example.com"):
            with self.subTest(value=value), patch.dict(os.environ, {"HOSTS": value}):
                with self.assertRaisesRegex(ImproperlyConfigured, "HOSTS must be a comma-separated list"):
                    env_list("HOSTS")

    def test_csrf_origins_require_scheme_and_reject_paths_or_credentials(self):
        for value in ("example.com", "https://example.com/", "https://user@example.com", "https://example.com:bad"):
            with self.subTest(value=value), patch.dict(os.environ, {"DJANGO_CSRF_TRUSTED_ORIGINS": value}):
                with self.assertRaisesRegex(ImproperlyConfigured, "DJANGO_CSRF_TRUSTED_ORIGINS"):
                    csrf_origins()
        with patch.dict(os.environ, {"DJANGO_CSRF_TRUSTED_ORIGINS": "https://*.example.com,http://localhost:8000"}):
            self.assertEqual(csrf_origins(), ["https://*.example.com", "http://localhost:8000"])

    def test_hsts_duration_rejects_negative_or_noninteger_values(self):
        for value in ("-1", "1.5", "tomorrow", ""):
            with self.subTest(value=value), patch.dict(os.environ, {"DURATION": value}):
                with self.assertRaisesRegex(ImproperlyConfigured, "DURATION must be a nonnegative integer"):
                    env_nonnegative_int("DURATION")


class ProjectConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="django-config-")
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name).resolve() / "project with spaces"
        self.project.mkdir()
        for directory in ("Project", "MainApp"):
            shutil.copytree(ROOT / directory, self.project / directory, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        theme = self.project / "theme"
        theme.mkdir()
        for filename in ("__init__.py", "apps.py"):
            shutil.copyfile(ROOT / "theme" / filename, theme / filename)
        shutil.copytree(ROOT / "theme" / "templates", theme / "templates")
        self.css = theme / "static" / "css" / "dist" / "styles.css"
        self.css.parent.mkdir(parents=True)
        self.css.write_text(".configuration-fixture { display: block; }\n", encoding="utf-8")
        shutil.copyfile(ROOT / "manage.py", self.project / "manage.py")
        self.unrelated = Path(self.temporary.name) / "unrelated cwd"
        self.unrelated.mkdir()
        self.secret = secrets.token_urlsafe(64)
        self.environment = {
            key: value for key, value in os.environ.items()
            if not key.startswith("DJANGO_") and key not in {"NPM_BIN_PATH", "PYTHON_DOTENV_DISABLED"}
        }
        self.environment.update({
            "PYTHONPATH": str(self.project),
            "DJANGO_SETTINGS_MODULE": "Project.settings",
            "DJANGO_SECRET_KEY": self.secret,
            "DJANGO_DEBUG": "true",
            "DJANGO_ALLOWED_HOSTS": "localhost,testserver",
        })

    def run_python(self, *args, **overrides):
        environment = self.environment.copy()
        for key, value in overrides.items():
            if value is None:
                environment.pop(key, None)
            else:
                environment[key] = value
        return subprocess.run(
            [sys.executable, *args], cwd=self.unrelated, env=environment,
            capture_output=True, text=True, timeout=30,
        )

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def inspect_settings(self, **overrides):
        result = self.run_python("-c", """
import json
from django.conf import settings
print(json.dumps({
    'debug': settings.DEBUG,
    'hosts': settings.ALLOWED_HOSTS,
    'csrf': settings.CSRF_TRUSTED_ORIGINS,
    'database': str(settings.DATABASES['default']['NAME']),
    'static_root': str(settings.STATIC_ROOT),
    'npm': settings.NPM_BIN_PATH,
    'redirect': settings.SECURE_SSL_REDIRECT,
    'session_secure': settings.SESSION_COOKIE_SECURE,
    'csrf_secure': settings.CSRF_COOKIE_SECURE,
    'proxy': settings.SECURE_PROXY_SSL_HEADER,
}))
""", **overrides)
        self.assert_success(result)
        return json.loads(result.stdout)

    def test_project_root_dotenv_and_real_environment_precedence(self):
        dotenv_secret = secrets.token_urlsafe(64)
        (self.project / ".env").write_text(
            f"DJANGO_SECRET_KEY={dotenv_secret}\nDJANGO_DEBUG=false\n"
            "DJANGO_ALLOWED_HOSTS=dotenv.example.com\n", encoding="utf-8",
        )
        (self.unrelated / ".env").write_text("DJANGO_DEBUG=invalid\n", encoding="utf-8")
        configured = self.inspect_settings(DJANGO_ALLOWED_HOSTS=None)
        self.assertTrue(configured["debug"])
        self.assertEqual(configured["hosts"], ["dotenv.example.com"])
        result = self.run_python("-c", """
import os
from django.conf import settings
assert settings.SECRET_KEY == os.environ['EXPECTED_SECRET']
""", EXPECTED_SECRET=self.secret)
        self.assert_success(result)

    def test_local_paths_do_not_depend_on_current_directory(self):
        configured = self.inspect_settings()
        self.assertEqual(Path(configured["database"]), self.project / "db.sqlite3")
        self.assertEqual(Path(configured["static_root"]), self.project / "staticfiles")

    def test_missing_or_blank_secret_fails_clearly_without_disclosing_a_value(self):
        for value in (None, "", "  "):
            with self.subTest(value=value):
                result = self.run_python(str(self.project / "manage.py"), "check", DJANGO_SECRET_KEY=value)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("DJANGO_SECRET_KEY is required", result.stderr)
                self.assertNotIn(self.secret, result.stderr)

    def test_debug_defaults_to_false_and_requires_production_hosts(self):
        configured = self.inspect_settings(DJANGO_DEBUG=None)
        self.assertFalse(configured["debug"])
        result = self.run_python(str(self.project / "manage.py"), "check", DJANGO_DEBUG="false", DJANGO_ALLOWED_HOSTS=None)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_ALLOWED_HOSTS must contain", result.stderr)

    def test_local_settings_disable_https_redirect_and_secure_cookies(self):
        configured = self.inspect_settings()
        self.assertFalse(configured["redirect"])
        self.assertFalse(configured["session_secure"])
        self.assertFalse(configured["csrf_secure"])
        self.assertIsNone(configured["proxy"])
        result = self.run_python(str(self.project / "manage.py"), "check")
        self.assert_success(result)

    def test_production_settings_and_explicit_proxy_trust(self):
        configured = self.inspect_settings(
            DJANGO_DEBUG="false", DJANGO_ALLOWED_HOSTS="app.example.com",
            DJANGO_CSRF_TRUSTED_ORIGINS="https://app.example.com",
            DJANGO_TRUST_X_FORWARDED_PROTO="true",
        )
        self.assertFalse(configured["debug"])
        self.assertTrue(configured["redirect"])
        self.assertTrue(configured["session_secure"])
        self.assertTrue(configured["csrf_secure"])
        self.assertEqual(configured["csrf"], ["https://app.example.com"])
        self.assertEqual(configured["proxy"], ["HTTP_X_FORWARDED_PROTO", "https"])

    def test_representative_https_deployment_passes_all_deployment_checks(self):
        result = self.run_python(
            str(self.project / "manage.py"), "check", "--deploy", "--fail-level", "WARNING",
            DJANGO_DEBUG="false", DJANGO_ALLOWED_HOSTS="app.example.com",
            DJANGO_SECURE_HSTS_SECONDS="300", DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS="true",
            DJANGO_SECURE_HSTS_PRELOAD="true",
        )
        self.assert_success(result)
        self.assertIn("no issues", result.stdout)

    def test_static_collection_and_wsgi_startup_work_without_node(self):
        result = self.run_python(str(self.project / "manage.py"), "collectstatic", "--noinput", PATH="")
        self.assert_success(result)
        self.assertEqual((self.project / "staticfiles" / "css" / "dist" / "styles.css").read_text(), self.css.read_text())
        result = self.run_python("-c", "from Project.wsgi import application; assert callable(application)", PATH="")
        self.assert_success(result)
        self.assertEqual(self.inspect_settings(PATH="")["npm"], "npm.cmd" if os.name == "nt" else "npm")

    def make_fake_npm(self):
        directory = self.project / "tools with spaces"
        directory.mkdir()
        executable = directory / ("npm.cmd" if os.name == "nt" else "npm")
        executable.write_text("@echo npm-space-path-ok\n" if os.name == "nt" else "#!/bin/sh\necho npm-space-path-ok\n", encoding="utf-8")
        executable.chmod(0o755)
        return executable

    def test_npm_is_discovered_on_path(self):
        executable = self.make_fake_npm()
        configured = self.inspect_settings(PATH=str(executable.parent))
        self.assertEqual(Path(configured["npm"]), executable)

    def test_explicit_npm_path_with_spaces_executes_through_django_tailwind(self):
        executable = self.make_fake_npm()
        (self.project / ".env").write_text(f'NPM_BIN_PATH="{executable.as_posix()}"\n', encoding="utf-8")
        result = self.run_python("-c", "from tailwind.npm import NPM; NPM().command('--version')")
        self.assert_success(result)
        self.assertIn("npm-space-path-ok", result.stdout)

    def test_relative_npm_paths_are_resolved_from_project_root(self):
        executable = self.make_fake_npm()
        configured = self.inspect_settings(NPM_BIN_PATH=str(executable.relative_to(self.project)))
        self.assertEqual(Path(configured["npm"]), executable)

    def test_explicit_dot_relative_npm_path_is_resolved_from_project_root(self):
        configured = self.inspect_settings(NPM_BIN_PATH="./npm")
        self.assertEqual(Path(configured["npm"]), self.project / "npm")

    def test_empty_explicit_npm_override_fails_clearly(self):
        result = self.run_python(str(self.project / "manage.py"), "check", NPM_BIN_PATH="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("NPM_BIN_PATH is required", result.stderr)


if __name__ == "__main__":
    unittest.main()
