#!/usr/bin/env python3
"""
WebSocket server for Flutter app.

Listens on 0.0.0.0:8000 and provides:
- Real-time RSL (signal strength) data streaming from VNA
- Command handling from Flutter client

Requires: pip install websockets pyvisa pyvisa-py
"""
import asyncio
import json
import random
import time
from typing import Optional, Set

try:
    import websockets
    from websockets.server import serve
except ImportError:
    print("Error: websockets not installed")
    print("Install with: pip install websockets")
    exit(1)

try:
    import pyvisa as visa
except ImportError:
    print("Warning: pyvisa not installed. Using simulated data.")
    print("Install with: pip install pyvisa pyvisa-py")
    visa = None

# Connected WebSocket clients
WS_CLIENTS: Set = set()

# VNA connection settings
VNA_IP = "192.168.15.90"
VNA_PORT = 5025
VNA_FREQ = 1e9  # 1 GHz
VNA_PARAM = "S21"  # S-parameter to measure
vna_instrument = None


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


def connect_vna() -> Optional:
    """Connect to VNA instrument."""
    global vna_instrument
    if visa is None:
        print("PyVISA not available, using simulated data")
        return None
    
    try:
        rm = visa.ResourceManager("@py")
        resource = f"TCPIP0::{VNA_IP}::{VNA_PORT}::SOCKET"
        inst = rm.open_resource(resource)
        inst.timeout = 5000
        inst.write_termination = "\n"
        inst.read_termination = "\n"
        
        # Configure for single-point measurement
        inst.write("FORM:DATA ASCii")
        inst.write("CALC:PAR:PORT 1")
        inst.write(f"CALC:PAR:DEF 'Trc1',{VNA_PARAM}")
        inst.write("CALC:PAR:SEL 'Trc1'")
        inst.write(f"SENS:FREQ:STAR {VNA_FREQ}")
        inst.write(f"SENS:FREQ:STOP {VNA_FREQ}")
        inst.write("SENSe:SWEep:POINts 1")
        inst.write("CALC:FORM MLOG")  # log magnitude (dB)
        inst.write("INIT:CONT OFF")
        
        idn = inst.query("*IDN?")
        print(f"Connected to VNA: {idn.strip()}")
        return inst
    except Exception as e:
        print(f"Failed to connect to VNA at {VNA_IP}:{VNA_PORT} - {e}")
        print("Falling back to simulated data")
        return None


def get_vna_reading() -> float:
    """Get single amplitude reading from VNA."""
    global vna_instrument
    
    if vna_instrument is None:
        # Simulated data
        return -85.5 + random.uniform(-2, 2)
    
    try:
        vna_instrument.write("INIT")
        vna_instrument.query("*OPC?")
        data_str = vna_instrument.query("CALC:DATA? FDATA")
        amplitude = float(data_str.strip().split(",")[0])
        return amplitude
    except Exception as e:
        print(f"Error reading from VNA: {e}")
        # Return simulated value on error
        return -85.5 + random.uniform(-2, 2)


async def broadcast_signal_data():
    """Broadcast real VNA signal data to all connected clients."""
    global vna_instrument
    
    # Connect to VNA
    vna_instrument = connect_vna()
    
    while True:
        if WS_CLIENTS:
            # Get real or simulated RSL data
            rsl_value = get_vna_reading()
            
            data = {
                "rsl": rsl_value,
                "timestamp": time.time(),
                "source": "vna" if vna_instrument else "simulated"
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
