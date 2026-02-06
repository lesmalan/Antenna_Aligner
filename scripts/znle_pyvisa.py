#!/usr/bin/env python3
"""
ZNLE6 Vector Network Analyzer (VNA) Control Script

This script communicates with the R&S ZNLE6 VNA over TCP/IP to:
- Perform frequency sweeps and save amplitude data to CSV
- Monitor signal strength over time for antenna alignment
- Generate plots for visual analysis

Hardware Setup:
  - ZNLE6 VNA connected via Ethernet (default: 192.168.15.90)
  - Signal source (NanoVNA H4) transmitting at test frequency
  - Receiver antenna (Pasco WA-9800A) connected to ZNLE6 port 1

Usage Examples:
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

# ==================================================================
# IMPORT DEPENDENCIES
# ==================================================================

# PyVISA: Library for controlling test instruments via SCPI commands
try:
    import pyvisa as visa
except ImportError:
    print("Error: pyvisa not installed. Run: pip install pyvisa pyvisa-py", file=sys.stderr)
    sys.exit(1)

# Matplotlib: Library for generating plots
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend (saves files without displaying windows)
    import matplotlib.pyplot as plt
except ImportError:
    print("Error: matplotlib not installed. Run: pip install matplotlib", file=sys.stderr)
    sys.exit(1)

def main() -> None:
    """Parse arguments, connect to VNA, and execute measurement."""
    
    # Command-line argument parser
    ap = argparse.ArgumentParser(
        description="Control ZNLE6 VNA for frequency sweeps and signal monitoring"
    )
    
    # Connection parameters
    ap.add_argument("--ip", default="192.168.15.90", 
                    help="VNA IP address (default: 192.168.15.90)")
    ap.add_argument("--port", default=5025, type=int, 
                    help="SCPI port (default: 5025)")
    
    # Frequency range parameters (used for both modes)
    ap.add_argument("--start", default=float(900e6), type=float, 
                    help="Start frequency in Hz (default: 900 MHz)")
    ap.add_argument("--stop", default=float(1500e6), type=float, 
                    help="Stop frequency in Hz (default: 1500 MHz)")
    ap.add_argument("--points", default=201, type=int, 
                    help="Number of sweep points (default: 201)")
    
    # Measurement parameters
    ap.add_argument("--param", default="S11", 
                    help="S-parameter: S11 (port 1 reflection), S21 (transmission), etc.")
    ap.add_argument("--sweep-time", default=None, type=float, 
                    help="Sweep duration in seconds (optional)")
    
    # Output parameters
    ap.add_argument("--out", default="trace.csv", 
                    help="Output CSV file path (default: trace.csv)")
    ap.add_argument("--plot", action="store_true", 
                    help="Generate plot image")
    
    # Monitor mode parameters (for antenna alignment)
    ap.add_argument("--monitor", action="store_true", 
                    help="Enable time-series monitoring mode")
    ap.add_argument("--monitor-freq", default=float(1e9), type=float, 
                    help="Frequency to monitor in Hz (default: 1 GHz)")
    ap.add_argument("--duration", default=60, type=float, 
                    help="Monitoring duration in seconds (default: 60)")
    ap.add_argument("--interval", default=1.0, type=float, 
                    help="Time between measurements in seconds (default: 1.0)")
    
    args = ap.parse_args()

    # ------------------------------------------------------------------
    # Connect to VNA via TCP/IP
    # ------------------------------------------------------------------
    rm = visa.ResourceManager("@py")  # Use pyvisa-py backend (pure Python, no NI-VISA needed)
    resource = f"TCPIP0::{args.ip}::{args.port}::SOCKET"  # Raw socket connection
    inst = rm.open_resource(resource)
    inst.timeout = 15000  # 15 second timeout for commands
    inst.write_termination = "\n"  # SCPI commands end with newline
    inst.read_termination = "\n"

    # Verify connection with identification query
    idn = inst.query("*IDN?")  # SCPI standard identification command
    print(f"Connected: {idn}")

    # ------------------------------------------------------------------
    # Configure VNA measurement parameters
    # ------------------------------------------------------------------
    # Set data format to ASCII (human-readable text instead of binary)
    inst.write("FORM:DATA ASCii")
    
    # Configure to read from port 1 (receiver antenna input)
    inst.write("CALC:PAR:PORT 1")
    
    # Define and select measurement trace with specified S-parameter
    inst.write(f"CALC:PAR:DEF 'Trc1',{args.param}")
    inst.write("CALC:PAR:SEL 'Trc1'")
    
    # Set frequency range
    inst.write(f"SENS:FREQ:STAR {args.start}")
    inst.write(f"SENS:FREQ:STOP {args.stop}")
    inst.write(f"SENSe:SWEep:POINts {args.points}")
    
    # Optional: Set custom sweep time
    if args.sweep_time is not None:
        inst.write(f"SENSe:SWEep:TIME {args.sweep_time}")
        print(f"Set sweep time: {args.sweep_time} seconds")
    
    # Set amplitude format to logarithmic magnitude (dB)
    inst.write("CALC:FORM MLOG")
    
    # Disable continuous sweeping (we'll trigger manually)
    inst.write("INIT:CONT OFF")

    # ==================================================================
    # MONITOR MODE: Track signal strength over time for antenna alignment
    # ==================================================================
    if args.monitor:
        print(f"Starting monitoring for {args.duration} seconds...")
        
        # Initialize data collection arrays
        timestamps = []  # Time points in seconds
        amplitudes = []  # Signal strength in dB
        start_time = time.time()
        
        # Calculate frequency step between points
        step = (args.stop - args.start) / max(1, args.points - 1)
        
        # Determine which frequency index to monitor
        # This allows tracking a specific frequency or the peak across the sweep
        if args.monitor_freq is not None:
            # Find closest sweep point to requested frequency
            monitor_idx = int((args.monitor_freq - args.start) / step)
            monitor_idx = max(0, min(monitor_idx, args.points - 1))  # Clamp to valid range
            actual_freq = args.start + monitor_idx * step
            print(f"Monitoring frequency: {actual_freq / 1e9:.4f} GHz (point {monitor_idx}/{args.points})")
        else:
            # Monitor maximum amplitude across entire sweep
            monitor_idx = None
            print("Monitoring maximum amplitude across sweep")
        
        # Monitoring loop: Repeatedly measure and record amplitude
        while (time.time() - start_time) < args.duration:
            # Trigger a frequency sweep
            inst.write("INIT")
            inst.query("*OPC?")  # Wait for sweep to complete
            
            # Retrieve amplitude data
            data_str = inst.query("CALC:DATA? FDATA")
            amps = [float(x) for x in data_str.strip().split(",") if x.strip()]
            
            # Calculate elapsed time
            elapsed = time.time() - start_time
            
            # Extract the amplitude value we're monitoring
            if monitor_idx is not None:
                # Specific frequency point
                amp_value = amps[monitor_idx] if monitor_idx < len(amps) else amps[0]
            else:
                # Maximum across sweep
                amp_value = max(amps)
            
            # Record data point
            timestamps.append(elapsed)
            amplitudes.append(amp_value)
            print(f"t={elapsed:.1f}s, amp={amp_value:.2f} dB")
            
            # Wait before next measurement
            time.sleep(args.interval)
        
        # ------------------------------------------------------------------
        # Save time-series data to CSV
        # ------------------------------------------------------------------
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("time_s,amp_dB\n")
            for t, amp in zip(timestamps, amplitudes):
                f.write(f"{t:.3f},{amp}\n")
        print(f"Saved time-series data to {args.out}")
        
        # ------------------------------------------------------------------
        # Generate time-series plot
        # ------------------------------------------------------------------
        if args.plot:
            plot_filename = get_plot_path(args.out)
            
            # Calculate average for consistent y-axis scaling
            # Fixed scaling allows direct comparison between multiple alignment attempts
            avg_amplitude = sum(amplitudes) / len(amplitudes) if amplitudes else 0
            
            # Create time-series plot
            plt.figure(figsize=(10, 6))
            plt.plot(timestamps, amplitudes, linewidth=1.5, marker='o', markersize=3)
            plt.xlabel("Time (seconds)")
            plt.ylabel("Amplitude (dB)")
            plt.title(f"{args.param} Signal Monitoring (Avg: {avg_amplitude:.2f} dB)")
            plt.grid(True, alpha=0.3)
            
            # Set fixed y-axis limits: average ± 2.5 dB
            # This prevents auto-scaling from hiding small signal variations
            plt.ylim(avg_amplitude - 2.5, avg_amplitude + 2.5)
            
            plt.tight_layout()
            plt.savefig(plot_filename, dpi=150)
            plt.close()  # Free memory
            print(f"Saved plot to {plot_filename}")
            print(f"Average amplitude: {avg_amplitude:.2f} dB")
            print(f"Y-axis range: [{avg_amplitude-2.5:.2f}, {avg_amplitude+2.5:.2f}] dB")
    # ==================================================================
    # FREQUENCY SWEEP MODE: Measure amplitude across frequency range
    # ==================================================================
    else:
        # Trigger a single frequency sweep
        inst.write("INIT")
        inst.query("*OPC?")  # Wait for operation complete
        
        # Retrieve formatted amplitude data
        data_str = inst.query("CALC:DATA? FDATA")
        amps = [float(x) for x in data_str.strip().split(",") if x.strip()]

        # Validate data length
        if len(amps) != args.points:
            print(f"Warning: received {len(amps)} points, expected {args.points}")

        # Generate corresponding frequency array
        step = (args.stop - args.start) / max(1, args.points - 1)
        freqs = [args.start + i * step for i in range(len(amps))]

        # ------------------------------------------------------------------
        # Save frequency sweep data to CSV
        # ------------------------------------------------------------------
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("freq_Hz,amp_dB\n")
            for freq, amp in zip(freqs, amps):
                f.write(f"{freq:.6f},{amp}\n")
        print(f"Saved trace to {args.out}")

        # ------------------------------------------------------------------
        # Generate frequency response plot
        # ------------------------------------------------------------------
        if args.plot:
            plot_filename = get_plot_path(args.out)
            
            # Create frequency sweep plot
            plt.figure(figsize=(10, 6))
            # Convert Hz to GHz for readability
            plt.plot([f / 1e9 for f in freqs], amps, linewidth=1.5)
            plt.xlabel("Frequency (GHz)")
            plt.ylabel("Amplitude (dB)")
            plt.title(f"{args.param} Frequency Response")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(plot_filename, dpi=150)
            plt.close()  # Free memory
            print(f"Saved plot to {plot_filename}")


if __name__ == "__main__":
    main()
