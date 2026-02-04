#!/usr/bin/env python3
"""
Simple TCP control server for the Pi.

Listens on 0.0.0.0:8000 by default and accepts simple newline-terminated
commands from a Flutter client or netcat/telnet.

Commands:
  PING              -> responds with PONG
  RUN <args>        -> starts `znle_pyvisa.py` with the provided args (space-separated)
  STATUS            -> lists running jobs (pid and command)
  QUIT or EXIT      -> closes the connection

Runs each RUN command as a subprocess and returns the PID.
"""
from __future__ import annotations
import shlex
import socketserver
import subprocess
import threading
from typing import Dict, Tuple

JOBS_LOCK = threading.Lock()
JOBS: Dict[int, Tuple[subprocess.Popen, str]] = {}


class ThreadedTCPHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        peer = self.client_address
        print(f"Connection from {peer}")
        for raw in self.rfile:
            try:
                line = raw.decode("utf-8", errors="replace").strip()
            except Exception:
                break
            if not line:
                continue
            cmd = line.strip()
            print(f"Received command from {peer}: {cmd}")

            if cmd.upper() == "PING":
                self.wfile.write(b"PONG\n")
                self.wfile.flush()
                continue

            if cmd.upper() in ("QUIT", "EXIT"):
                self.wfile.write(b"BYE\n")
                self.wfile.flush()
                break

            if cmd.upper() == "STATUS":
                with JOBS_LOCK:
                    if not JOBS:
                        self.wfile.write(b"NO_JOBS\n")
                    else:
                        for pid, (proc, cmdline) in JOBS.items():
                            line_out = f"PID:{pid} CMD:{cmdline}\n".encode("utf-8")
                            self.wfile.write(line_out)
                self.wfile.flush()
                continue

            if cmd.startswith("RUN "):
                args_part = cmd[4:].strip()
                if not args_part:
                    self.wfile.write(b"ERROR: missing args\n")
                    self.wfile.flush()
                    continue

                # Build command: run local znle_pyvisa.py using python3
                parts = shlex.split(args_part)
                cmd_list = ["python3", "scripts/znle_pyvisa.py"] + parts

                try:
                    proc = subprocess.Popen(cmd_list)
                except Exception as exc:  # pragma: no cover - runtime
                    self.wfile.write(f"ERROR: failed to start: {exc}\n".encode("utf-8"))
                    self.wfile.flush()
                    continue

                with JOBS_LOCK:
                    JOBS[proc.pid] = (proc, " ".join(cmd_list))

                self.wfile.write(f"STARTED {proc.pid}\n".encode("utf-8"))
                self.wfile.flush()
                continue

            # Unknown command
            self.wfile.write(b"ERROR: unknown command\n")
            self.wfile.flush()


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


def reap_jobs() -> None:
    """Background thread to remove finished jobs from JOBS dict."""
    import time

    while True:
        with JOBS_LOCK:
            to_delete = []
            for pid, (proc, _) in list(JOBS.items()):
                ret = proc.poll()
                if ret is not None:
                    to_delete.append(pid)
            for pid in to_delete:
                print(f"Job {pid} finished")
                JOBS.pop(pid, None)
        time.sleep(1.0)


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    server = ThreadingTCPServer((host, port), ThreadedTCPHandler)
    print(f"Listening on {host}:{port}")

    janitor = threading.Thread(target=reap_jobs, daemon=True)
    janitor.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down server")
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
