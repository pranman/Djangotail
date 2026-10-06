"""Exercise the real HTTP-first ordering that exposed the hosted Windows race."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from scripts.starter_checks import (
    VerificationError, wait_for_development_ready, wait_until, watcher_initial_build_complete,
)


FIXTURE = Path(__file__).resolve().parent / "fixtures/development_readiness.py"


class WatcherLogTests(unittest.TestCase):
    def test_prelaunch_production_build_and_incremental_callbacks_are_not_readiness(self):
        initial = "Done in 10ms\n[10ms] [@tailwindcss/cli] (initial build)\n"
        self.assertFalse(watcher_initial_build_complete(initial))
        self.assertFalse(watcher_initial_build_complete(
            initial + "Starting CSS watcher...\nDone in 2ms\n[2ms] [@tailwindcss/cli] (watcher)\n"
        ))

    def test_windows_line_endings_and_ansi_styles_are_supported(self):
        output = ("Starting CSS watcher...\r\nDone in \x1b[33m438ms\x1b[39m\r\n"
                  "\x1b[2m[438.5ms]\x1b[22m [@tailwindcss/cli] (initial build)\r\n")
        self.assertTrue(watcher_initial_build_complete(output))

    def test_failed_initial_build_diagnostics_without_success_are_not_readiness(self):
        output = "Starting CSS watcher...\n[10ms] [@tailwindcss/cli] (initial build)\nError starting watch stream\n"
        self.assertFalse(watcher_initial_build_complete(output))


class DevelopmentReadinessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="delayed watcher ")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.logfile = self.directory / "development.log"

    def start_fixture(self, mode="delayed"):
        with self.logfile.open("w", encoding="utf-8") as output:
            process = subprocess.Popen([sys.executable, "-u", str(FIXTURE), str(self.directory), mode],
                                       stdout=output, stderr=subprocess.STDOUT)
        self.addCleanup(self.stop_fixture, process)
        address = self.directory / "address.json"
        wait_until(address.exists, "HTTP fixture did not start", timeout=5)
        return process, json.loads(address.read_text())["url"]

    @staticmethod
    def stop_fixture(process):
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)

    def test_http_first_and_noop_callback_wait_for_the_delayed_initial_build(self):
        process, url = self.start_fixture()
        finished = threading.Event()
        errors = []

        def check():
            try:
                wait_for_development_ready(process, url, self.logfile, timeout=5)
            except Exception as error:
                errors.append(error)
            finally:
                finished.set()

        worker = threading.Thread(target=check, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 6)
        wait_until((self.directory / "http-observed").exists, "HTTP was not observed", timeout=5)
        self.assertFalse(finished.wait(0.1), errors)
        (self.directory / "release-watcher").touch()
        wait_until((self.directory / "incremental-observed").exists, "No-op callback was not observed", timeout=5)
        self.assertFalse(finished.wait(0.1), errors)
        (self.directory / "release-initial-build").touch()
        self.assertTrue(finished.wait(5), "Verifier never accepted the actual initial build")
        self.assertFalse(errors, errors)

    def test_early_watcher_failure_names_the_child_and_exit_code(self):
        process, url = self.start_fixture("exit")
        (self.directory / "release-watcher").touch()
        process.wait(timeout=5)
        with self.assertRaisesRegex(VerificationError, "CSS watcher exited with code 7.*development.log"):
            wait_for_development_ready(process, url, self.logfile)

    def test_http_success_without_initial_build_times_out_actionably(self):
        process, url = self.start_fixture()
        with self.assertRaisesRegex(VerificationError, "timed out waiting for CSS watcher initial build"):
            wait_for_development_ready(process, url, self.logfile, timeout=0.25)
        self.assertTrue((self.directory / "http-observed").exists())

    def test_launcher_exit_without_child_diagnostic_is_actionable(self):
        self.logfile.write_text("Starting CSS watcher...\n")
        with self.assertRaisesRegex(VerificationError, "launcher exited before readiness \\(code 17\\)"):
            wait_for_development_ready(Mock(poll=Mock(return_value=17)), "http://unused", self.logfile)

    def test_watcher_completion_without_http_success_does_not_become_ready(self):
        from urllib.error import URLError
        self.logfile.write_text("Starting CSS watcher...\nDone in 12ms\n[12ms] [@tailwindcss/cli] (initial build)\n")
        with patch("urllib.request.urlopen", side_effect=URLError("not listening")), self.assertRaisesRegex(
            VerificationError, "timed out waiting for Django HTTP response"
        ):
            wait_for_development_ready(Mock(poll=Mock(return_value=None)), "http://unused", self.logfile, timeout=0.1)

    def test_launcher_exit_during_the_http_probe_is_not_reported_as_ready(self):
        self.logfile.write_text("Starting CSS watcher...\nDone in 12ms\n[12ms] [@tailwindcss/cli] (initial build)\n")
        response = Mock(status=200)
        with patch("urllib.request.urlopen") as fetch:
            fetch.return_value.__enter__.return_value = response
            with self.assertRaisesRegex(VerificationError, "launcher exited before readiness \\(code 17\\)"):
                wait_for_development_ready(Mock(poll=Mock(side_effect=[None, 17])), "http://unused", self.logfile)
