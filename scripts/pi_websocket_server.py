#!/usr/bin/env python3
"""
WebSocket server for Flutter app.

Listens on 0.0.0.0:8000 and provides:
- Real-time RSL (signal strength) data streaming from VNA
- Sweep data (azimuth/elevation) with degree + amplitude
- Motor position tracking
- Command handling from Flutter client

The Flutter app connects and automatically receives sweep data when the
real-time monitor motor controls script is running.

Requires: pip install websockets pyvisa pyvisa-py pyserial

NOTE: This server REQUIRES real VNA hardware connection. No simulated data fallback.
Will exit with error if VNA cannot be connected.
"""
import asyncio
import json
import time
from typing import Optional, Set, Dict, List

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
    print("ERROR: pyvisa not installed. Real VNA data is required.")
    print("Install with: pip install pyvisa pyvisa-py")
    exit(1)

try:
    import serial
except ImportError:
    print("Warning: pyserial not installed. Motor control disabled.")
    print("Install with: pip install pyserial")
    serial = None

# Connected WebSocket clients
WS_CLIENTS: Set = set()

# VNA connection settings
VNA_IP = "192.168.15.90"
VNA_PORT = 5025
VNA_FREQ = 1e9  # 1 GHz
VNA_PARAM = "S21"  # S-parameter to measure
vna_instrument = None

# Motor controller settings
MOTOR_PORT = "/dev/ttyACM0"  # Arduino serial port
motor_serial = None
current_azimuth = 0.0
current_elevation = 0.0

# Sweep state
sweep_active = False
sweep_type = None  # "azimuth" or "elevation"
sweep_data: List[Dict] = []  # List of {degree, amplitude} points


async def websocket_handler(websocket):
    """Handle WebSocket connections from Flutter app."""
    global sweep_active, sweep_type, sweep_data, current_azimuth, current_elevation
    
    print(f"Client connected: {websocket.remote_address}")
    WS_CLIENTS.add(websocket)
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                cmd = data.get("cmd", "")
                action = data.get("action", "")
                
                if cmd == "PING":
                    await websocket.send(json.dumps({"response": "PONG"}))
                    
                elif cmd == "GET_RSL":
                    # Send current RSL reading
                    rsl = get_vna_reading()
                    await websocket.send(json.dumps({
                        "rsl": rsl, 
                        "timestamp": time.time(),
                        "azimuth_degree": current_azimuth,
                        "elevation_degree": current_elevation
                    }))
                    
                elif cmd == "START_SWEEP":
                    # Start a new sweep (azimuth or elevation)
                    sweep_type = data.get("sweep_type", "azimuth")
                    sweep_active = True
                    sweep_data = []
                    await websocket.send(json.dumps({
                        "sweep_status": "started",
                        "sweep_type": sweep_type
                    }))
                    print(f"Started {sweep_type} sweep")
                    
                elif cmd == "STOP_SWEEP":
                    # Complete the sweep and send all collected data
                    sweep_active = False
                    await websocket.send(json.dumps({
                        "sweep_status": "completed",
                        "sweep_type": sweep_type,
                        "sweep_data": sweep_data
                    }))
                    print(f"Completed {sweep_type} sweep with {len(sweep_data)} points")
                    sweep_data = []
                    
                elif action == "start":
                    # Legacy support for initial connection
                    await websocket.send(json.dumps({
                        "status": "ready",
                        "rsl": get_vna_reading(),
                        "azimuth_degree": current_azimuth,
                        "elevation_degree": current_elevation
                    }))
                    
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


def connect_vna() -> object:
    """Connect to VNA instrument. FAILS HARD if connection cannot be established."""
    global vna_instrument
    
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
        print(f"FATAL ERROR: Failed to connect to VNA at {VNA_IP}:{VNA_PORT} - {e}")
        print("Real VNA data is required. Cannot proceed with simulated data.")
        exit(1)


def get_vna_reading() -> float:
    """Get single amplitude reading from VNA. FAILS if VNA data unavailable."""
    global vna_instrument
    
    if vna_instrument is None:
        raise RuntimeError("VNA instrument not connected. Cannot provide simulated data.")
    
    try:
        vna_instrument.write("INIT")
        vna_instrument.query("*OPC?")
        data_str = vna_instrument.query("CALC:DATA? FDATA")
        amplitude = float(data_str.strip().split(",")[0])
        return amplitude
    except Exception as e:
        print(f"FATAL ERROR: Failed to read from VNA: {e}")
        raise RuntimeError(f"VNA read error: {e}. No fallback simulated data available.")


def connect_motor():
    """Connect to Arduino motor controller."""
    global motor_serial
    if serial is None:
        print("PySerial not available, motor control disabled")
        return None
    
    try:
        motor_serial = serial.Serial(MOTOR_PORT, 115200, timeout=2)
        time.sleep(2)  # Wait for Arduino reset
        
        # Clear startup messages
        while motor_serial.in_waiting > 0:
            motor_serial.readline()
        
        # Test connection
        motor_serial.write(b"STATUS\n")
        motor_serial.flush()
        time.sleep(0.2)
        
        if motor_serial.in_waiting > 0:
            response = motor_serial.readline().decode('utf-8').strip()
            print(f"Motor controller connected: {response}")
            return motor_serial
        else:
            print("Motor controller not responding")
            return None
    except Exception as e:
        print(f"Failed to connect to motor controller: {e}")
        return None


def query_motor_position():
    """Query current motor position from Arduino."""
    global current_azimuth, current_elevation, motor_serial
    
    if motor_serial is None or not motor_serial.is_open:
        return
    
    try:
        motor_serial.write(b"STATUS\n")
        motor_serial.flush()
        
        start = time.time()
        while motor_serial.in_waiting == 0 and (time.time() - start) < 0.3:
            time.sleep(0.01)
        
        if motor_serial.in_waiting > 0:
            response = motor_serial.readline().decode('utf-8').strip()
            # Parse: "AZ=123.45 EL=67.89"
            if 'AZ' in response and 'EL' in response:
                parts = response.split()
                for part in parts:
                    if part.startswith('AZ'):
                        current_azimuth = float(part.split('=')[1])
                    elif part.startswith('EL'):
                        current_elevation = float(part.split('=')[1])
    except Exception:
        pass  # Silent failure


async def broadcast_signal_data():
    """Broadcast real VNA signal data to all connected clients."""
    global vna_instrument, sweep_active, sweep_type, sweep_data
    global current_azimuth, current_elevation
    
    # Connect to VNA and motor controller
    vna_instrument = connect_vna()
    connect_motor()
    
    while True:
        if WS_CLIENTS:
            # Query motor position
            query_motor_position()
            
            # Get real VNA data (only source of truth)
            rsl_value = get_vna_reading()
            
            # Build data packet (all data is from real VNA)
            data = {
                "rsl": rsl_value,
                "amplitude": rsl_value,
                "timestamp": time.time(),
                "azimuth_degree": current_azimuth,
                "elevation_degree": current_elevation
            }
            
            # If sweep is active, also include sweep data point
            if sweep_active:
                degree = current_azimuth if sweep_type == "azimuth" else current_elevation
                sweep_point = {"degree": degree, "amplitude": rsl_value}
                sweep_data.append(sweep_point)
                data["sweep_active"] = True
                data["sweep_type"] = sweep_type
                data["sweep_point"] = sweep_point
            
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
