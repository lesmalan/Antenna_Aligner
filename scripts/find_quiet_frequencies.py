#!/usr/bin/env python3
"""
Scan for quiet frequency bands using ZNLE6 VNA + Pasco WA-9800A receiver.
This script measures background RF noise levels across a frequency range
and identifies the quietest bands for your signal transmission.

Usage:
  python3 find_quiet_frequencies.py --ip 192.168.15.90 --center 900e6 --span 200e6
  python3 find_quiet_frequencies.py --start 800e6 --stop 1000e6 --points 401
"""
from __future__ import annotations
import argparse
import sys
import time
import numpy as np
from datetime import datetime

try:
    import pyvisa as visa
except Exception:
    print("Error: pyvisa not installed. Run: pip install pyvisa pyvisa-py", file=sys.stderr)
    sys.exit(1)

try:
    import matplotlib
    matplotlib.use('TkAgg')  # Interactive backend
    import matplotlib.pyplot as plt
except Exception:
    print("Error: matplotlib not installed. Run: pip install matplotlib", file=sys.stderr)
    sys.exit(1)


def hz_to_str(freq_hz: float) -> str:
    """Convert Hz to readable string (MHz or GHz)."""
    if freq_hz >= 1e9:
        return f"{freq_hz/1e9:.3f} GHz"
    else:
        return f"{freq_hz/1e6:.1f} MHz"


def find_quiet_bands(freqs: np.ndarray, power_dbm: np.ndarray, threshold_db: float = 5.0, min_bandwidth_mhz: float = 10.0):
    """
    Identify frequency bands where power is below a threshold.
    
    Args:
        freqs: Frequency array in Hz
        power_dbm: Power measurements in dBm
        threshold_db: dB below the median to consider 'quiet'
        min_bandwidth_mhz: Minimum bandwidth for a quiet band in MHz
    
    Returns:
        List of tuples (start_freq, stop_freq, avg_power)
    """
    median_power = np.median(power_dbm)
    threshold_power = median_power - threshold_db
    
    quiet_mask = power_dbm < threshold_power
    
    # Find contiguous quiet regions
    quiet_bands = []
    in_band = False
    band_start = 0
    
    for i, is_quiet in enumerate(quiet_mask):
        if is_quiet and not in_band:
            # Start of a quiet band
            band_start = i
            in_band = True
        elif not is_quiet and in_band:
            # End of a quiet band
            band_freqs = freqs[band_start:i]
            band_power = power_dbm[band_start:i]
            bandwidth_mhz = (band_freqs[-1] - band_freqs[0]) / 1e6
            
            if bandwidth_mhz >= min_bandwidth_mhz:
                quiet_bands.append((
                    band_freqs[0],
                    band_freqs[-1],
                    np.mean(band_power),
                    bandwidth_mhz
                ))
            in_band = False
    
    # Handle case where band extends to the end
    if in_band and len(freqs) > band_start:
        band_freqs = freqs[band_start:]
        band_power = power_dbm[band_start:]
        bandwidth_mhz = (band_freqs[-1] - band_freqs[0]) / 1e6
        
        if bandwidth_mhz >= min_bandwidth_mhz:
            quiet_bands.append((
                band_freqs[0],
                band_freqs[-1],
                np.mean(band_power),
                bandwidth_mhz
            ))
    
    return quiet_bands


