#!/usr/bin/env python3
"""
WebSocket server for Flutter app.

Listens on 0.0.0.0:8000 and provides:
- Real-time RSL (signal strength) data streaming
- Command handling from Flutter client

Requires: pip install websockets
"""
import asyncio
import json
import random
import time
from typing import Set

try:
    import websockets
    from websockets.server import serve
except ImportError:
    print("Error: websockets not installed")
    print("Install with: pip install websockets")
    exit(1)

# Connected WebSocket clients
WS_CLIENTS: Set = set()


async def websocket_handler(websocket):
    """Handle WebSocket connections from Flutter app."""
    print(f"Client connected: {websocket.remote_address}")
    WS_CLIENTS.add(websocket)
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                cmd = data.get("cmd", "")
                
                if cmd == "PING":
                    await websocket.send(json.dumps({"response": "PONG"}))
                elif cmd == "GET_RSL":
                    # Send current RSL reading
                    rsl = -85.5 + random.uniform(-2, 2)
                    await websocket.send(json.dumps({"rsl": rsl, "timestamp": time.time()}))
                    
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"error": "Invalid JSON"}))
            except Exception as e:
                print(f"Error handling message: {e}")
                
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        WS_CLIENTS.discard(websocket)
        print(f"Client disconnected: {websocket.remote_address}")


async def broadcast_signal_data():
    """Broadcast simulated signal data to all connected clients."""
    while True:
        if WS_CLIENTS:
            # TODO: Replace with real VNA signal reading
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


async def main():
    """Start WebSocket server and broadcaster."""
    host = "0.0.0.0"
    port = 8000
    
    print(f"Starting WebSocket server on ws://{host}:{port}")
    
    async with serve(websocket_handler, host, port):
        print(f"Server ready. Flutter should connect to ws://192.168.15.192:{port}/ws")
        # Run broadcaster
        await broadcast_signal_data()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down server")
