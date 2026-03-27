#!/usr/bin/env python3
"""
Real-Time ZNLE6 Signal Monitor with Motor Controls

This script continuously measures signal amplitude at a target frequency and
displays results in a live-updating matplotlib plot. Designed for antenna
alignment and signal tracking applications WITH MOTOR CONTROL INTEGRATION.

Usage:
  python3 znle_realtime_monitor_motor_controls.py --ip 192.168.15.90 --freq 977e6 --param S21
  
Features:
  - Continuous real-time measurements at specified frequency
  - Live-updating amplitude vs time plot
  - Configurable S-parameter (S11, S12, S21, S22)
  - CSV data logging with timestamps
  - Graceful shutdown on Ctrl+C or window close
  - [TODO] Motor control integration for automated antenna positioning
  - [TODO] Angle tracking and correlation with signal strength
"""
import argparse
import os
import sys
import time
from datetime import datetime
from collections import deque

STEPS_PER_REV = 200
DEGREES_PER_STEP = 360.0 / STEPS_PER_REV

# NumPy for data handling
try:
    import numpy as np
except ImportError:
    print("Error: numpy not installed. Run: pip install numpy", file=sys.stderr)
    sys.exit(1)

# PyVISA for instrument control
try:
    import pyvisa as visa
except ImportError:
    print("Error: pyvisa not installed. Run: pip install pyvisa pyvisa-py", file=sys.stderr)
    sys.exit(1)

# Matplotlib for live plotting
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
except ImportError:
    print("Error: matplotlib not installed. Run: pip install matplotlib", file=sys.stderr)
    sys.exit(1)

# Shared temp file path for reading motor position from GUI
MOTOR_POS_FILE = '/tmp/antenna_aligner_motor_pos.txt'


# =============================================================================
# TODO: Motor Control Integration
# =============================================================================
# Future additions:
# - Import motor controller module
# - Add motor position tracking
# - Add motor control commands (rotate, stop, home)
# - Correlate motor angle with signal amplitude
# - Add automated scanning capabilities
# =============================================================================


