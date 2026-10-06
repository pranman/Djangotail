"""An HTTP-first development process with explicitly gated watcher diagnostics."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time


def wait_for(path):
    while not path.exists():
        time.sleep(0.01)


def main():
    directory = Path(sys.argv[1])
    mode = sys.argv[2]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ready HTTP")
            (directory / "http-observed").touch()

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        address = directory / "address.json"
        temporary = address.with_suffix(".tmp")
        temporary.write_text(json.dumps({"url": f"http://127.0.0.1:{server.server_port}"}))
        temporary.replace(address)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        # The public launcher completes a different build before it starts the
        # watcher. These diagnostics deliberately arrive before HTTP is ready.
        print("Done in 10ms\n[10ms] [@tailwindcss/cli] (initial build)\nStarting CSS watcher...", flush=True)
        wait_for(directory / "release-watcher")
        if mode == "exit":
            print("Error: CSS watcher exited with code 7; stopping development.", flush=True)
            return 1
        # A generic 'Done in' may arrive from a no-op watcher callback while its
        # initial build is still in progress. It must not release the verifier.
        print("Done in 2ms\n[2ms] [@tailwindcss/cli] (watcher)", flush=True)
        (directory / "incremental-observed").touch()
        wait_for(directory / "release-initial-build")
        print("Done in \x1b[33m438ms\x1b[39m\n\x1b[2m[438.5ms]\x1b[22m [@tailwindcss/cli] (initial build)", flush=True)
        (directory / "initial-observed").touch()
        while True:
            time.sleep(0.1)


if __name__ == "__main__":
    raise SystemExit(main())
