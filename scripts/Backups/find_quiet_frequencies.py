#!/usr/bin/env python3
"""
RF Noise Floor Scanner - Find Quiet Frequency Bands

This script measures background RF noise levels across a frequency range to
identify the quietest bands for signal transmission. It's designed to help you
find frequencies with minimal interference in your lab environment.

How it works:
1. Connects to ZNLE6 VNA via Pasco WA-9800A receiver (no transmitter needed)
2. Scans across specified frequency range measuring ambient RF power
3. Analyzes the noise floor to find bands below threshold
4. Generates visual plot highlighting quiet bands in green
5. Recommends best frequency for your NanoVNA transmission

Usage Examples:
  Center/Span:   python3 find_quiet_frequencies.py --center 900e6 --span 200e6
  Start/Stop:    python3 find_quiet_frequencies.py --start 800e6 --stop 1000e6 --points 401
  Save data:     python3 find_quiet_frequencies.py --center 900e6 --span 200e6 --save-csv

Dependencies:
  pip install pyvisa pyvisa-py matplotlib numpy
"""
from __future__ import annotations
import argparse
import os
import sys
import time
from datetime import datetime

# ==================================================================
# IMPORT DEPENDENCIES
# ==================================================================

# NumPy: Scientific computing library for statistical analysis
try:
    import numpy as np
except ImportError:
    print("Error: numpy not installed. Run: pip install numpy", file=sys.stderr)
    sys.exit(1)

# PyVISA: Instrument control library
try:
    import pyvisa as visa
except ImportError:
    print("Error: pyvisa not installed. Run: pip install pyvisa pyvisa-py", file=sys.stderr)
    sys.exit(1)

# Matplotlib: Plotting library
try:
    import matplotlib
    matplotlib.use('TkAgg')  # Interactive backend for plot display
    import matplotlib.pyplot as plt
except ImportError:
    print("Error: matplotlib not installed. Run: pip install matplotlib", file=sys.stderr)
    sys.exit(1)

# ==================================================================
# HELPER FUNCTIONS
# ==================================================================

def hz_to_str(freq_hz: float) -> str:
    """
    Convert frequency in Hz to human-readable string.
    
    Examples:
        977000000 Hz  -> "977.0 MHz"
        2400000000 Hz -> "2.400 GHz"
    
    Args:
        freq_hz: Frequency in Hertz
    
    Returns:
        Formatted string with appropriate unit (MHz or GHz)
    """
    if freq_hz >= 1e9:
        return f"{freq_hz/1e9:.3f} GHz"
    else:
        return f"{freq_hz/1e6:.1f} MHz"