class RealtimeMonitorWithMotor:
    """Real-time VNA monitor with live plotting and motor control"""
    
    def __init__(self, ip, port, freq, param, csv_path, motor_port=None, max_points=1000, smoothing_window=10):
        self.ip = ip
        self.port = port
        self.target_freq = freq
        self.param = param
        self.csv_path = csv_path
        self.motor_port = motor_port
        self.max_points = max_points
        self.smoothing_window = smoothing_window
        
        # Data storage (using deque for efficient FIFO)
        self.times = deque(maxlen=max_points)
        self.amplitudes = deque(maxlen=max_points)
        self.raw_amplitudes = deque(maxlen=max_points)  # Store raw data for smoothing
        self.start_time = time.time()
        self.running = True
        
        # Motor control attributes
        self.motor_connected = False
        self.current_az = 0
        self.current_el = 0
        
        # VNA connection
        self.inst = None
        self.connect_vna()
        
        # Motor connection
        if self.motor_port:
            self.connect_motor()
        
        # CSV file
        self.csv_file = None
        if csv_path:
            self.csv_file = open(csv_path, 'w')
            if self.motor_connected:
                self.csv_file.write("Timestamp,Elapsed_Time_s,Frequency_Hz,Amplitude_Raw_dB,Amplitude_Smoothed_dB,Azimuth_deg,Elevation_deg\n")
            else:
                self.csv_file.write("Timestamp,Elapsed_Time_s,Frequency_Hz,Amplitude_Raw_dB,Amplitude_Smoothed_dB\n")
            self.csv_file.flush()
        
        # Setup plot
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.line, = self.ax.plot([], [], 'b-', linewidth=1.5)
        self.ax.set_xlabel('Time (seconds)', fontsize=12)
        self.ax.set_ylabel('Amplitude (dB)', fontsize=12)
        smooth_text = f" (smoothed: {smoothing_window} samples)" if smoothing_window > 1 else ""
        self.ax.set_title(f'Real-Time Signal Monitor with Motor Control - {param} @ {freq/1e6:.1f} MHz{smooth_text}', 
                         fontsize=14, fontweight='bold')
        self.ax.grid(True, alpha=0.3)
        
        # Text annotation for current value
        self.value_text = self.ax.text(0.02, 0.98, '', transform=self.ax.transAxes,
                                       verticalalignment='top', fontsize=11,
                                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    def connect_vna(self):
        """Establish connection to VNA and configure measurement"""
        print(f"Connecting to ZNLE6 at {self.ip}:{self.port}...")
        rm = visa.ResourceManager("@py")
        resource = f"TCPIP0::{self.ip}::{self.port}::SOCKET"
        
        try:
            self.inst = rm.open_resource(resource)
            self.inst.timeout = 10000  # 10 second timeout
            self.inst.write_termination = "\n"
            self.inst.read_termination = "\n"
            
            # Verify connection
            idn = self.inst.query("*IDN?")
            print(f"Connected: {idn.strip()}\n")
            
            # Configure VNA
            print("Configuring VNA for real-time monitoring...")
            
            # Set data format to ASCII
            self.inst.write("FORM:DATA ASCii")
            
            # Disable averaging for fast measurements
            self.inst.write("SENS:AVER OFF")
            
            # Configure S-parameter
            self.inst.write(f"CALC:PAR:DEF 'Trc1',{self.param}")
            self.inst.write("CALC:PAR:SEL 'Trc1'")
            
            # Set single frequency point (CW mode)
            self.inst.write(f"SENS:FREQ:STAR {self.target_freq}")
            self.inst.write(f"SENS:FREQ:STOP {self.target_freq}")
            self.inst.write("SENS:SWEep:POINts 1")
            
            # Set format to log magnitude (dB)
            self.inst.write("CALC:FORM MLOG")
            
            # Disable continuous sweep (we'll trigger manually)
            self.inst.write("INIT:CONT OFF")
            
            print("VNA configured successfully!")
            print(f"Monitoring: {self.param} at {self.target_freq/1e6:.1f} MHz")
            print("Press Ctrl+C or close plot window to stop\n")
            
        except Exception as e:
            print(f"Error connecting to VNA: {e}", file=sys.stderr)
            sys.exit(1)
    
    def connect_motor(self):
        """Enable motor position tracking via shared temp file written by GUI."""
        print(f"Motor tracking enabled - position will be read from GUI in real-time...")
        # The GUI owns the serial port and writes current position to MOTOR_POS_FILE.
        # We just mark motor as connected so CSV includes the Az/El columns.
        self.motor_connected = True
        print(f"Motor position source: {MOTOR_POS_FILE}")
    
    def query_motor_position(self):
        """Read current motor position from shared position file written by GUI."""
        try:
            with open(MOTOR_POS_FILE, 'r') as f:
                content = f.read().strip()
            az_str, el_str = content.split(',')
            self.current_az = int(az_str)
            self.current_el = int(el_str)
        except Exception:
            pass  # Keep last known position if file missing or unreadable

    def steps_to_degrees(self, steps):
        """Convert motor steps to degrees for logs and display."""
        return steps * DEGREES_PER_STEP
    
    def measure_amplitude(self):
        """Perform single measurement and return amplitude"""
        try:
            # Trigger single sweep
            self.inst.write("INIT")
            self.inst.query("*OPC?")
            
            # Get data
            data_str = self.inst.query("CALC:DATA? FDATA")
            amplitude = float(data_str.strip())
            
            return amplitude
        except Exception as e:
            print(f"Measurement error: {e}", file=sys.stderr)
            return None
    
    def update_plot(self, frame):
        """Animation function called by FuncAnimation"""
        if not self.running:
            return self.line, self.value_text
        
        # Measure amplitude
        amplitude = self.measure_amplitude()
        
        if amplitude is not None:
            # Calculate elapsed time
            elapsed = time.time() - self.start_time
            
            # Store raw data
            self.times.append(elapsed)
            self.raw_amplitudes.append(amplitude)
            
            # Calculate smoothed amplitude (rolling average)
            if self.smoothing_window > 1 and len(self.raw_amplitudes) >= self.smoothing_window:
                # Average the last N samples
                recent_samples = list(self.raw_amplitudes)[-self.smoothing_window:]
                smoothed_amplitude = np.mean(recent_samples)
            else:
                # Not enough samples yet, use raw value
                smoothed_amplitude = amplitude
            
            self.amplitudes.append(smoothed_amplitude)
            
            # Query motor position if connected
            if self.motor_connected:
                self.query_motor_position()
            
            # Write raw data to CSV (preserve original measurements)
            if self.csv_file:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                if self.motor_connected:
                    az_deg = self.steps_to_degrees(self.current_az)
                    el_deg = self.steps_to_degrees(self.current_el)
                    self.csv_file.write(f"{timestamp},{elapsed:.3f},{self.target_freq},{amplitude:.3f},{smoothed_amplitude:.3f},{az_deg:.2f},{el_deg:.2f}\n")
                else:
                    self.csv_file.write(f"{timestamp},{elapsed:.3f},{self.target_freq},{amplitude:.3f},{smoothed_amplitude:.3f}\n")
                self.csv_file.flush()
            
            # Update plot data (using smoothed values)
            self.line.set_data(list(self.times), list(self.amplitudes))
            
            # Auto-scale axes
            if len(self.times) > 0:
                self.ax.set_xlim(0, max(self.times) * 1.1 + 1)
                
                if len(self.amplitudes) > 0:
                    amp_array = np.array(list(self.amplitudes))
                    amp_min = np.min(amp_array)
                    amp_max = np.max(amp_array)
                    amp_range = amp_max - amp_min
                    
                    # Add 15% margin on top and bottom, minimum 5 dB range
                    if amp_range < 5:
                        # If range is very small, use fixed margin
                        margin = 5
                    else:
                        # Use 15% of range as margin, minimum 2 dB
                        margin = max(2, amp_range * 0.15)
                    
                    y_min = amp_min - margin
                    y_max = amp_max + margin
                    self.ax.set_ylim(y_min, y_max)
            
            # Update value text
            smooth_info = f" (smoothed)" if self.smoothing_window > 1 else ""
            motor_info = ""
            if self.motor_connected:
                az_deg = self.steps_to_degrees(self.current_az)
                el_deg = self.steps_to_degrees(self.current_el)
                motor_info = f"\nAz: {az_deg:.1f} deg El: {el_deg:.1f} deg"
            self.value_text.set_text(f'Current: {smoothed_amplitude:.2f} dB{smooth_info}\nRaw: {amplitude:.2f} dB\nTime: {elapsed:.1f} s\nPoints: {len(self.times)}{motor_info}')
            
            # Print to console every 10 measurements
            if len(self.times) % 10 == 0:
                smooth_info = f"  Smoothed={smoothed_amplitude:.2f} dB" if self.smoothing_window > 1 else ""
                motor_info = ""
                if self.motor_connected:
                    az_deg = self.steps_to_degrees(self.current_az)
                    el_deg = self.steps_to_degrees(self.current_el)
                    motor_info = f"  Az={az_deg:.1f} deg El={el_deg:.1f} deg"
                print(f"t={elapsed:.1f}s  Raw={amplitude:.2f} dB{smooth_info}{motor_info}  Points={len(self.times)}")
        
        return self.line, self.value_text
    
    def start(self, interval=500):
        """Start real-time monitoring with animation"""
        # Set up animation (interval in milliseconds)
        # Note: blit=False allows axis limits to update dynamically
        ani = FuncAnimation(self.fig, self.update_plot, interval=interval, 
                          blit=False, cache_frame_data=False)
        
        # Handle window close event
        self.fig.canvas.mpl_connect('close_event', self.on_close)
        
        try:
            plt.show()
        except KeyboardInterrupt:
            print("\nStopping monitor...")
        finally:
            self.cleanup()
    
    def on_close(self, event):
        """Handle plot window close"""
        self.running = False
        self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        self.running = False
        
        if self.inst:
            try:
                self.inst.close()
                print("VNA connection closed")
            except:
                pass
        
        if self.csv_file:
            try:
                self.csv_file.close()
                print(f"Data saved to: {self.csv_path}")
            except:
                pass


def main():
    """Parse arguments and start real-time monitor"""
    ap = argparse.ArgumentParser(
        description="Real-time ZNLE6 signal monitor with motor control integration",
        epilog="Example: %(prog)s --ip 192.168.15.90 --freq 977e6 --param S21"
    )
    
    # Connection parameters
    ap.add_argument("--ip", default="192.168.15.90",
                   help="ZNLE6 IP address (default: 192.168.15.90)")
    ap.add_argument("--port", default=5025, type=int,
                   help="SCPI port (default: 5025)")
    
    # Motor control arguments
    ap.add_argument("--motor-port", default=None,
                   help="Serial port for motor controller (e.g., /dev/ttyACM0)")
    
    # Measurement parameters
    ap.add_argument("--freq", type=float, required=True,
                   help="Target frequency in Hz (e.g., 977e6 for 977 MHz)")
    ap.add_argument("--param", default="S22", choices=["S11", "S12", "S21", "S22"],
                   help="S-parameter to measure (default: S22)")
    
    # Output parameters
    ap.add_argument("--csv-dir", default=".",
                   help="Directory for CSV file (default: current directory)")
    ap.add_argument("--filename", default="realtime_monitor_motor",
                   help="Base filename for CSV output (default: realtime_monitor_motor)")
    ap.add_argument("--interval", default=500, type=int,
                   help="Measurement interval in milliseconds (default: 500)")
    ap.add_argument("--max-points", default=1000, type=int,
                   help="Maximum data points to display (default: 1000)")
    ap.add_argument("--smoothing", default=10, type=int,
                   help="Smoothing window size (number of samples to average, default: 10)")
    
    args = ap.parse_args()
    
    # Generate timestamped CSV filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"{args.filename}_{timestamp}.csv"
    csv_path = os.path.join(args.csv_dir, csv_filename)
    os.makedirs(args.csv_dir, exist_ok=True)
    
    print("="*60)
    print("ZNLE6 Real-Time Signal Monitor with Motor Controls")
    print("="*60)
    print(f"Target Frequency: {args.freq/1e6:.1f} MHz")
    print(f"S-Parameter: {args.param}")
    print(f"Measurement Interval: {args.interval} ms")
    print(f"Smoothing Window: {args.smoothing} samples")
    print(f"CSV Output: {csv_path}")
    if args.motor_port:
        print(f"Motor Controller: {args.motor_port}")
    else:
        print("Motor Controller: Not connected")
    print("="*60)
    print()
    
    # Create and start monitor
    monitor = RealtimeMonitorWithMotor(
        ip=args.ip,
        port=args.port,
        freq=args.freq,
        param=args.param,
        csv_path=csv_path,
        motor_port=args.motor_port,
        max_points=args.max_points,
        smoothing_window=args.smoothing
    )
    
    monitor.start(interval=args.interval)


if __name__ == "__main__":
    main()