def main():
    ap = argparse.ArgumentParser(description="Scan for quiet frequency bands using ZNLE6")
    ap.add_argument("--ip", default="192.168.15.90", help="ZNLE6 IP address")
    ap.add_argument("--port", default=5025, type=int, help="SCPI port (default: 5025)")
    ap.add_argument("--center", type=float, help="Center frequency in Hz (e.g., 900e6)")
    ap.add_argument("--span", type=float, help="Frequency span in Hz (e.g., 200e6)")
    ap.add_argument("--start", type=float, help="Start frequency in Hz (alternative to center/span)")
    ap.add_argument("--stop", type=float, help="Stop frequency in Hz (alternative to center/span)")
    ap.add_argument("--points", default=401, type=int, help="Number of sweep points (default: 401)")
    ap.add_argument("--threshold-db", default=5.0, type=float, help="dB below median to consider quiet (default: 5)")
    ap.add_argument("--min-bandwidth", default=10.0, type=float, help="Minimum bandwidth in MHz for quiet band (default: 10)")
    ap.add_argument("--save-csv", action="store_true", help="Save scan results to CSV")
    ap.add_argument("--receiver-port", default=1, type=int, help="VNA receiver port (1 or 2, default: 1)")
    args = ap.parse_args()
    
    # Determine frequency range
    if args.center and args.span:
        start_freq = args.center - args.span / 2
        stop_freq = args.center + args.span / 2
    elif args.start and args.stop:
        start_freq = args.start
        stop_freq = args.stop
    else:
        # Default: 800-1000 MHz
        start_freq = 800e6
        stop_freq = 1000e6
        print(f"Using default range: {hz_to_str(start_freq)} to {hz_to_str(stop_freq)}")
    
    print(f"\n{'='*60}")
    print(f"ZNLE6 Quiet Frequency Band Scanner")
    print(f"{'='*60}")
    print(f"Instrument: {args.ip}:{args.port}")
    print(f"Frequency range: {hz_to_str(start_freq)} to {hz_to_str(stop_freq)}")
    print(f"Sweep points: {args.points}")
    print(f"Receiver port: {args.receiver_port}")
    print(f"{'='*60}\n")
    
    # Connect to ZNLE6
    print("Connecting to ZNLE6...")
    rm = visa.ResourceManager("@py")
    resource = f"TCPIP0::{args.ip}::{args.port}::SOCKET"
    
    try:
        inst = rm.open_resource(resource)
        inst.timeout = 20000  # 20 second timeout
        inst.write_termination = "\n"
        inst.read_termination = "\n"
        
        idn = inst.query("*IDN?")
        print(f"Connected: {idn.strip()}\n")
        
        # Configure for power measurement (S11 or S21 depending on setup)
        print("Configuring VNA for spectrum scan...")
        inst.write("FORM:DATA ASCii")
        inst.write(f"CALC:PAR:PORT {args.receiver_port}")
        inst.write(f"CALC:PAR:DEF 'Trc1',S{args.receiver_port}{args.receiver_port}")  # S11 or S22
        inst.write("CALC:PAR:SEL 'Trc1'")
        inst.write(f"SENS:FREQ:STAR {start_freq}")
        inst.write(f"SENS:FREQ:STOP {stop_freq}")
        inst.write(f"SENS:SWEep:POINts {args.points}")
        inst.write("CALC:FORM MLOG")  # Log magnitude (dB)
        inst.write("INIT:CONT OFF")
        
        # Perform sweep
        print("Performing frequency sweep...")
        inst.write("INIT")
        inst.query("*OPC?")  # Wait for operation complete
        
        # Retrieve data
        print("Retrieving data...")
        data_str = inst.query("CALC:DATA? FDATA")
        power_dbm = np.array([float(x) for x in data_str.strip().split(",") if x.strip()])
        
        # Generate frequency array
        freqs = np.linspace(start_freq, stop_freq, args.points)
        
        # Ensure data length matches
        if len(power_dbm) != len(freqs):
            print(f"Warning: Data length mismatch. Expected {len(freqs)}, got {len(power_dbm)}")
            min_len = min(len(freqs), len(power_dbm))
            freqs = freqs[:min_len]
            power_dbm = power_dbm[:min_len]
        
        inst.close()
        
        # Analysis
        print(f"\n{'='*60}")
        print("NOISE FLOOR ANALYSIS")
        print(f"{'='*60}")
        print(f"Mean power: {np.mean(power_dbm):.2f} dBm")
        print(f"Median power: {np.median(power_dbm):.2f} dBm")
        print(f"Min power: {np.min(power_dbm):.2f} dBm at {hz_to_str(freqs[np.argmin(power_dbm)])}")
        print(f"Max power: {np.max(power_dbm):.2f} dBm at {hz_to_str(freqs[np.argmax(power_dbm)])}")
        print(f"Std deviation: {np.std(power_dbm):.2f} dB")
        
        # Find quiet bands
        quiet_bands = find_quiet_bands(freqs, power_dbm, args.threshold_db, args.min_bandwidth)
        
        if quiet_bands:
            print(f"\n{'='*60}")
            print(f"QUIET FREQUENCY BANDS ({len(quiet_bands)} found)")
            print(f"{'='*60}")
            for i, (f_start, f_stop, avg_pwr, bw) in enumerate(quiet_bands, 1):
                center = (f_start + f_stop) / 2
                print(f"\nBand {i}:")
                print(f"  Range: {hz_to_str(f_start)} - {hz_to_str(f_stop)}")
                print(f"  Center: {hz_to_str(center)}")
                print(f"  Bandwidth: {bw:.1f} MHz")
                print(f"  Avg power: {avg_pwr:.2f} dBm")
        else:
            print(f"\nNo quiet bands found with current criteria.")
            print(f"Try reducing --threshold-db or --min-bandwidth")
        
        # Save CSV if requested
        if args.save_csv:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = f"noise_scan_{timestamp}.csv"
            with open(csv_path, 'w') as f:
                f.write("Frequency_Hz,Frequency_MHz,Power_dBm\n")
                for freq, pwr in zip(freqs, power_dbm):
                    f.write(f"{freq},{freq/1e6},{pwr}\n")
            print(f"\nData saved to: {csv_path}")
        
        # Plot results
        print("\nGenerating plot...")
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.plot(freqs / 1e6, power_dbm, linewidth=1, label='Measured Power')
        ax.axhline(np.median(power_dbm), color='orange', linestyle='--', 
                   linewidth=1.5, label=f'Median: {np.median(power_dbm):.1f} dBm')
        ax.axhline(np.median(power_dbm) - args.threshold_db, color='green', 
                   linestyle=':', linewidth=1.5, 
                   label=f'Quiet Threshold: {np.median(power_dbm) - args.threshold_db:.1f} dBm')
        
        # Highlight quiet bands
        for f_start, f_stop, _, _ in quiet_bands:
            ax.axvspan(f_start / 1e6, f_stop / 1e6, alpha=0.2, color='green')
        
        ax.set_xlabel('Frequency (MHz)', fontsize=12)
        ax.set_ylabel('Power (dBm)', fontsize=12)
        ax.set_title('RF Noise Floor Scan - Quiet Band Detection', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        plt.tight_layout()
        
        # Save plot
        plot_path = f"noise_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(plot_path, dpi=150)
        print(f"Plot saved to: {plot_path}")
        
        plt.show()
        
        print(f"\n{'='*60}")
        print("RECOMMENDATION:")
        if quiet_bands:
            best_band = max(quiet_bands, key=lambda x: x[3])  # Largest bandwidth
            center = (best_band[0] + best_band[1]) / 2
            print(f"Use {hz_to_str(center)} for your transmission")
            print(f"This frequency has {best_band[3]:.1f} MHz of quiet bandwidth")
            print(f"and {best_band[2]:.1f} dBm average noise floor")
        else:
            print("Consider using the frequency with minimum power:")
            print(f"{hz_to_str(freqs[np.argmin(power_dbm)])}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
