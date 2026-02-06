#!/usr/bin/env python3
"""
ZNLE6 Vector Network Analyzer (VNA) Control Script

This script communicates with the R&S ZNLE6 VNA over TCP/IP to:
- Perform frequency sweeps and save amplitude data to CSV  
- Monitor signal strength over time for antenna alignment
- Generate plots for visual analysis

Hardware setup:
- ZNLE6 VNA connected via Ethernet
- Signal source (NanoVNA H4) transmitting at test frequency
- Receiver antenna (Pasco WA-9800A) connected to ZNLE6 port 1

Usage:
  Single sweep:  python3 znle_pyvisa.py --start 900e6 --stop 1500e6 --out data.csv --plot
  Monitor mode:  python3 znle_pyvisa.py --monitor --monitor-freq 977e6 --duration 60 --plot

Dependencies:
  pip install pyvisa pyvisa-py matplotlib
"""

from __future__ import annotations
import argparse
import os
import sys
import time
from datetime import datetime

# ============================================================================
# IMPORT DEPENDENCIES
# ============================================================================

try:
    import pyvisa as visa
except ImportError:
    print("Error: pyvisa not installed. Run: pip install pyvisa pyvisa-py", file=sys.stderr)
    sys.exit(1)

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend (saves files without displaying)
    import matplotlib.pyplot as plt
except ImportError:
    print("Error: matplotlib not installed. Run: pip install matplotlib", file=sys.stderr)
    sys.exit(1)


# ============================================================================
# VNA INSTRUMENT CONTROL FUNCTIONS
# ============================================================================

def connect_to_vna(ip: str, port: int) -> visa.Resource:
    """
    Establish TCP/IP connection to ZNLE6 VNA.
    
    Args:
        ip: VNA IP address (e.g., "192.168.15.90")
        port: SCPI command port (usually 5025)
    
    Returns:
        PyVISA instrument resource object
    """
    rm = visa.ResourceManager("@py")  # Use pyvisa-py backend (pure Python)
    resource = f"TCPIP0::{ip}::{port}::SOCKET"
    inst = rm.open_resource(resource)
    inst.timeout = 15000  # 15 second timeout for commands
    inst.write_termination = "\n"
    inst.read_termination = "\n"
    return inst


def configure_vna(inst: visa.Resource, start_freq: float, stop_freq: float, 
                  points: int, param: str, sweep_time: float = None) -> None:
    """
    Configure VNA measurement parameters.
    
    Args:
        inst: PyVISA instrument object
        start_freq: Starting frequency in Hz
        stop_freq: Stopping frequency in Hz
        points: Number of frequency points to measure
        param: S-parameter to measure (S11, S21, S12, or S22)
        sweep_time: Optional sweep duration in seconds
    """
    # Set data format to ASCII (human-readable text)
    inst.write("FORM:DATA ASCii")
    
    # Configure to read from port 1 (receiver antenna input)
    inst.write("CALC:PAR:PORT 1")
    
    # Define and select measurement trace
    inst.write(f"CALC:PAR:DEF 'Trc1',{param}")
    inst.write("CALC:PAR:SEL 'Trc1'")
    
    # Set frequency range
    inst.write(f"SENS:FREQ:STAR {start_freq}")
    inst.write(f"SENS:FREQ:STOP {stop_freq}")
    inst.write(f"SENS:SWEep:POINts {points}")
    
    # Set sweep time if specified
    if sweep_time is not None:
        inst.write(f"SENS:SWEep:TIME {sweep_time}")
    
    # Set amplitude format to logarithmic magnitude (dB)
    inst.write("CALC:FORM MLOG")
    
    # Disable continuous sweeping (single sweep mode)
    inst.write("INIT:CONT OFF")


def perform_sweep(inst: visa.Resource) -> list[float]:
    """
    Trigger a single frequency sweep and retrieve amplitude data.
    
    Args:
        inst: PyVISA instrument object
    
    Returns:
        List of amplitude values in dB
    """
    # Initiate sweep
    inst.write("INIT")
    
    # Wait for sweep to complete
    inst.query("*OPC?")
    
    # Retrieve formatted data (amplitude in dB)
    data_str = inst.query("CALC:DATA? FDATA")
    
    # Parse comma-separated values into float list
    amplitudes = [float(x) for x in data_str.strip().split(",") if x.strip()]
    
    return amplitudes


# ============================================================================
# DATA PROCESSING AND PLOTTING
# ============================================================================