def find_quiet_bands(freqs: np.ndarray, power_dbm: np.ndarray, threshold_db: float = 5.0, min_bandwidth_mhz: float = 10.0):
    """
    Identify contiguous frequency bands with low RF noise.
    
    Algorithm:
    1. Calculate median noise level across entire scan
    2. Define "quiet" as power below (median - threshold_db)
    3. Find contiguous regions meeting the quiet criteria
    4. Filter out narrow bands below minimum bandwidth
    
    Args:
        freqs: Frequency array in Hz
        power_dbm: Measured power levels in dBm at each frequency
        threshold_db: dB below median to consider "quiet" (default: 5)
        min_bandwidth_mhz: Minimum bandwidth for valid quiet band in MHz (default: 10)
    
    Returns:
        List of tuples: (start_freq_hz, stop_freq_hz, avg_power_dbm, bandwidth_mhz)
    """
    # Calculate baseline noise level (median is robust to outliers)
    median_power = np.median(power_dbm)
    threshold_power = median_power - threshold_db
    
    # Create boolean mask: True where power is below threshold (quiet)
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
    """Parse arguments, scan frequency range, and identify quiet bands."""
    
    # ===============================================================
    # COMMAND-LINE ARGUMENT PARSING
    # ===============================================================
    ap = argparse.ArgumentParser(
        description="Scan for quiet frequency bands using ZNLE6 VNA",
        epilog="Example: %(prog)s --center 900e6 --span 200e6 --save-csv"
    )
    
    # Connection parameters
    ap.add_argument("--ip", default="192.168.15.90", 
                    help="ZNLE6 IP address (default: 192.168.15.90)")
    ap.add_argument("--port", default=5025, type=int, 
                    help="SCPI port (default: 5025)")
    ap.add_argument("--receiver-port", default=1, type=int, 
                    help="VNA receiver port: 1 or 2 (default: 1)")
    ap.add_argument("--s-parameter", default="S22", type=str,
                    help="S-parameter to measure: S11, S12, S21, or S22 (default: S22)")
    
    # Frequency range (two input modes: center/span or start/stop)
    ap.add_argument("--center", type=float, 
                    help="Center frequency in Hz (e.g., 900e6 for 900 MHz)")
    ap.add_argument("--span", type=float, 
                    help="Frequency span in Hz (e.g., 200e6 for 200 MHz)")
    ap.add_argument("--start", type=float, 
                    help="Start frequency in Hz (alternative to center/span)")
    ap.add_argument("--stop", type=float, 
                    help="Stop frequency in Hz (alternative to center/span)")
    ap.add_argument("--points", default=401, type=int, 
                    help="Number of sweep points (default: 401)")
    
    # Analysis parameters
    ap.add_argument("--threshold-db", default=5.0, type=float, 
                    help="dB below median to consider quiet (default: 5)")
    ap.add_argument("--min-bandwidth", default=10.0, type=float, 
                    help="Minimum bandwidth in MHz for quiet band (default: 10)")
    
    # Output parameters
    ap.add_argument("--save-csv", action="store_true", 
                    help="Save scan results to CSV file")
    ap.add_argument("--csv-dir", default=".", 
                    help="Directory for CSV files (default: current directory)")
    ap.add_argument("--plots-dir", default=".", 
                    help="Directory for plot files (default: current directory)")
    ap.add_argument("--filename", default="noise_scan", 
                    help="Base filename for output files (default: noise_scan)")
    
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
    print(f"S-Parameter: {args.s_parameter}")
    print(f"{'='*60}\n")
    
    # ===============================================================
    # VNA CONNECTION AND CONFIGURATION
    # ===============================================================
    
    print("Connecting to ZNLE6...")
    rm = visa.ResourceManager("@py")
    resource = f"TCPIP0::{args.ip}::{args.port}::SOCKET"
    
    try:
        # Open TCP/IP socket connection to VNA
        inst = rm.open_resource(resource)
        inst.timeout = 60000  # 60 second timeout for slow sweeps with many points
        inst.write_termination = "\n"  # SCPI uses newline termination
        inst.read_termination = "\n"
        
        # Verify connection with instrument identification query
        print("Querying instrument identification...")
        idn = inst.query("*IDN?")
        print(f"Connected: {idn.strip()}\n")
        
        # ===============================================================
        # VNA MEASUREMENT SETUP
        # ===============================================================
        
        print("Configuring VNA for spectrum scan...")
        
        # Reset averaging to speed up measurement
        inst.write("SENS:AVER OFF")
        
        # Set data format to ASCII (comma-separated values)
        inst.write("FORM:DATA ASCii")
        
        # Configure measurement port and S-parameter
        # S11: Reflection from port 1
        # S12: Transmission from port 2 to port 1 (reverse transmission)
        # S21: Transmission from port 1 to port 2 (forward transmission)
        # S22: Reflection from port 2
        inst.write(f"CALC:PAR:PORT {args.receiver_port}")
        
        # Set the specified S-parameter
        inst.write(f"CALC:PAR:DEF 'Trc1',{args.s_parameter}")
        inst.write("CALC:PAR:SEL 'Trc1'")
        
        # Set frequency sweep range
        inst.write(f"SENS:FREQ:STAR {start_freq}")
        inst.write(f"SENS:FREQ:STOP {stop_freq}")
        inst.write(f"SENS:SWEep:POINts {args.points}")
        
        # Set format to log magnitude (dBm power measurement)
        inst.write("CALC:FORM MLOG")
        
        # Disable continuous sweep (we'll trigger single sweep)
        inst.write("INIT:CONT OFF")
        
        # ===============================================================
        # PERFORM FREQUENCY SWEEP
        # ===============================================================
        
        print(f"Performing frequency sweep ({args.points} points)...")
        print("This may take 30-60 seconds depending on VNA settings...")
        inst.write("INIT")  # Start single sweep
        print("Waiting for sweep to complete...")
        inst.query("*OPC?")  # Wait for operation complete
        print("Sweep complete!")
        
        # ===============================================================
        # RETRIEVE MEASUREMENT DATA
        # ===============================================================
        
        print("Retrieving data from VNA...")
        data_str = inst.query("CALC:DATA? FDATA")  # Get formatted data
        print(f"Retrieved {len(data_str)} characters of data")
        
        # Parse CSV string into numpy array of power values
        power_dbm = np.array([float(x) for x in data_str.strip().split(",") if x.strip()])
        
        # Generate frequency array matching sweep points
        freqs = np.linspace(start_freq, stop_freq, args.points)
        
        # Ensure data length matches
        if len(power_dbm) != len(freqs):
            print(f"Warning: Data length mismatch. Expected {len(freqs)}, got {len(power_dbm)}")
            min_len = min(len(freqs), len(power_dbm))
            freqs = freqs[:min_len]
            power_dbm = power_dbm[:min_len]
        
        inst.close()
        
        # ===============================================================
        # STATISTICAL ANALYSIS OF NOISE FLOOR
        # ===============================================================
        
        print(f"\n{'='*60}")
        print("NOISE FLOOR ANALYSIS")
        print(f"{'='*60}")
        print(f"Mean power: {np.mean(power_dbm):.2f} dBm")
        print(f"Median power: {np.median(power_dbm):.2f} dBm")
        print(f"Min power: {np.min(power_dbm):.2f} dBm at {hz_to_str(freqs[np.argmin(power_dbm)])}")
        print(f"Max power: {np.max(power_dbm):.2f} dBm at {hz_to_str(freqs[np.argmax(power_dbm)])}")
        print(f"Std deviation: {np.std(power_dbm):.2f} dB")
        
        # ===============================================================
        # IDENTIFY QUIET FREQUENCY BANDS
        # ===============================================================
        
        # Find contiguous bands below noise threshold
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
            csv_filename = f"{args.filename}_{timestamp}.csv"
            csv_path = os.path.join(args.csv_dir, csv_filename)
            os.makedirs(args.csv_dir, exist_ok=True)
            with open(csv_path, 'w') as f:
                f.write("Frequency_Hz,Frequency_MHz,Power_dBm\n")
                for freq, pwr in zip(freqs, power_dbm):
                    f.write(f"{freq},{freq/1e6},{pwr}\n")
            print(f"\nData saved to: {csv_path}")
        
        # ===============================================================
        # GENERATE VISUALIZATION PLOT
        # ===============================================================
        
        print("\nGenerating plot...")
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Find and mark the single quietest frequency
        quietest_idx = np.argmin(power_dbm)
        quietest_freq = freqs[quietest_idx]
        quietest_power = power_dbm[quietest_idx]
        
        # Plot measured power spectrum
        ax.plot(freqs / 1e6, power_dbm, linewidth=1, label='Measured Power')
        
        # Add reference lines: median and quiet threshold
        ax.axhline(np.median(power_dbm), color='orange', linestyle='--', 
                   linewidth=1.5, label=f'Median: {np.median(power_dbm):.1f} dBm')
        ax.axhline(np.median(power_dbm) - args.threshold_db, color='green', 
                   linestyle=':', linewidth=1.5, 
                   label=f'Quiet Threshold: {np.median(power_dbm) - args.threshold_db:.1f} dBm')
        
        # Mark the quietest frequency with a red star
        ax.plot(quietest_freq / 1e6, quietest_power, 'r*', markersize=15, 
                label=f'Quietest: {hz_to_str(quietest_freq)} @ {quietest_power:.1f} dBm', zorder=5)
        
        # Shade quiet bands in green
        for f_start, f_stop, _, _ in quiet_bands:
            ax.axvspan(f_start / 1e6, f_stop / 1e6, alpha=0.2, color='green')
        
        ax.set_xlabel('Frequency (MHz)', fontsize=12)
        ax.set_ylabel('Power (dBm)', fontsize=12)
        ax.set_title('RF Noise Floor Scan - Quiet Band Detection', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best')
        
        plt.tight_layout()
        
        # Save plot
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        plot_filename = f"{args.filename}_{timestamp}.png"
        plot_path = os.path.join(args.plots_dir, plot_filename)
        os.makedirs(args.plots_dir, exist_ok=True)
        plt.savefig(plot_path, dpi=150)
        plt.close()  # Close the plot to free memory
        print(f"Plot saved to: {plot_path}")
        
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
        
        # Automatically open the saved plot
        print("Opening plot...")
        try:
            import subprocess
            subprocess.Popen(['xdg-open', plot_path])
        except Exception as e:
            print(f"Could not automatically open plot: {e}")
            print(f"Please open manually: {plot_path}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
