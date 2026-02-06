#!/usr/bin/env python3
"""
Flutter App Communication Server - WebSocket & TCP

This server enables bidirectional communication between the Antenna Aligner
Flutter mobile app and the Raspberry Pi 5 VNA controller. It provides two
protocols for flexibility:

1. **WebSocket (Port 8000)**: Primary protocol for Flutter app
   - JSON-formatted bidirectional messaging
   - Real-time signal strength streaming (RSL data)
   - Command/response pattern for VNA control

2. **TCP Plain Text (Port 8000)**: Testing/debugging interface
   - Simple text commands: PING, STATUS, RUN, QUIT
   - Useful for netcat testing: nc 192.168.15.90 8000

Architecture:
- Multi-threaded TCP server (handles multiple connections)
- Async WebSocket server (efficient real-time streaming)
- Background job manager (tracks running VNA measurements)
- Signal broadcaster (pushes RSL data to all connected clients)

Dependencies:
  pip install websockets

Systemd Service:
  sudo systemctl enable pi_tcp_server.service
  sudo systemctl start pi_tcp_server.service
"""

# ==================================================================
# IMPORT DEPENDENCIES
# ==================================================================
# ==================================================================
# IMPORT DEPENDENCIES
# ==================================================================

from __future__ import annotations
import asyncio          # Async WebSocket server
import json             # JSON encoding for Flutter communication
import random           # Simulated signal data (temporary)
import shlex            # Safe shell argument parsing
import socketserver     # TCP server framework
import subprocess       # Launch VNA control scripts
import threading        # Background job cleanup
import time
from typing import Dict, Set, Tuple

# WebSocket library (optional but recommended)
try:
    import websockets
    from websockets.server import serve
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False
    print("Warning: websockets not installed. Install with: pip install websockets")

# ==================================================================
# GLOBAL STATE
# ==================================================================

# Job tracking: Maps PID -> (subprocess.Popen object, command string)
# Tracks running VNA measurement processes
JOBS_LOCK = threading.Lock()
JOBS: Dict[int, Tuple[subprocess.Popen, str]] = {}

# WebSocket client tracking: Set of active websocket connections
# Used for broadcasting signal data to all connected Flutter apps
WS_CLIENTS: Set = set()


# ==================================================================
# TCP SERVER - Plain Text Command Interface
# ==================================================================


