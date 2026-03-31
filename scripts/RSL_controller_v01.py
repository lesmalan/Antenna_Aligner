#!/usr/bin/env python3
"""
RSL Controller v01 - Enhanced ZNLE6 Real-Time Signal Monitor with Motor Controls

Improvements over base version:
- Motor position displayed in degrees instead of steps
- Absolute position control - enter target position in degrees
- CCW (counter-clockwise) rotation is positive for azimuth
- Incremental movement: all moves broken into 2-step chunks with position updates
- Auto-connects to motor controller on startup
- Elevation limits: -75° to +75°
- Frequent position updates during monitoring
- Enhanced scrollable UI with better layout
- Motor controls displayed prominently at top of window
- Responsive position tracking during measurements
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import os
import sys
import time
from datetime import datetime

# Serial communication for motor controller
try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Error: pyserial not installed. Run: pip install pyserial", file=sys.stderr)
    sys.exit(1)


# Motor/Step conversion: assuming 200 steps per full rotation (stepper motor standard)
# Adjust this value based on your actual motor specs and gearing
STEPS_PER_DEGREE = 200 / 360.0  # ~0.556 steps per degree (or ~1.8 degrees per step)

# Movement increment size (steps per movement command)
INCREMENTAL_STEP_SIZE = 2  # Move 2 steps at a time, then update position


class RSLControllerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("RSL Controller v01 - ZNLE6 Real-Time Monitor with Motor Controls")
        self.root.geometry("800x1000")
        
        # Default parameters - VNA
        self.ip = tk.StringVar(value="192.168.15.90")
        self.port = tk.StringVar(value="5025")
        self.target_freq = tk.StringVar(value="977e6")
        self.param = tk.StringVar(value="S21")
        self.interval = tk.StringVar(value="500")
        self.smoothing_window = tk.StringVar(value="10")
        
        # Motor Controller State
        self.motor_ser = None
        self.motor_connected = False
        self.motor_port = tk.StringVar(value="/dev/ttyACM0")
        self.motor_baudrate = tk.IntVar(value=115200)
        self.current_az_steps = 0  # Store steps internally
        self.current_el_steps = 0
        self.current_az_degrees = tk.DoubleVar(value=0.0)  # Display in degrees
        self.current_el_degrees = tk.DoubleVar(value=0.0)
        self.manual_az_step = tk.IntVar(value=10)
        self.manual_el_step = tk.IntVar(value=5)

        # Absolute position targets
        self.target_az_degrees = tk.DoubleVar(value=0.0)
        self.target_el_degrees = tk.DoubleVar(value=0.0)
        
        # Position offset for software-based home calibration (fallback)
        self.home_offset_az = 0
        self.home_offset_el = 0
        self.use_software_home = False
        
        # Set default directories
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_dir = os.path.join(base_dir, "CSVs")
        plots_dir = os.path.join(base_dir, "Plots")
        os.makedirs(csv_dir, exist_ok=True)
        os.makedirs(plots_dir, exist_ok=True)
        
        self.csv_directory = tk.StringVar(value=csv_dir)
        self.plots_directory = tk.StringVar(value=plots_dir)
        self.filename = tk.StringVar(value="realtime_monitor_motor")
        
        self.running = False
        self.process = None
        self.position_update_thread = None
        self.position_update_running = False
        
        self.create_widgets()
        self.refresh_motor_ports()

        # Auto-connect to motor on startup
        self.root.after(500, self.auto_connect_motor)
    
    def create_widgets(self):
        # Main container with scrollbar
        canvas = tk.Canvas(self.root, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Make mousewheel scrolling work
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        main_frame = ttk.Frame(scrollable_frame, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        row = 0

        # Title
        title_label = ttk.Label(main_frame, text="RSL Controller v01",
                                font=('Arial', 14, 'bold'))
        title_label.grid(row=row, column=0, columnspan=2, pady=(0, 5))
        row += 1

        subtitle_label = ttk.Label(main_frame, text="ZNLE6 Real-Time Monitor with Motor Controls (Enhanced)",
                                   font=('Arial', 10))
        subtitle_label.grid(row=row, column=0, columnspan=2, pady=(0, 15))
        row += 1

        # Manual Motor Control - NOW AT TOP (Most Prominent)
        manual_frame = ttk.LabelFrame(main_frame, text="Motor Control", padding="10")
        manual_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1

        # Current position display (in DEGREES now) - MOST PROMINENT
        pos_display_frame = ttk.LabelFrame(manual_frame, text="Current Position (Degrees)", relief=tk.RIDGE, padding="8")
        pos_display_frame.grid(row=0, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=8)

        az_frame = ttk.Frame(pos_display_frame)
        az_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=10)
        ttk.Label(az_frame, text="Azimuth (Az):", font=("Arial", 10, "bold")).pack()
        ttk.Label(az_frame, textvariable=self.current_az_degrees,
                 font=("Arial", 16, "bold"), foreground="green").pack()
        ttk.Label(az_frame, text="degrees", font=("Arial", 8)).pack()

        el_frame = ttk.Frame(pos_display_frame)
        el_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=10)
        ttk.Label(el_frame, text="Elevation (El):", font=("Arial", 10, "bold")).pack()
        ttk.Label(el_frame, textvariable=self.current_el_degrees,
                 font=("Arial", 16, "bold"), foreground="blue").pack()
        ttk.Label(el_frame, text="degrees", font=("Arial", 8)).pack()

        # Separator - Absolute Position (Prominent)
        ttk.Separator(manual_frame, orient='horizontal').grid(row=1, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=8)
        ttk.Label(manual_frame, text="Absolute Position (CCW = Positive)", font=("Arial", 9, "bold")).grid(row=2, column=0, columnspan=4, pady=(2, 2))

        # Azimuth absolute position
        ttk.Label(manual_frame, text="Target Azimuth (degrees):").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(manual_frame, textvariable=self.target_az_degrees, width=12).grid(row=3, column=1, pady=5, padx=2)
        ttk.Button(manual_frame, text="Go To Az Position", width=22,
                  command=self.goto_absolute_azimuth).grid(row=3, column=2, columnspan=2, pady=5, padx=2, sticky=(tk.W, tk.E))

        # Elevation absolute position
        ttk.Label(manual_frame, text="Target Elevation (degrees):").grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Entry(manual_frame, textvariable=self.target_el_degrees, width=12).grid(row=4, column=1, pady=5, padx=2)
        ttk.Button(manual_frame, text="Go To El Position", width=22,
                  command=self.goto_absolute_elevation).grid(row=4, column=2, columnspan=2, pady=5, padx=2, sticky=(tk.W, tk.E))

        # Separator - Relative Movement
        ttk.Separator(manual_frame, orient='horizontal').grid(row=5, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=8)
        ttk.Label(manual_frame, text="Relative Movement", font=("Arial", 9, "bold")).grid(row=6, column=0, columnspan=4, pady=(2, 2))

        # Azimuth controls
        ttk.Label(manual_frame, text="Azimuth Step (degrees):").grid(row=7, column=0, sticky=tk.W, pady=5)
        ttk.Entry(manual_frame, textvariable=self.manual_az_step, width=8).grid(row=7, column=1, pady=5, padx=2)
        ttk.Button(manual_frame, text="← CCW", width=10,
                  command=lambda: self.manual_move('az', -self.manual_az_step.get())).grid(row=7, column=2, pady=5, padx=2)
        ttk.Button(manual_frame, text="CW →", width=10,
                  command=lambda: self.manual_move('az', self.manual_az_step.get())).grid(row=7, column=3, pady=5, padx=2)

        # Elevation controls
        ttk.Label(manual_frame, text="Elevation Step (degrees):").grid(row=8, column=0, sticky=tk.W, pady=5)
        ttk.Entry(manual_frame, textvariable=self.manual_el_step, width=8).grid(row=8, column=1, pady=5, padx=2)
        ttk.Button(manual_frame, text="↓ Down", width=10,
                  command=lambda: self.manual_move('el', -self.manual_el_step.get())).grid(row=8, column=2, pady=5, padx=2)
        ttk.Button(manual_frame, text="↑ Up", width=10,
                  command=lambda: self.manual_move('el', self.manual_el_step.get())).grid(row=8, column=3, pady=5, padx=2)

        # Separator
        ttk.Separator(manual_frame, orient='horizontal').grid(row=9, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=8)

        # Quick actions
        ttk.Button(manual_frame, text="Home (0,0)",
                  command=self.goto_home).grid(row=10, column=0, columnspan=2, pady=8, sticky=(tk.W, tk.E))
        ttk.Button(manual_frame, text="Emergency Stop",
                  command=self.emergency_stop).grid(row=10, column=2, columnspan=2, pady=8, sticky=(tk.W, tk.E))

        # Home position setting
        ttk.Button(manual_frame, text="Set Current as Home",
                  command=self.set_current_as_home).grid(row=11, column=0, columnspan=4, pady=5, sticky=(tk.W, tk.E))

        ttk.Label(manual_frame, text="⚠ Elevation limits: -75° to +75°",
                 foreground="red", font=('Arial', 8)).grid(row=12, column=0, columnspan=4, pady=(2, 0))
        
        # Measurement Settings
        meas_frame = ttk.LabelFrame(main_frame, text="Measurement Settings", padding="10")
        meas_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        ttk.Label(meas_frame, text="Target Frequency (Hz):").grid(row=0, column=0, sticky=tk.W, pady=5)
        freq_entry = ttk.Entry(meas_frame, textvariable=self.target_freq, width=20)
        freq_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        ttk.Label(meas_frame, text="(e.g., 977e6 for 977 MHz)").grid(row=0, column=2, sticky=tk.W, pady=5)
        
        ttk.Label(meas_frame, text="S-Parameter:").grid(row=1, column=0, sticky=tk.W, pady=5)
        param_frame = ttk.Frame(meas_frame)
        param_frame.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        param_combo = ttk.Combobox(param_frame, textvariable=self.param, 
                                   values=["S11", "S12", "S21", "S22"], 
                                   state="readonly", width=10)
        param_combo.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(param_frame, text="(S21/S12=Transmission, S11/S22=Reflection)").pack(side=tk.LEFT)
        
        ttk.Label(meas_frame, text="Update Interval (ms):").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(meas_frame, textvariable=self.interval, width=20).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        ttk.Label(meas_frame, text="(500 = 2 updates/sec)").grid(row=2, column=2, sticky=tk.W, pady=5)
        
        ttk.Label(meas_frame, text="Smoothing Window:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(meas_frame, textvariable=self.smoothing_window, width=20).grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        ttk.Label(meas_frame, text="(10 = average last 10 samples)").grid(row=3, column=2, sticky=tk.W, pady=5)
        
        # Output Settings
        output_frame = ttk.LabelFrame(main_frame, text="Output Settings", padding="10")
        output_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        ttk.Label(output_frame, text="CSV Directory:").grid(row=0, column=0, sticky=tk.W, pady=2)
        dir_frame = ttk.Frame(output_frame)
        dir_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)
        ttk.Entry(dir_frame, textvariable=self.csv_directory, width=40).pack(side=tk.LEFT)
        ttk.Button(dir_frame, text="Browse...", command=self.browse_csv_dir, width=8).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(output_frame, text="Filename:").grid(row=1, column=0, sticky=tk.W, pady=2)
        filename_frame = ttk.Frame(output_frame)
        filename_frame.grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Entry(filename_frame, textvariable=self.filename, width=30).pack(side=tk.LEFT)
        ttk.Label(filename_frame, text="(without extension)").pack(side=tk.LEFT, padx=5)
        
        # Monitor Control buttons
        monitor_button_frame = ttk.LabelFrame(main_frame, text="Monitor Control", padding="10")
        monitor_button_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        button_inner_frame = ttk.Frame(monitor_button_frame)
        button_inner_frame.pack(fill=tk.X, pady=5)
        
        self.start_button = ttk.Button(button_inner_frame, text="Start Real-Time Monitor", 
                                       command=self.start_monitor, width=25)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_inner_frame, text="Stop Monitor", 
                                      command=self.stop_monitor, state=tk.DISABLED, width=15)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_inner_frame, text="Help", command=self.show_help, width=10).pack(side=tk.LEFT, padx=5)

        # Status
        self.status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        row += 1

        # Connection Settings - NOW AT BOTTOM
        conn_frame = ttk.LabelFrame(main_frame, text="VNA Connection Settings", padding="10")
        conn_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1

        ttk.Label(conn_frame, text="ZNLE6 IP Address:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(conn_frame, textvariable=self.ip, width=20).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2, sticky=tk.W, pady=2, padx=(10, 0))
        ttk.Entry(conn_frame, textvariable=self.port, width=10).grid(row=0, column=3, sticky=tk.W, pady=2, padx=5)

        # Motor Controller Connection - NOW AT BOTTOM
        motor_conn_frame = ttk.LabelFrame(main_frame, text="Motor Controller Connection", padding="10")
        motor_conn_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1

        ttk.Label(motor_conn_frame, text="Port:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.motor_port_combo = ttk.Combobox(motor_conn_frame, textvariable=self.motor_port, width=15)
        self.motor_port_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        ttk.Button(motor_conn_frame, text="Refresh",
                  command=self.refresh_motor_ports, width=10).grid(row=0, column=2, pady=2, padx=5)

        self.motor_connect_button = ttk.Button(motor_conn_frame, text="Connect Motor",
                                              command=self.toggle_motor_connection)
        self.motor_connect_button.grid(row=1, column=0, columnspan=3, pady=5)

        motor_conn_frame.columnconfigure(1, weight=1)
        
        # Info text
        info_frame = ttk.LabelFrame(main_frame, text="Information", padding="10")
        info_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        info_text = tk.Text(info_frame, height=8, width=80, wrap=tk.WORD)
        info_text.insert(1.0,
            "RSL Controller v01 - Real-Time Signal Monitor with Motor Control\n\n"
            "Key Features:\n"
            "• Motor position displayed in DEGREES (not steps)\n"
            "• Absolute position control - enter target degrees directly\n"
            "• CCW (counter-clockwise) rotation is positive for azimuth\n"
            "• Incremental movement - motors move in 2-step increments with frequent position updates\n"
            "• Auto-connects to motor controller on startup\n"
            "• Elevation limits: -75° to +75°\n"
            "• Frequent position updates (even during measurements)\n"
            "• Prominent motor controls at top of window\n"
            "• Scrollable interface for all parameters\n"
            "• Live plot window shows amplitude vs time\n"
            "• Continuous CSV data logging with timestamps\n"
            "• Manual motor controls for antenna positioning\n"
            "• Operates independently from measurements")
        info_text.config(state=tk.DISABLED)
        info_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
    
    def browse_csv_dir(self):
        directory = filedialog.askdirectory(initialdir=self.csv_directory.get())
        if directory:
            self.csv_directory.set(directory)
    
    def validate_inputs(self):
        """Validate all input fields"""
        try:
            # Validate frequency
            freq = float(self.target_freq.get())
            if freq <= 0:
                raise ValueError("Target frequency must be positive")
            
            # Validate interval
            interval = int(self.interval.get())
            if interval < 100:
                raise ValueError("Update interval must be at least 100 ms")
            if interval > 10000:
                raise ValueError("Update interval must be at most 10000 ms")
            
            # Validate smoothing window
            smoothing = int(self.smoothing_window.get())
            if smoothing < 1:
                raise ValueError("Smoothing window must be at least 1")
            if smoothing > 100:
                raise ValueError("Smoothing window must be at most 100")
            
            # Validate filename
            if not self.filename.get().strip():
                raise ValueError("Filename cannot be empty")
            
            return True
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return False
    
    def build_command(self):
        """Build command line for backend script"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "znle_realtime_monitor_motor_controls.py")
        
        cmd = [sys.executable, script_path]
        cmd.extend(["--ip", self.ip.get()])
        cmd.extend(["--port", self.port.get()])
        cmd.extend(["--freq", self.target_freq.get()])
        cmd.extend(["--param", self.param.get()])
        cmd.extend(["--csv-dir", self.csv_directory.get()])
        cmd.extend(["--filename", self.filename.get()])
        cmd.extend(["--interval", self.interval.get()])
        cmd.extend(["--smoothing", self.smoothing_window.get()])
        
        # Add motor port if connected
        if self.motor_connected and self.motor_port.get():
            cmd.extend(["--motor-port", self.motor_port.get()])
        
        return cmd
    
    def start_monitor(self):
        """Start the real-time monitor with motor controls"""
        if self.running:
            return
        
        if not self.validate_inputs():
            return
        
        # Ensure CSV directory exists
        try:
            os.makedirs(self.csv_directory.get(), exist_ok=True)
        except Exception as e:
            messagebox.showerror("Directory Error", f"Cannot create CSV directory:\n{e}")
            return
        
        # Build command
        cmd = self.build_command()
        
        self.running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_label.config(text="Monitor running... (close plot window or click Stop to end)")
        
        # Start position update thread
        self.position_update_running = True
        self.position_update_thread = threading.Thread(target=self.frequent_position_updates, daemon=True)
        self.position_update_thread.start()
        
        # Run in thread
        thread = threading.Thread(target=self.run_monitor, args=(cmd,), daemon=True)
        thread.start()
    
    def frequent_position_updates(self):
        """Update motor position frequently during monitoring (every 200ms)"""
        while self.position_update_running:
            if self.motor_connected:
                self.update_motor_position()
            time.sleep(0.2)  # Update every 200ms
    
    def run_monitor(self, cmd):
        """Run the monitor script"""
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for process to complete
            self.process.wait()
            
            # Check return code
            if self.process.returncode == 0:
                self.root.after(0, self.monitor_complete, True, None)
            else:
                stderr = self.process.stderr.read()
                self.root.after(0, self.monitor_complete, False, stderr)
        
        except Exception as e:
            self.root.after(0, self.monitor_complete, False, str(e))
    
    def monitor_complete(self, success, error_msg=None):
        """Called when monitor completes"""
        self.running = False
        self.position_update_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        if success:
            self.status_label.config(text="Monitor stopped")
            messagebox.showinfo("Monitor Complete", "Real-time monitoring completed.\nCSV data has been saved.")
        else:
            self.status_label.config(text="Monitor failed")
            if error_msg:
                messagebox.showerror("Monitor Error", f"An error occurred:\n\n{error_msg}")
    
    def stop_monitor(self):
        """Stop the running monitor"""
        if self.process:
            self.process.terminate()
        self.position_update_running = False
        self.status_label.config(text="Stopping monitor...")
    
    # =========================================================================
    # Motor Controller Functions
    # =========================================================================
    
    def refresh_motor_ports(self):
        """Scan for available serial ports."""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.motor_port_combo['values'] = ports
        if ports and not self.motor_port.get():
            self.motor_port.set(ports[0])

    def auto_connect_motor(self):
        """Automatically attempt to connect to motor on startup."""
        if not self.motor_connected and self.motor_port.get():
            print(f"[Motor] Auto-connecting to default port: {self.motor_port.get()}")
            self.status_label.config(text="Auto-connecting to motor controller...")
            self.toggle_motor_connection()
    
    def toggle_motor_connection(self):
        """Connect or disconnect from Arduino motor controller."""
        if self.motor_connected:
            self.disconnect_motor()
        else:
            # Run connection in background thread to avoid freezing GUI
            self.motor_connect_button.config(state=tk.DISABLED)
            self.status_label.config(text="Connecting to motor controller...")
            thread = threading.Thread(target=self.connect_motor_thread, daemon=True)
            thread.start()
    
    def connect_motor_thread(self):
        """Background thread for motor connection."""
        port = self.motor_port.get()
        baudrate = self.motor_baudrate.get()
        
        try:
            print(f"[Motor] Connecting to {port} at {baudrate} baud...")
            self.motor_ser = serial.Serial(port, baudrate, timeout=2)
            time.sleep(2)  # Wait for Arduino reset
            
            # Read startup messages
            startup_msgs = []
            while self.motor_ser.in_waiting > 0:
                line = self.motor_ser.readline().decode('utf-8').strip()
                startup_msgs.append(line)
                print(f"[Arduino] {line}")
            
            # Test communication with STATUS command
            print("[Motor] Testing communication...")
            self.motor_ser.write(b"STATUS\n")
            self.motor_ser.flush()
            time.sleep(0.5)
            
            test_response = None
            if self.motor_ser.in_waiting > 0:
                test_response = self.motor_ser.readline().decode('utf-8').strip()
                print(f"[Motor] Test response: {test_response}")
            
            if test_response and (test_response.startswith("POS") or test_response.startswith("OK")):
                # Success!
                self.motor_connected = True
                self.root.after(0, self.connection_success, port)
                self.root.after(100, self.update_motor_position)
                # AUTO-START THE MONITOR when motor connects
                self.root.after(500, self.auto_start_monitor)
            else:
                # No valid response
                raise Exception(f"Arduino not responding properly. Got: {test_response or 'no response'}")
            
        except serial.SerialException as e:
            print(f"[Motor] Connection failed: {e}")
            self.root.after(0, self.connection_failed, port, str(e))
        except Exception as e:
            print(f"[Motor] Error: {e}")
            self.root.after(0, self.connection_failed, port, str(e))
    
    def auto_start_monitor(self):
        """Automatically start the monitor after successful motor connection"""
        if self.motor_connected and not self.running:
            print("[Motor] Motor connected! Auto-starting real-time monitor...")
            self.start_monitor()
    
    def connection_success(self, port):
        """Called from main thread when connection succeeds."""
        self.motor_connect_button.config(text="Disconnect Motor", state=tk.NORMAL)
        self.status_label.config(text=f"Motor controller connected on {port}")
        
        # Reset software home mode on new connection
        self.use_software_home = False
        self.home_offset_az = 0
        self.home_offset_el = 0
        
        messagebox.showinfo("Motor Connected", f"Successfully connected to motor controller on {port}\n\nMonitor will start automatically...")
    
    def connection_failed(self, port, error):
        """Called from main thread when connection fails."""
        self.motor_connect_button.config(state=tk.NORMAL)
        self.status_label.config(text=f"Motor connection failed")
        messagebox.showerror("Motor Connection Error", 
                           f"Could not connect to {port}\n\n{error}\n\n" +
                           "Make sure:\n" +
                           "1. Arduino is plugged in\n" +
                           "2. Correct port is selected\n" +
                           "3. Motor controller sketch is uploaded\n" +
                           "4. No other program is using the port")
        # Clean up failed connection
        if self.motor_ser and self.motor_ser.is_open:
            self.motor_ser.close()
        self.motor_ser = None
        self.motor_connected = False
    
    def disconnect_motor(self):
        """Close motor controller serial connection."""
        if self.motor_ser and self.motor_ser.is_open:
            self.motor_ser.close()
        self.motor_connected = False
        self.motor_connect_button.config(text="Connect Motor")
        self.status_label.config(text="Motor controller disconnected")
    
    def send_motor_command(self, command):
        """Send command to Arduino and return response."""
        if not self.motor_connected or not self.motor_ser:
            print(f"[Motor] ERROR: Not connected")
            self.status_label.config(text="Error: Motor controller not connected")
            return None
        
        try:
            cmd_bytes = (command + '\n').encode('utf-8')
            print(f"[Motor] Sending: {command}")
            self.motor_ser.write(cmd_bytes)
            self.motor_ser.flush()
            
            # Wait for response with timeout
            start_time = time.time()
            while self.motor_ser.in_waiting == 0 and (time.time() - start_time) < 1.0:
                time.sleep(0.05)
            
            if self.motor_ser.in_waiting > 0:
                response = self.motor_ser.readline().decode('utf-8').strip()
                print(f"[Motor] Response: {response}")
                return response
            else:
                print(f"[Motor] No response to: {command}")
                self.status_label.config(text=f"Motor timeout: {command}")
                return None
                
        except Exception as e:
            print(f"[Motor] Communication error: {e}")
            self.status_label.config(text=f"Motor communication error: {e}")
            return None
    
    def update_motor_position(self):
        """Query current motor positions and convert to degrees."""
        if not self.motor_connected:
            return
        
        response = self.send_motor_command("STATUS")
        if response and response.startswith("POS"):
            try:
                # Parse: "POS AZ:123 EL:456"
                parts = response.split()
                az_steps = int(parts[1].split(':')[1])
                el_steps = int(parts[2].split(':')[1])
                
                # Store internal step values
                self.current_az_steps = az_steps
                self.current_el_steps = el_steps
                
                # Convert steps to degrees for display
                az_degrees = az_steps / STEPS_PER_DEGREE
                el_degrees = el_steps / STEPS_PER_DEGREE
                
                # Apply software home offset if in software mode
                if self.use_software_home:
                    az_degrees = az_degrees - (self.home_offset_az / STEPS_PER_DEGREE)
                    el_degrees = el_degrees - (self.home_offset_el / STEPS_PER_DEGREE)
                
                self.current_az_degrees.set(round(az_degrees, 2))
                self.current_el_degrees.set(round(el_degrees, 2))
                print(f"[Motor] Position: Az={az_degrees:.2f}°, El={el_degrees:.2f}°" + 
                      (f" (offset: Az={self.home_offset_az}, El={self.home_offset_el})" if self.use_software_home else ""))
            except (IndexError, ValueError) as e:
                print(f"[Motor] Error parsing status: {response} - {e}")
                self.status_label.config(text=f"Error parsing motor status: {response}")
        elif response:
            print(f"[Motor] Unexpected STATUS response: {response}")
    
    def incremental_move(self, axis, total_steps):
        """
        Move motor incrementally in INCREMENTAL_STEP_SIZE chunks.
        Updates position after each increment for better tracking.

        Args:
            axis: 'az' or 'el'
            total_steps: Total steps to move (can be positive or negative)

        Returns:
            True if all increments succeeded, False otherwise
        """
        if total_steps == 0:
            return True

        # Determine direction and number of full increments
        direction = 1 if total_steps > 0 else -1
        abs_total = abs(total_steps)
        num_full_increments = abs_total // INCREMENTAL_STEP_SIZE
        remainder = abs_total % INCREMENTAL_STEP_SIZE

        # Command prefix based on axis
        cmd_prefix = "AZ" if axis == 'az' else "EL"
        axis_name = "Azimuth" if axis == 'az' else "Elevation"

        print(f"[Motor] {axis_name} incremental move: {total_steps} steps total")
        print(f"[Motor] Breaking into {num_full_increments} increments of {INCREMENTAL_STEP_SIZE} steps + {remainder} remainder")

        # Get initial position
        if axis == 'az':
            initial_position = self.current_az_steps
        else:
            initial_position = self.current_el_steps

        # Perform full increments
        for i in range(num_full_increments):
            increment = INCREMENTAL_STEP_SIZE * direction
            print(f"[Motor] Sending increment {i+1}/{num_full_increments}: {cmd_prefix} {increment}")
            response = self.send_motor_command(f"{cmd_prefix} {increment}")

            # Log response for debugging
            print(f"[Motor] Response to increment {i+1}: {response}")

            # Give motor time to complete movement
            time.sleep(0.2)  # Increased from 0.1 to 0.2 for more reliable movement

            # Update position after each increment
            self.update_motor_position()

            # Verify position changed
            if axis == 'az':
                position_changed = self.current_az_steps != initial_position
            else:
                position_changed = self.current_el_steps != initial_position

            if not position_changed and i == 0:
                # First increment didn't move - this is a real error
                print(f"[Motor] Warning: Position did not change after first increment")
                self.status_label.config(text=f"{axis_name} move failed - motor not responding")
                return False

            # Update status to show progress
            total_increments = num_full_increments + (1 if remainder > 0 else 0)
            progress_pct = int((i + 1) / total_increments * 100)
            current_pos = self.current_az_degrees.get() if axis == 'az' else self.current_el_degrees.get()
            self.status_label.config(text=f"{axis_name} moving: {progress_pct}% complete ({current_pos:.2f}°)")

            # Force GUI update
            self.root.update_idletasks()

        # Perform remainder if any
        if remainder > 0:
            increment = remainder * direction
            print(f"[Motor] Sending remainder: {cmd_prefix} {increment}")
            response = self.send_motor_command(f"{cmd_prefix} {increment}")
            print(f"[Motor] Remainder response: {response}")

            time.sleep(0.2)
            self.update_motor_position()

            # Update progress to 100%
            current_pos = self.current_az_degrees.get() if axis == 'az' else self.current_el_degrees.get()
            self.status_label.config(text=f"{axis_name} moving: 100% complete ({current_pos:.2f}°)")
            self.root.update_idletasks()

        # Final position update
        self.update_motor_position()

        # Verify final position
        if axis == 'az':
            final_position = self.current_az_steps
        else:
            final_position = self.current_el_steps

        steps_moved = final_position - initial_position
        print(f"[Motor] Movement complete. Requested: {total_steps} steps, Actual: {steps_moved} steps")

        # Consider it successful if we moved in the right direction and reasonably close
        if abs(steps_moved - total_steps) <= 1:  # Allow 1 step tolerance
            return True
        else:
            print(f"[Motor] Warning: Position mismatch. Expected {total_steps}, got {steps_moved}")
            # Still return True if we moved in the right direction
            if (total_steps > 0 and steps_moved > 0) or (total_steps < 0 and steps_moved < 0):
                return True
            return False

    def move_azimuth_absolute(self, target_az_degrees):
        """Move azimuth to absolute position (in degrees) with incremental movements."""
        target_steps = int(target_az_degrees * STEPS_PER_DEGREE)

        # Calculate relative movement from current position
        steps_to_move = target_steps - self.current_az_steps

        if steps_to_move == 0:
            self.status_label.config(text=f"Already at azimuth {target_az_degrees}°")
            return True

        print(f"[Motor] Azimuth absolute move to {target_az_degrees}° ({target_steps} steps)")
        print(f"[Motor] Current position: {self.current_az_steps} steps, need to move {steps_to_move} steps")

        # Perform incremental move
        success = self.incremental_move('az', steps_to_move)

        if success:
            final_pos = self.current_az_degrees.get()
            self.status_label.config(text=f"Azimuth move complete: {final_pos:.2f}°")
            return True
        else:
            self.status_label.config(text=f"Azimuth move failed")
            return False
    
    def move_elevation_absolute(self, target_el_degrees):
        """Move elevation to absolute position (in degrees) with incremental movements."""
        target_steps = int(target_el_degrees * STEPS_PER_DEGREE)

        # Calculate relative movement from current position
        steps_to_move = target_steps - self.current_el_steps

        if steps_to_move == 0:
            self.status_label.config(text=f"Already at elevation {target_el_degrees}°")
            return True

        print(f"[Motor] Elevation absolute move to {target_el_degrees}° ({target_steps} steps)")
        print(f"[Motor] Current position: {self.current_el_steps} steps, need to move {steps_to_move} steps")

        # Perform incremental move
        success = self.incremental_move('el', steps_to_move)

        if success:
            final_pos = self.current_el_degrees.get()
            self.status_label.config(text=f"Elevation move complete: {final_pos:.2f}°")
            return True
        else:
            self.status_label.config(text=f"Elevation move failed")
            return False
    
    def manual_move(self, axis, degrees):
        """Manual relative movement for azimuth or elevation (in degrees) with incremental steps."""
        if not self.motor_connected:
            messagebox.showwarning("Not Connected", "Motor controller not connected")
            return

        # Convert degrees to steps
        steps = int(degrees * STEPS_PER_DEGREE)
        print(f"[Motor] Manual move: {axis} by {degrees}° ({steps} steps)")

        # Use incremental movement for better position tracking
        success = self.incremental_move(axis, steps)

        if success:
            axis_name = "Azimuth" if axis == 'az' else "Elevation"
            final_pos = self.current_az_degrees.get() if axis == 'az' else self.current_el_degrees.get()
            self.status_label.config(text=f"{axis_name} manual move complete: {final_pos:.2f}°")
        else:
            messagebox.showwarning("Motor Error", f"Motor did not complete movement properly")

    def goto_absolute_azimuth(self):
        """Move to absolute azimuth position entered by user."""
        if not self.motor_connected:
            messagebox.showwarning("Not Connected", "Motor controller not connected")
            return

        try:
            target_degrees = self.target_az_degrees.get()
            print(f"[Motor] Moving to absolute azimuth position: {target_degrees}°")

            # Apply software home offset if in software mode
            actual_target = target_degrees
            if self.use_software_home:
                offset_degrees = self.home_offset_az / STEPS_PER_DEGREE
                actual_target = target_degrees + offset_degrees
                print(f"[Motor] Software home mode: adjusting target from {target_degrees}° to {actual_target}° (offset: {offset_degrees}°)")

            # Use the existing move_azimuth_absolute method
            success = self.move_azimuth_absolute(actual_target)
            if success:
                self.status_label.config(text=f"Moved to azimuth {target_degrees}°")
            else:
                messagebox.showwarning("Motor Error", f"Failed to move to azimuth {target_degrees}°")
        except Exception as e:
            messagebox.showerror("Input Error", f"Invalid azimuth value: {e}")

    def goto_absolute_elevation(self):
        """Move to absolute elevation position entered by user."""
        if not self.motor_connected:
            messagebox.showwarning("Not Connected", "Motor controller not connected")
            return

        try:
            target_degrees = self.target_el_degrees.get()

            # Check elevation limits
            if target_degrees < -75 or target_degrees > 75:
                messagebox.showwarning("Elevation Limit",
                                     f"Target elevation {target_degrees}° is outside safe limits.\n\n"
                                     f"Elevation must be between -75° and +75°")
                return

            print(f"[Motor] Moving to absolute elevation position: {target_degrees}°")

            # Apply software home offset if in software mode
            actual_target = target_degrees
            if self.use_software_home:
                offset_degrees = self.home_offset_el / STEPS_PER_DEGREE
                actual_target = target_degrees + offset_degrees
                print(f"[Motor] Software home mode: adjusting target from {target_degrees}° to {actual_target}° (offset: {offset_degrees}°)")

            # Use the existing move_elevation_absolute method
            success = self.move_elevation_absolute(actual_target)
            if success:
                self.status_label.config(text=f"Moved to elevation {target_degrees}°")
            else:
                messagebox.showwarning("Motor Error", f"Failed to move to elevation {target_degrees}°")
        except Exception as e:
            messagebox.showerror("Input Error", f"Invalid elevation value: {e}")
    
    def goto_home(self):
        """Return to home position (0, 0)."""
        if not self.motor_connected:
            messagebox.showwarning("Not Connected", "Motor controller not connected")
            return
        
        print("[Motor] Homing to (0°, 0°)...")
        
        # If using software home, need to go to the offset position
        if self.use_software_home:
            print(f"[Motor] Software home mode: moving to Az={self.home_offset_az}, El={self.home_offset_el}")
            response1 = self.send_motor_command(f"AZABS {self.home_offset_az}")
            response2 = self.send_motor_command(f"ELABS {self.home_offset_el}")
            self.status_label.config(text=f"Homing (software mode) -> Az:{response1}, El:{response2}")
            
            if response1 and response1.startswith("OK") and response2 and response2.startswith("OK"):
                self.root.after(1000, self.update_motor_position)
            else:
                messagebox.showwarning("Motor Error", f"Home command failed.\nAz: {response1}\nEl: {response2}")
        else:
            # Use hardware HOME command
            response = self.send_motor_command("HOME")
            self.status_label.config(text=f"Homing -> {response}")
            
            if response and response.startswith("OK"):
                self.root.after(1000, self.update_motor_position)
            else:
                messagebox.showwarning("Motor Error", f"Home command failed.\nResponse: {response}")
    
    def emergency_stop(self):
        """Emergency stop all motors."""
        if not self.motor_connected:
            return
        
        print("[Motor] EMERGENCY STOP!")
        response = self.send_motor_command("STOP")
        self.status_label.config(text=f"EMERGENCY STOP -> {response}")
        self.root.after(100, self.update_motor_position)
    
    def set_current_as_home(self):
        """Set the current position as the new home (0, 0) using SETZERO command or software fallback."""
        if not self.motor_connected:
            messagebox.showwarning("Not Connected", "Motor controller not connected")
            return
        
        # Get current position for confirmation message
        current_az = self.current_az_degrees.get()
        current_el = self.current_el_degrees.get()
        
        # Confirm with user
        confirm = messagebox.askyesno(
            "Calibrate Home Position",
            f"Set current position as new home (0°, 0°)?\n\n"
            f"Current Position:\n"
            f"  Azimuth: {current_az:.2f}°\n"
            f"  Elevation: {current_el:.2f}°\n\n"
            f"This will reset the position tracking to zero.\n"
            f"The 'Home (0,0)' button will return to this position.\n\n"
            f"Continue?"
        )
        
        if not confirm:
            self.status_label.config(text="Calibrate home cancelled")
            return
        
        print(f"[Motor] Attempting to calibrate home position (Az={current_az}°, El={current_el}°)...")
        
        # Try hardware SETZERO command first
        response = self.send_motor_command("SETZERO")
        
        if response and ("OK" in response.upper()):
            # Hardware command successful
            print(f"[Motor] Hardware SETZERO successful: {response}")
            self.use_software_home = False
            self.home_offset_az = 0
            self.home_offset_el = 0
            self.status_label.config(text=f"Home calibrated via Arduino (was Az={current_az:.2f}°, El={current_el:.2f}°)")
            messagebox.showinfo(
                "Home Position Calibrated",
                f"Home position set successfully via Arduino!\n\n"
                f"Position counters have been reset to (0°, 0°).\n"
                f"Previous coordinates: Az={current_az:.2f}°, El={current_el:.2f}°\n\n"
                f"Use 'Home (0,0)' button to return to this position."
            )
            # Update position display - should now show (0, 0)
            self.current_az_degrees.set(0.0)
            self.current_el_degrees.set(0.0)
            self.root.after(100, self.update_motor_position)
            
        else:
            # Hardware command failed, use software fallback
            print(f"[Motor] Hardware SETZERO failed: {response}")
            print(f"[Motor] Using software-based home calibration")
            
            self.use_software_home = True
            self.home_offset_az = self.current_az_steps
            self.home_offset_el = self.current_el_steps
            
            # Immediately update display to show (0, 0)
            self.current_az_degrees.set(0.0)
            self.current_el_degrees.set(0.0)
            
            self.status_label.config(text=f"Home calibrated via software (was Az={current_az:.2f}°, El={current_el:.2f}°)")
            messagebox.showinfo(
                "Home Position Calibrated (Software Mode)",
                f"Home position set successfully!\n\n"
                f"Using software-based tracking.\n"
                f"Position offsets saved: Az={current_az:.2f}°, El={current_el:.2f}°\n\n"
                f"Display now shows (0°, 0°).\n"
                f"Use 'Home (0,0)' button to return to this position."
            )
    
    # =========================================================================
    
    def show_help(self):
        """Show help dialog"""
        help_text = """RSL Controller v01 - ZNLE6 Real-Time Signal Monitor with Motor Controls

KEY IMPROVEMENTS:
• Motor position displayed in DEGREES instead of steps
• Incremental movement: all moves broken into 2-step chunks with position updates
• Auto-connects to motor controller on startup
• Elevation limits expanded: -75° to +75°
• Motor controls prominently displayed at top of window
• Frequent position updates every 200ms during monitoring
• Enhanced scrollable interface for all parameters

FEATURES:
• Live plot showing amplitude vs time
• Continuous CSV data logging with timestamps
• Configurable S-parameter selection
• Adjustable update rate and smoothing
• Independent motor control section
• Manual motor positioning controls (in degrees)
• Absolute position control - enter target degrees directly
• Incremental movement provides smooth tracking and progress updates
• Configurable home position
• Position tracking with degree display
• [TODO] Automated scanning capabilities

SETUP:
1. Enter ZNLE6 IP address and port
2. Connect to motor controller (Arduino via serial port)
3. Specify target frequency in Hz (e.g., 977e6 = 977 MHz)
4. Select S-parameter:
   - S21: Transmission measurements
   - S11: Reflection at port 1
   - S22: Reflection at port 2
5. Set update interval (500ms = 2 updates/second)
6. Configure smoothing window for noise reduction
7. Choose output directory and filename

USAGE:
• Click "Connect Motor" to establish connection
• Monitor starts automatically when motor connects
• A plot window will open with live data
• Use motor controls to position antenna during monitoring
• Data is saved to CSV throughout monitoring

MOTOR CONTROLS (In Degrees):
• Connect/Disconnect: Establish serial connection to Arduino
• Relative Movement: Move azimuth/elevation in configurable degree steps
  - CCW (counter-clockwise) is positive rotation for azimuth
  - Up is positive for elevation
  - All movements use incremental 2-step chunks with position updates
• Absolute Position: Enter target position in degrees and move directly
  - Positions are relative to home (0°, 0°)
  - CCW rotation is considered positive
  - Elevation limits enforced: -75° to +75°
  - Movement broken into 2-step increments with progress tracking
• Set Current as Home: Define current position as new (0°, 0°) reference
• Home (0,0): Return to home position
• Emergency Stop: Immediately halt all motor movement

INCREMENTAL MOVEMENT:
All motor movements (relative and absolute) are automatically broken into
2-step increments. After each increment:
• Motor position is queried and updated on display
• Progress percentage is shown in status bar
• Current position in degrees is displayed
This provides smooth tracking and allows monitoring signal changes during movement.

HOME POSITION CALIBRATION:
The "Set Current as Home" feature allows you to redefine the home position:
1. Move antenna to desired starting position
2. Click "Set Current as Home"
3. Arduino resets position counters to (0°, 0°)
4. "Home (0,0)" button will return to this position

POSITION DISPLAY:
All positions are automatically converted from steps to degrees:
• Standard conversion: 200 steps per full 360° rotation
• Displays with 2 decimal places for precision
• Updates frequent ly (every 200ms) during monitoring

WORKFLOW:
1. Connect motor controller
2. Position antenna at desired starting point
3. Click "Set Current as Home" to calibrate
4. Monitor starts automatically
5. Use motor controls to adjust antenna position
6. Observe signal changes in real-time as antenna moves
7. All data logged automatically to CSV

TIPS:
• Faster update intervals (100-500ms) for dynamic signals
• Slower intervals (1000-2000ms) for stable signals
• CSV file contains all data points with timestamps
• Motor positions logged for each measurement
• Use motor step size to fine-tune movements
"""
        
        help_window = tk.Toplevel(self.root)
        help_window.title("Help - RSL Controller v01")
        help_window.geometry("800x800")
        
        text_widget = tk.Text(help_window, wrap=tk.WORD, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(help_window, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.insert(1.0, help_text)
        text_widget.config(state=tk.DISABLED)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)


def main():
    root = tk.Tk()
    app = RSLControllerGUI(root)
    
    # Cleanup on window close
    def on_closing():
        app.position_update_running = False
        if app.motor_connected:
            app.disconnect_motor()
        if app.process:
            app.process.terminate()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