def save_frequency_sweep(frequencies: list[float], amplitudes: list[float], 
                         output_path: str) -> None:
    """
    Save frequency sweep data to CSV file.
    
    Args:
        frequencies: List of frequency values in Hz
        amplitudes: List of amplitude values in dB
        output_path: Output CSV file path
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("freq_Hz,amp_dB\n")
        for freq, amp in zip(frequencies, amplitudes):
            f.write(f"{freq:.6f},{amp}\n")


def save_timeseries(timestamps: list[float], amplitudes: list[float], 
                    output_path: str) -> None:
    """
    Save time-series monitoring data to CSV file.
    
    Args:
        timestamps: List of time points in seconds
        amplitudes: List of amplitude values in dB
        output_path: Output CSV file path
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("time_s,amp_dB\n")
        for t, amp in zip(timestamps, amplitudes):
            f.write(f"{t:.3f},{amp}\n")


def get_plot_path(csv_path: str) -> str:
    """
    Determine plot save location based on environment or CSV path.
    
    Args:
        csv_path: CSV file path
    
    Returns:
        Plot file path (.png)
    """
    base_name = os.path.basename(csv_path).rsplit('.', 1)[0] + '_plot.png'
    
    # Check if GUI specified separate plots directory
    plots_dir = os.environ.get('PLOTS_DIR')
    if plots_dir:
        return os.path.join(plots_dir, base_name)
    else:
        # Save plot alongside CSV
        return csv_path.rsplit('.', 1)[0] + '_plot.png'


def plot_frequency_sweep(frequencies: list[float], amplitudes: list[float], 
                         param: str, output_path: str) -> None:
    """
    Generate and save frequency sweep plot.
    
    Args:
        frequencies: List of frequency values in Hz
        amplitudes: List of amplitude values in dB
        param: S-parameter name for plot title
        output_path: Output PNG file path
    """
    plt.figure(figsize=(10, 6))
    
    # Convert Hz to GHz for readability
    freqs_ghz = [f / 1e9 for f in frequencies]
    
    plt.plot(freqs_ghz, amplitudes, linewidth=1.5)
    plt.xlabel("Frequency (GHz)")
    plt.ylabel("Amplitude (dB)")
    plt.title(f"{param} Frequency Response")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_timeseries(timestamps: list[float], amplitudes: list[float], 
                    param: str, output_path: str) -> None:
    """
    Generate and save time-series monitoring plot with fixed y-axis scaling.
    
    The y-axis is centered on the average amplitude ±2.5 dB to provide
    consistent scale for comparing multiple alignment attempts.
    
    Args:
        timestamps: List of time points in seconds
        amplitudes: List of amplitude values in dB
        param: S-parameter name for plot title
        output_path: Output PNG file path
    """
    # Calculate average for consistent y-axis scaling
    avg_amplitude = sum(amplitudes) / len(amplitudes) if amplitudes else 0
    
    plt.figure(figsize=(10, 6))
    plt.plot(timestamps, amplitudes, linewidth=1.5, marker='o', markersize=3)
    plt.xlabel("Time (seconds)")
    plt.ylabel("Amplitude (dB)")
    plt.title(f"{param} Signal Monitoring (Avg: {avg_amplitude:.2f} dB)")
    plt.grid(True, alpha=0.3)
    
    # Set fixed y-axis limits: average ± 2.5 dB
    plt.ylim(avg_amplitude - 2.5, avg_amplitude + 2.5)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    print(f"Average amplitude: {avg_amplitude:.2f} dB")
    print(f"Y-axis range: [{avg_amplitude-2.5:.2f}, {avg_amplitude+2.5:.2f}] dB")


# ============================================================================
# OPERATING MODES
# ============================================================================

def frequency_sweep_mode(inst: visa.Resource, args) -> None:
    """
    Single frequency sweep mode: measure amplitude across frequency range.
    
    This mode is used for characterizing antenna frequency response.
    
    Args:
        inst: PyVISA instrument object
        args: Command-line arguments
    """
    # Trigger sweep and retrieve data
    amplitudes = perform_sweep(inst)
    
    # Validate data length
    if len(amplitudes) != args.points:
        print(f"Warning: received {len(amplitudes)} points, expected {args.points}")
    
    # Generate frequency array
    step = (args.stop - args.start) / max(1, args.points - 1)
    frequencies = [args.start + i * step for i in range(len(amplitudes))]
    
    # Save data to CSV
    save_frequency_sweep(frequencies, amplitudes, args.out)
    print(f"Saved trace to {args.out}")
    
    # Generate plot if requested
    if args.plot:
        plot_path = get_plot_path(args.out)
        plot_frequency_sweep(frequencies, amplitudes, args.param, plot_path)
        print(f"Saved plot to {plot_path}")


