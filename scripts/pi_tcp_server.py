#!/usr/bin/env python3
"""
WebSocket + TCP control server for the Pi.

Listens on 0.0.0.0:8000 by default and accepts:
1. WebSocket connections at /ws for Flutter app (streams JSON data)
2. Plain TCP text commands for testing/control

Requires: pip install websockets
"""
from __future__ import annotations
import asyncio
import json
import random
import shlex
import subprocess
import threading
import time
from typing import Dict, Set, Tuple

try:
    import websockets
    from websockets.server import serve
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False
    print("Warning: websockets not installed. Install with: pip install websockets")

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


JOBS_LOCK = threading.Lock()
JOBS: Dict[int, Tuple[subprocess.Popen, str]] = {}
WS_CLIENTS: Set = set()


def reap_jobs() -> None:
    """Background thread to remove finished jobs from JOBS dict."""
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


async def websocket_handler(websocket):
    """Handle WebSocket connections from Flutter app."""
    print(f"WebSocket client connected: {websocket.remote_address}")
    WS_CLIENTS.add(websocket)
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                cmd = data.get("cmd", "")
                if cmd == "PING":
                    await websocket.send(json.dumps({"response": "PONG"}))
            except Exception as e:
                print(f"Error handling message: {e}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        WS_CLIENTS.discard(websocket)
        print(f"WebSocket client disconnected: {websocket.remote_address}")


async def broadcast_signal_data():
    """Broadcast simulated signal data to all connected WebSocket clients."""
    while True:
        if WS_CLIENTS:
            # In production, read real signal data here
            data = {
                "rsl": -85.5 + random.uniform(-2, 2),
                "timestamp": time.time()
            }
            # Broadcast to all clients
            disconnected = set()
            for client in WS_CLIENTS:
                try:
                    await client.send(json.dumps(data))
                except Exception:
                    disconnected.add(client)
            # Remove disconnected clients
            WS_CLIENTS.difference_update(disconnected)
        await asyncio.sleep(0.5)


async def start_websocket_server(host: str, port: int):
    """Start WebSocket server."""
    async with serve(websocket_handler, host, port):
        print(f"WebSocket server listening on ws://{host}:{port}/ws")
        # Start broadcaster
        await broadcast_signal_data()


def run_websocket_server(host: str, port: int):
    """Run WebSocket server in asyncio event loop."""
    asyncio.run(start_websocket_server(host, port))


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    janitor = threading.Thread(target=reap_jobs, daemon=True)
    janitor.start()

    if WS_AVAILABLE:
        print(f"Starting WebSocket server on {host}:{port}")
        run_websocket_server(host, port)
    else:
        print("WebSocket library not available. Install with: pip install websockets")


if __name__ == "__main__":
    main()
