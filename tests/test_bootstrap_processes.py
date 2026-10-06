"""Real descendant cleanup and port release on macOS, Linux, and Windows."""

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import bootstrap


FIXTURE = Path(__file__).resolve().parent / "fixtures/process_tree.py"


class DevelopmentProcessesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="starter process test ")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def start_supervisor(self):
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen([sys.executable, str(FIXTURE), "supervisor", str(self.directory)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
        self.addCleanup(self.cleanup_process, process)
        deadline = time.monotonic() + 15
        records = []
        for name in ("django", "watcher"):
            path = self.directory / name / "parent.json"
            while not path.exists():
                if process.poll() is not None or time.monotonic() >= deadline:
                    self.fail(f"Supervisor did not start {name}; return code {process.poll()}")
                time.sleep(0.02)
            records.append(json.loads((self.directory / name / "leaf.json").read_text()))
        return process, records

    def cleanup_process(self, process):
        if process.poll() is None:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    def assert_ports_released(self, records):
        # Checking the listening socket avoids platform differences around zombie PIDs.
        for record in records:
            deadline = time.monotonic() + 5
            while True:
                with socket.socket() as probe:
                    try:
                        probe.bind(("127.0.0.1", record["port"]))
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            self.fail(f"Descendant still owns port {record['port']}")
                time.sleep(0.05)

    def test_child_failure_stops_sibling_and_orphaned_grandchildren(self):
        process, records = self.start_supervisor()
        (self.directory / "django/exit").touch()
        self.assertEqual(process.wait(timeout=15), 1)
        self.assert_ports_released(records)

    def test_interrupt_stops_both_complete_process_trees(self):
        process, records = self.start_supervisor()
        process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
        self.assertEqual(process.wait(timeout=15), 130)
        self.assert_ports_released(records)

    def test_watcher_failure_stops_django_tree(self):
        process, records = self.start_supervisor()
        (self.directory / "watcher/exit").touch()
        self.assertEqual(process.wait(timeout=15), 1)
        self.assert_ports_released(records)

    def test_occupied_port_fails_before_build_or_launch(self):
        layout = bootstrap.Layout(self.directory)
        layout.environment.mkdir()
        (layout.root / ".env").touch()
        (layout.frontend / "node_modules").mkdir(parents=True)
        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen()
            with patch.object(bootstrap, "validate_environment"), \
                 patch.object(bootstrap, "run") as run, \
                 patch.object(bootstrap, "supervise") as supervise, \
                 self.assertRaisesRegex(bootstrap.BootstrapError, "Cannot bind"):
                bootstrap.dev(layout, bootstrap.Prerequisites("npm", "pip", None),
                              "127.0.0.1", busy.getsockname()[1])
        run.assert_not_called()
        supervise.assert_not_called()

    def test_dev_builds_before_launch_and_keeps_django_autoreload(self):
        layout = bootstrap.Layout(self.directory)
        layout.environment.mkdir()
        (layout.root / ".env").touch()
        (layout.frontend / "node_modules").mkdir(parents=True)
        order = []
        with patch.object(bootstrap, "validate_environment"), \
             patch.object(bootstrap, "ensure_port_available"), \
             patch.object(bootstrap, "run", side_effect=lambda *a, **k: order.append(a[0])), \
             patch.object(bootstrap, "supervise", side_effect=lambda commands: order.append(commands)):
            bootstrap.dev(layout, bootstrap.Prerequisites("npm", "pip", None), "127.0.0.1", 8123)
        self.assertEqual(order[1], ["npm", "run", "build"])
        self.assertEqual(order[2][0][1], [str(layout.python), "manage.py", "runserver", "127.0.0.1:8123"])
        self.assertEqual(order[2][1][1], ["npm", "run", "dev"])
        self.assertNotIn("--noreload", order[2][0][1])


if __name__ == "__main__":
    unittest.main()