def monitor_mode(inst: visa.Resource, args) -> None:
    """
    Time-series monitoring mode: repeatedly measure amplitude for antenna alignment.
    
    This mode tracks signal strength changes as the antenna is physically adjusted.
    The output shows whether alignment is improving or degrading in real-time.
    
    Args:
        inst: PyVISA instrument object
        args: Command-line arguments
    """
    print(f"Starting monitoring for {args.duration} seconds...")
    
    # Calculate frequency step
    step = (args.stop - args.start) / max(1, args.points - 1)
    
    # Determine which frequency point to monitor
    if args.monitor_freq is not None:
        # Find closest point to requested frequency
        monitor_idx = int((args.monitor_freq - args.start) / step)
        monitor_idx = max(0, min(monitor_idx, args.points - 1))
        actual_freq = args.start + monitor_idx * step
        print(f"Monitoring frequency: {actual_freq / 1e9:.4f} GHz (index {monitor_idx})")
    else:
        # Monitor maximum amplitude across entire sweep
        monitor_idx = None
        print("Monitoring maximum amplitude across sweep")
    
    # Data collection arrays
    timestamps = []
    amplitudes = []
    start_time = time.time()
    
    # Monitoring loop
    while (time.time() - start_time) < args.duration:
        # Perform sweep
        sweep_amps = perform_sweep(inst)
        
        # Extract amplitude value
        elapsed = time.time() - start_time
        if monitor_idx is not None:
            amp_value = sweep_amps[monitor_idx] if monitor_idx < len(sweep_amps) else sweep_amps[0]
        else:
            amp_value = max(sweep_amps)
        
        # Record data point
        timestamps.append(elapsed)
        amplitudes.append(amp_value)
        print(f"t={elapsed:.1f}s, amp={amp_value:.2f} dB")
        
        # Wait before next measurement
        time.sleep(args.interval)
    
    # Save time-series data
    save_timeseries(timestamps, amplitudes, args.out)
    print(f"Saved time-series data to {args.out}")
    
    # Generate plot if requested
    if args.plot:
        plot_path = get_plot_path(args.out)
        plot_timeseries(timestamps, amplitudes, args.param, plot_path)
        print(f"Saved plot to {plot_path}")


# ============================================================================
# MAIN PROGRAM
# ============================================================================

def main() -> None:
    """
    Parse arguments, connect to VNA, and execute requested measurement mode.
    """
    # Command-line argument parser
    ap = argparse.ArgumentParser(
        description="Control ZNLE6 VNA for frequency sweeps and signal monitoring"
    )
    
    # Connection parameters
    ap.add_argument("--ip", default="192.168.15.90", 
                    help="VNA IP address (default: 192.168.15.90)")
    ap.add_argument("--port", default=5025, type=int, 
                    help="SCPI port (default: 5025)")
    
    # Frequency range parameters
    ap.add_argument("--start", default=float(900e6), type=float, 
                    help="Start frequency in Hz (default: 900 MHz)")
    ap.add_argument("--stop", default=float(1500e6), type=float, 
                    help="Stop frequency in Hz (default: 1500 MHz)")
    ap.add_argument("--points", default=201, type=int, 
                    help="Number of sweep points (default: 201)")
    
    # Measurement parameters
    ap.add_argument("--param", default="S11", 
                    help="S-parameter to measure: S11, S21, S12, or S22 (default: S11)")
    ap.add_argument("--sweep-time", default=None, type=float, 
                    help="Sweep duration in seconds (optional)")
    
    # Output parameters
    ap.add_argument("--out", default="trace.csv", 
                    help="Output CSV file path (default: trace.csv)")
    ap.add_argument("--plot", action="store_true", 
                    help="Generate plot image")
    
    # Monitor mode parameters
    ap.add_argument("--monitor", action="store_true", 
                    help="Enable time-series monitoring mode")
    ap.add_argument("--monitor-freq", default=float(1e9), type=float, 
                    help="Frequency to monitor in Hz (default: 1 GHz)")
    ap.add_argument("--duration", default=60, type=float, 
                    help="Monitoring duration in seconds (default: 60)")
    ap.add_argument("--interval", default=1.0, type=float, 
                    help="Time between measurements in seconds (default: 1.0)")
    
    args = ap.parse_args()
    
    # Connect to VNA
    inst = connect_to_vna(args.ip, args.port)
    
    # Verify connection
    idn = inst.query("*IDN?")
    print(f"Connected: {idn}")
    
    # Configure VNA for measurement
    configure_vna(inst, args.start, args.stop, args.points, args.param, args.sweep_time)
    
    if args.sweep_time is not None:
        print(f"Set sweep time: {args.sweep_time} seconds")
    
    # Execute appropriate mode
    if args.monitor:
        monitor_mode(inst, args)
    else:
        frequency_sweep_mode(inst, args)
    
    # Close connection
    inst.close()


if __name__ == "__main__":
    main()
