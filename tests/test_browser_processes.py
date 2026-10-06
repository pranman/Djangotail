"""Prove standalone browser startup failures release real descendant sockets."""

import json
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts import check_browser


FIXTURE = Path(__file__).resolve().parent / "fixtures/process_tree.py"


class BrowserProcessesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="browser process test ")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.project = self.directory / "source"
        (self.project / "theme/static_src/node_modules").mkdir(parents=True)
        self.artifacts = self.directory / "artifacts"
        self.artifacts.mkdir()
        self.records = self.directory / "records"
        self.records.mkdir()
        # Both fake development processes spawn real children which ignore TERM.
        # The server exits after spawning; the watcher remains running. The same
        # production fixture used by bootstrap tests owns each listening socket.
        (self.project / "manage.py").write_text(f'''
import os
from pathlib import Path
import subprocess
import sys
import time

if sys.argv[1:] == ["tailwind", "build"]:
    raise SystemExit(0)
name = "watcher" if sys.argv[1:] == ["tailwind", "start"] else "server"
directory = Path(os.environ["BROWSER_PROCESS_RECORDS"]) / name
directory.mkdir()
subprocess.Popen([sys.executable, {str(FIXTURE)!r}, "leaf", str(directory)])
while not (directory / "leaf.json").exists():
    time.sleep(0.02)
if name == "server":
    raise SystemExit(7)
print("Done in 1ms", flush=True)
while True:
    time.sleep(0.1)
''', encoding="utf-8")

    def assert_released(self, names):
        for name in names:
            record = json.loads((self.records / name / "leaf.json").read_text())
            deadline = time.monotonic() + 5
            while True:
                with socket.socket() as probe:
                    try:
                        probe.bind(("127.0.0.1", record["port"]))
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            self.fail(f"{name} descendant still owns port {record['port']}")
                time.sleep(0.05)

    def test_failed_second_start_stops_the_already_running_watcher_tree(self):
        start = check_browser.bootstrap.start_process

        def fail_server(name, *args, **kwargs):
            if name == "server":
                raise FileNotFoundError("simulated server launch failure")
            return start(name, *args, **kwargs)

        with patch.object(check_browser, "ROOT", self.project), \
             patch.dict(os.environ, {"BROWSER_PROCESS_RECORDS": str(self.records)}), \
             patch.object(check_browser.bootstrap, "start_process", side_effect=fail_server):
            with self.assertRaisesRegex(FileNotFoundError, "server launch failure"):
                with check_browser.isolated_server(self.artifacts):
                    self.fail("Failed startup must not yield a browser session")
        self.assert_released(("watcher",))

    def test_exited_parent_and_live_sibling_both_release_their_descendants(self):
        with patch.object(check_browser, "ROOT", self.project), \
             patch.dict(os.environ, {"BROWSER_PROCESS_RECORDS": str(self.records)}):
            with self.assertRaisesRegex(RuntimeError, "Development process exited"):
                with check_browser.isolated_server(self.artifacts):
                    self.fail("Exited server must not yield a browser session")
        self.assert_released(("server", "watcher"))


if __name__ == "__main__":
    unittest.main()
