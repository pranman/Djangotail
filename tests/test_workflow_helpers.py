"""Release checks must start clean without modifying the caller's checkout."""

import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.starter_checks import (
    CommandLog, VerificationError, disposable_checkout, isolated_environment, settle_browser_reload,
)


class WorkflowFixtureTests(unittest.TestCase):
    def test_fixture_copies_tracked_source_without_configuration_or_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            subprocess.run(["git", "init", "--quiet", str(source)], check=True)
            (source / "manage.py").write_text("# tracked source\n")
            (source / ".env").write_text("local-secret=never-copy\n")
            subprocess.run(["git", "add", "manage.py", ".env"], cwd=source, check=True)
            with disposable_checkout(source, cold=True) as fixture:
                self.assertEqual((fixture.root / "manage.py").read_text(), "# tracked source\n")
                self.assertFalse((fixture.root / ".env").exists())
                self.assertIn(" ", str(fixture.root))
                self.assertNotEqual(fixture.root, fixture.caller)
                self.assertFalse(Path(fixture.environment["UV_CACHE_DIR"]).exists())
            self.assertEqual((source / ".env").read_text(), "local-secret=never-copy\n")

    def test_fixture_removes_active_project_and_django_configuration(self):
        values = {"DJANGO_DEBUG": "false", "DJANGO_SECRET_KEY": "private", "NPM_BIN_PATH": "bad",
                  "VIRTUAL_ENV": "other-project", "UV_PROJECT_ENVIRONMENT": "other-project"}
        with patch.dict(os.environ, values):
            environment = isolated_environment()
        for key in values:
            self.assertNotIn(key, environment)

    def test_diagnostic_logs_redact_known_secret_values(self):
        with tempfile.TemporaryDirectory() as directory:
            log = CommandLog(Path(directory))
            log.secrets.append("generated-private-value")
            log.write("check", "Error: generated-private-value")
            self.assertEqual((Path(directory) / "check.log").read_text(), "Error: [redacted]")

    def test_failure_diagnostics_scrub_a_secret_generated_before_setup_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            log = CommandLog(project / "diagnostics")
            (project / ".env").write_text("DJANGO_SECRET_KEY=late-generated-secret\n")
            (log.directory / "development.log").write_text("Error: late-generated-secret")
            log.sanitize(project)
            self.assertEqual((log.directory / "development.log").read_text(), "Error: [redacted]")


class BrowserReadinessTests(unittest.TestCase):
    def test_queued_reload_resets_the_stable_heartbeat_count(self):
        stream = io.BytesIO(
            b'data: {"type": "ping"}\n\n'
            b'data: {"type": "reload"}\n\n'
            b'data: {"type": "ping"}\n\n'
            b'data: {"type": "ping"}\n\n'
            b'data: {"type": "ping"}\n\n'
        )
        with patch("urllib.request.urlopen", return_value=stream):
            self.assertEqual(settle_browser_reload("http://127.0.0.1:8000"), 1)

    def test_initial_heartbeat_does_not_hide_a_pending_reload(self):
        stream = io.BytesIO(
            b'data: {"type": "ping"}\n\n'
            b'data: {"type": "reload"}\n\n'
            b'data: {"type": "ping"}\n\n'
            b'data: {"type": "ping"}\n\n'
        )
        with patch("urllib.request.urlopen", return_value=stream), self.assertRaisesRegex(
            VerificationError, "closed before it settled"
        ):
            settle_browser_reload("http://127.0.0.1:8000")
