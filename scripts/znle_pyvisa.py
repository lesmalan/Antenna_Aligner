#!/usr/bin/env python3
"""
R&S ZNLE6 control via PyVISA over TCP/IP.
Fetch formatted amplitude data (e.g., S21 in dB) and save CSV.

Usage:
  python3 znle_pyvisa.py --ip 192.168.15.90 --start 10e9 --stop 10.1e9 \
      --points 401 --param S21 --sweep-time 30 --out s21.csv

Requires:
  pip install pyvisa pyvisa-py
"""
from __future__ import annotations
import argparse
import math
import os
import sys
import time
from datetime import datetime

try:
    import pyvisa as visa
except Exception as exc:
    print("Error: pyvisa not installed. pip install pyvisa pyvisa-py", file=sys.stderr)
    raise

try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend for saving
    import matplotlib.pyplot as plt
except Exception as exc:
    print("Error: matplotlib not installed. pip install matplotlib", file=sys.stderr)
    raise


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip", default="192.168.15.90", help="Instrument IP")
    ap.add_argument("--port", default=5025, type=int, help="SCPI socket port (usually 5025)")
    ap.add_argument("--start", default=float(900e6), type=float, help="Start frequency (Hz)")
    ap.add_argument("--stop", default=float(1500e6), type=float, help="Stop frequency (Hz)")
    ap.add_argument("--points", default=201, type=int, help="Sweep points")
    ap.add_argument("--param", default="S11", help="Trace parameter (S11/S21/S12/S22)")
    ap.add_argument("--sweep-time", default=None, type=float, help="Sweep time in seconds (optional)")
    ap.add_argument("--out", default="../CSVs/trace.csv", help="Output CSV path")
    ap.add_argument("--plot", action="store_true", help="Display plot of amplitude vs frequency")
    ap.add_argument("--monitor", action="store_true", help="Monitor mode: plot amplitude vs time")
    ap.add_argument("--monitor-freq", default=float(1e9), type=float, help="Specific frequency to monitor (Hz), default: 1 GHz")
    ap.add_argument("--duration", default=60, type=float, help="Monitoring duration in seconds (default: 60)")
    ap.add_argument("--interval", default=1.0, type=float, help="Measurement interval in seconds (default: 1.0)")
    args = ap.parse_args()

    # Create output directories if they don't exist
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    csv_dir = os.path.join(base_dir, "CSVs")
    plots_dir = os.path.join(base_dir, "Plots")
    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(plots_dir, exist_ok=True)
    
    # Ensure output file is in CSVs directory if not an absolute path
    if not os.path.isabs(args.out):
        args.out = os.path.join(csv_dir, os.path.basename(args.out))

    rm = visa.ResourceManager("@py")  # use pyvisa-py backend
    # Raw socket resource string; alternatively: f"TCPIP::{args.ip}::INSTR"
    resource = f"TCPIP0::{args.ip}::{args.port}::SOCKET"
    inst = rm.open_resource(resource)
    inst.timeout = 15000
    inst.write_termination = "\n"
    inst.read_termination = "\n"

    # Basic sanity
    idn = inst.query("*IDN?")
    print(f"Connected: {idn}")

    # Configure measurement
    inst.write("FORM:DATA ASCii")
    inst.write("CALC:PAR:PORT 1")  # Set to port 1
    inst.write(f"CALC:PAR:DEF 'Trc1',{args.param}")
    inst.write("CALC:PAR:SEL 'Trc1'")
    inst.write(f"SENS:FREQ:STAR {args.start}")
    inst.write(f"SENS:FREQ:STOP {args.stop}")
    inst.write(f"SENSe:SWEep:POINts {args.points}")
    if args.sweep_time is not None:
        inst.write(f"SENSe:SWEep:TIME {args.sweep_time}")
        print(f"Set sweep time: {args.sweep_time} seconds")
    inst.write("CALC:FORM MLOG")  # log magnitude (dB)
    inst.write("INIT:CONT OFF")

    if args.monitor:
        # Time-series monitoring mode
        print(f"Starting monitoring for {args.duration} seconds...")
        timestamps = []
        amplitudes = []
        start_time = time.time()
        
        step = (args.stop - args.start) / (max(1, args.points - 1))
        
        # Determine which frequency index to monitor
        if args.monitor_freq is not None:
            monitor_idx = int((args.monitor_freq - args.start) / step)
            monitor_idx = max(0, min(monitor_idx, args.points - 1))
            print(f"Monitoring frequency: {args.start + monitor_idx * step / 1e9:.4f} GHz")
        else:
            monitor_idx = None
            print("Monitoring maximum amplitude across sweep")
        
        while (time.time() - start_time) < args.duration:
            inst.write("INIT")
            inst.query("*OPC?")
            data_str = inst.query("CALC:DATA? FDATA")
            amps = [float(x) for x in data_str.strip().split(",") if x.strip()]
            
            elapsed = time.time() - start_time
            
            if monitor_idx is not None:
                amp_value = amps[monitor_idx] if monitor_idx < len(amps) else amps[0]
            else:
                amp_value = max(amps)
            
            timestamps.append(elapsed)
            amplitudes.append(amp_value)
            print(f"t={elapsed:.1f}s, amp={amp_value:.2f} dB")
            
            time.sleep(args.interval)
        
        # Save time-series data
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("time_s,amp_dB\n")
            for t, amp in zip(timestamps, amplitudes):
                f.write(f"{t:.3f},{amp}\n")
        
        print(f"Saved time-series data to {args.out}")
        
        # Plot time-series
        if args.plot:
            plot_basename = os.path.basename(args.out).rsplit('.', 1)[0] + '_plot.png'
            # Use PLOTS_DIR from environment if set (from GUI), otherwise use plots_dir
            target_plots_dir = os.environ.get('PLOTS_DIR', plots_dir)
            plot_filename = os.path.join(target_plots_dir, plot_basename)
            
            # Calculate average amplitude for consistent y-axis scaling
            avg_amplitude = sum(amplitudes) / len(amplitudes) if amplitudes else 0
            
            plt.figure(figsize=(10, 6))
            plt.plot(timestamps, amplitudes, linewidth=1.5, marker='o', markersize=3)
            plt.xlabel("Time (seconds)")
            plt.ylabel("Amplitude (dB)")
            plt.title(f"{args.param} Amplitude vs Time (Avg: {avg_amplitude:.2f} dB)")
            
            # Set y-axis limits to average ± 5 dB for consistent comparison
            plt.ylim(avg_amplitude - 5, avg_amplitude + 5)
            
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(plot_filename, dpi=150)
            print(f"Saved plot to {plot_filename}")
            print(f"Average amplitude: {avg_amplitude:.2f} dB")
    else:
        # Single sweep mode (original behavior)
        inst.write("INIT")
        inst.query("*OPC?")  # wait for operation complete
        data_str = inst.query("CALC:DATA? FDATA")
        amps = [float(x) for x in data_str.strip().split(",") if x.strip()]

        if len(amps) != args.points:
            print(f"Warning: received {len(amps)} points, expected {args.points}")

        step = (args.stop - args.start) / (max(1, args.points - 1))

        # Generate frequency array
        freqs = [args.start + i * step for i in range(len(amps))]

        with open(args.out, "w", encoding="utf-8") as f:
            f.write("freq_Hz,amp_dB\n")
            for freq, amp in zip(freqs, amps):
                f.write(f"{freq:.6f},{amp}\n")

        print(f"Saved trace to {args.out}")

        # Plot if requested
        if args.plot:
            plot_basename = os.path.basename(args.out).rsplit('.', 1)[0] + '_plot.png'
            # Use PLOTS_DIR from environment if set (from GUI), otherwise use plots_dir
            target_plots_dir = os.environ.get('PLOTS_DIR', plots_dir)
            plot_filename = os.path.join(target_plots_dir, plot_basename)
            plt.figure(figsize=(10, 6))
            plt.plot([f / 1e9 for f in freqs], amps, linewidth=1.5)
            plt.xlabel("Frequency (GHz)")
            plt.ylabel("Amplitude (dB)")
            plt.title(f"{args.param} Trace")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(plot_filename, dpi=150)
            print(f"Saved plot to {plot_filename}")


if __name__ == "__main__":
    main()