class ThreadedTCPHandler(socketserver.StreamRequestHandler):
    """
    Handle plain-text TCP connections for testing and debugging.
    
    Supported Commands:
    - PING: Responds with PONG (connection test)
    - STATUS: Lists all running jobs (PID and command)
    - RUN <args>: Launches znle_pyvisa.py with specified arguments
    - QUIT/EXIT: Closes connection
    
    Example Usage:
      echo "PING" | nc 192.168.15.90 8000
      echo "RUN --monitor 977e6" | nc 192.168.15.90 8000
    """
    
    def handle(self) -> None:
        """Process incoming TCP connection and commands."""
        peer = self.client_address
        print(f"Connection from {peer}")
        
        # Read commands line by line until client disconnects
        for raw in self.rfile:
            try:
                line = raw.decode("utf-8", errors="replace").strip()
            except Exception:
                break
            if not line:
                continue
            
            cmd = line.strip()
            print(f"Received command from {peer}: {cmd}")

            # ---------------------------------------------------
            # Command: PING - Connection test
            # ---------------------------------------------------
            if cmd.upper() == "PING":
                self.wfile.write(b"PONG\n")
                self.wfile.flush()
                continue

            # ---------------------------------------------------
            # Command: QUIT/EXIT - Close connection
            # ---------------------------------------------------
            if cmd.upper() in ("QUIT", "EXIT"):
                self.wfile.write(b"BYE\n")
                self.wfile.flush()
                break

            # ---------------------------------------------------
            # Command: STATUS - List running jobs
            # ---------------------------------------------------
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

            # ---------------------------------------------------
            # Command: RUN <args> - Launch VNA measurement
            # ---------------------------------------------------
            if cmd.startswith("RUN "):
                args_part = cmd[4:].strip()
                if not args_part:
                    self.wfile.write(b"ERROR: missing args\n")
                    self.wfile.flush()
                    continue

                # Build command: python3 scripts/znle_pyvisa.py <args>
                parts = shlex.split(args_part)
                cmd_list = ["python3", "scripts/znle_pyvisa.py"] + parts

                try:
                    proc = subprocess.Popen(cmd_list)
                except Exception as exc:
                    self.wfile.write(f"ERROR: failed to start: {exc}\n".encode("utf-8"))
                    self.wfile.flush()
                    continue

                # Track the subprocess
                with JOBS_LOCK:
                    JOBS[proc.pid] = (proc, " ".join(cmd_list))

                self.wfile.write(f"STARTED {proc.pid}\n".encode("utf-8"))
                self.wfile.flush()
                continue

            # ---------------------------------------------------
            # Unknown command
            # ---------------------------------------------------
            self.wfile.write(b"ERROR: unknown command\n")
            self.wfile.flush()


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Multi-threaded TCP server (allows multiple simultaneous connections)."""
    allow_reuse_address = True


# ==================================================================
# BACKGROUND JOB MANAGEMENT
# ==================================================================

def reap_jobs() -> None:
    """
    Background cleanup thread for finished VNA measurement jobs.
    
    Runs in daemon thread, polls every second to check if spawned
    processes have exited. Removes completed jobs from JOBS dict.
    """
    while True:
        with JOBS_LOCK:
            to_delete = []
            for pid, (proc, _) in list(JOBS.items()):
                ret = proc.poll()  # Returns None if still running
                if ret is not None:  # Process has exited
                    to_delete.append(pid)
            for pid in to_delete:
                print(f"Job {pid} finished")
                JOBS.pop(pid, None)
        time.sleep(1.0)


# ==================================================================
# WEBSOCKET SERVER - Real-Time Flutter Communication
# ==================================================================

# ==================================================================
# WEBSOCKET SERVER - Real-Time Flutter Communication
# ==================================================================

async def websocket_handler(websocket):
    """
    Handle individual WebSocket connection from Flutter app.
    
    Receives JSON commands from app (e.g., {"cmd": "PING"})
    Responds with JSON messages (e.g., {"response": "PONG"})
    
    Connection lifetime:
    - Add to WS_CLIENTS on connect
    - Process incoming messages
    - Remove from WS_CLIENTS on disconnect
    """
    print(f"WebSocket client connected: {websocket.remote_address}")
    WS_CLIENTS.add(websocket)
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                cmd = data.get("cmd", "")
                
                # Handle PING command
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
    """
    Continuously broadcast signal strength data to all connected clients.
    
    Current Implementation: Simulated RSL data with random variation
    Future Enhancement: Read real RSL from VNA measurements
    
    Broadcast Format:
      {"rsl": -85.5, "timestamp": 1738872940.123}
    
    Update Rate: 2 Hz (every 0.5 seconds)
    """
    while True:
        if WS_CLIENTS:
            # TODO: Replace with real signal data from VNA
            # Simulated RSL: -85.5 dBm ± 2 dB random variation
            data = {
                "rsl": -85.5 + random.uniform(-2, 2),
                "timestamp": time.time()
            }
            
            # Broadcast to all connected clients
            disconnected = set()
            for client in WS_CLIENTS:
                try:
                    await client.send(json.dumps(data))
                except Exception:
                    # Mark for removal if send fails
                    disconnected.add(client)
            
            # Clean up disconnected clients
            WS_CLIENTS.difference_update(disconnected)
        
        await asyncio.sleep(0.5)  # 2 Hz update rate


async def start_websocket_server(host: str, port: int):
    """
    Start WebSocket server and signal broadcaster.
    
    Runs forever, serving WebSocket connections and broadcasting data.
    """
    async with serve(websocket_handler, host, port):
        print(f"WebSocket server listening on ws://{host}:{port}/ws")
        # Start signal broadcaster (runs forever)
        await broadcast_signal_data()


def run_websocket_server(host: str, port: int):
    """Run WebSocket server in asyncio event loop."""
    asyncio.run(start_websocket_server(host, port))


# ==================================================================
# MAIN ENTRY POINT
# ==================================================================

# ==================================================================
# MAIN ENTRY POINT
# ==================================================================

def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    """
    Start the communication server.
    
    1. Launch background job cleanup thread
    2. Start WebSocket server (if library available)
    
    Args:
        host: Listen address (0.0.0.0 = all interfaces)
        port: Listen port (default: 8000)
    """
    # Start background thread to clean up finished jobs
    janitor = threading.Thread(target=reap_jobs, daemon=True)
    janitor.start()

    if WS_AVAILABLE:
        print(f"Starting WebSocket server on {host}:{port}")
        run_websocket_server(host, port)
    else:
        print("WebSocket library not available. Install with: pip install websockets")


if __name__ == "__main__":
    main()
