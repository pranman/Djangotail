"""Real process trees for portable bootstrap lifecycle tests (no Django needed)."""

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import bootstrap


def record(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data), encoding="utf-8")
    temporary.replace(path)


def leaf(directory):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    if os.name == "nt":
        signal.signal(signal.SIGBREAK, signal.SIG_IGN)
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        record(directory / "leaf.json", {"pid": os.getpid(), "port": server.getsockname()[1]})
        while True:
            time.sleep(0.1)


def parent(directory):
    subprocess.Popen([sys.executable, __file__, "leaf", str(directory)])
    while not (directory / "leaf.json").exists():
        time.sleep(0.02)
    record(directory / "parent.json", {"pid": os.getpid()})
    while not (directory / "exit").exists():
        time.sleep(0.02)
    return 7


def supervisor(directory):
    commands = []
    for name in ("django", "watcher"):
        child_directory = directory / name
        child_directory.mkdir()
        commands.append((name, [sys.executable, __file__, "parent", str(child_directory)], directory))
    try:
        bootstrap.supervise(commands)
    except KeyboardInterrupt:
        return 130
    except bootstrap.BootstrapError:
        return 1


if __name__ == "__main__":
    mode, directory = sys.argv[1:]
    raise SystemExit(globals()[mode](Path(directory)))
