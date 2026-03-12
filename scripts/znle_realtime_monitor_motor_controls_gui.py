#!/usr/bin/env python3
"""
GUI for ZNLE6 Real-Time Signal Monitor with Motor Controls

Provides graphical interface for continuous signal monitoring with live plot
AND motor control integration for automated antenna positioning.
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


class RealtimeMonitorMotorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ZNLE6 Real-Time Monitor with Motor Controls")
        self.root.geometry("650x700")
        
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
        self.current_az = tk.IntVar(value=0)
        self.current_el = tk.IntVar(value=0)
        self.manual_az_step = tk.IntVar(value=10)
        self.manual_el_step = tk.IntVar(value=5)
        
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
        
        self.create_widgets()
        self.refresh_motor_ports()
    
    def create_widgets(self):
        # Main container with scrollbar
        canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        main_frame = ttk.Frame(scrollable_frame, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        row = 0
        
        # Title
        title_label = ttk.Label(main_frame, text="ZNLE6 Real-Time Monitor + Motor Controls", 
                                font=('Arial', 14, 'bold'))
        title_label.grid(row=row, column=0, columnspan=2, pady=(0, 15))
        row += 1
        
        # Connection Settings
        conn_frame = ttk.LabelFrame(main_frame, text="VNA Connection Settings", padding="10")
        conn_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        ttk.Label(conn_frame, text="ZNLE6 IP Address:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(conn_frame, textvariable=self.ip, width=20).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2, sticky=tk.W, pady=2, padx=(10, 0))
        ttk.Entry(conn_frame, textvariable=self.port, width=10).grid(row=0, column=3, sticky=tk.W, pady=2, padx=5)
        
        # Motor Controller Connection
        motor_conn_frame = ttk.LabelFrame(main_frame, text="Motor Controller", padding="10")
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
        
        # Manual Motor Control
        manual_frame = ttk.LabelFrame(main_frame, text="Manual Motor Control", padding="10")
        manual_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Current position display
        pos_display_frame = ttk.Frame(manual_frame)
        pos_display_frame.grid(row=0, column=0, columnspan=4, pady=5)
        
        ttk.Label(pos_display_frame, text="Az:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=2)
        ttk.Label(pos_display_frame, textvariable=self.current_az, 
                 font=("Arial", 12), foreground="green").pack(side=tk.LEFT, padx=5)
        ttk.Label(pos_display_frame, text="El:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(15,2))
        ttk.Label(pos_display_frame, textvariable=self.current_el, 
                 font=("Arial", 12), foreground="blue").pack(side=tk.LEFT, padx=5)
        
        # Azimuth controls
        ttk.Label(manual_frame, text="Azimuth:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(manual_frame, textvariable=self.manual_az_step, width=8).grid(row=1, column=1, pady=2, padx=2)
        ttk.Button(manual_frame, text="← CCW", width=8,
                  command=lambda: self.manual_move('az', -self.manual_az_step.get())).grid(row=1, column=2, pady=2, padx=2)
        ttk.Button(manual_frame, text="CW →", width=8,
                  command=lambda: self.manual_move('az', self.manual_az_step.get())).grid(row=1, column=3, pady=2, padx=2)
        
        # Elevation controls
        ttk.Label(manual_frame, text="Elevation:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(manual_frame, textvariable=self.manual_el_step, width=8).grid(row=2, column=1, pady=2, padx=2)
        ttk.Button(manual_frame, text="↓ Down", width=8,
                  command=lambda: self.manual_move('el', -self.manual_el_step.get())).grid(row=2, column=2, pady=2, padx=2)
        ttk.Button(manual_frame, text="↑ Up", width=8,
                  command=lambda: self.manual_move('el', self.manual_el_step.get())).grid(row=2, column=3, pady=2, padx=2)
        
        # Quick actions
        ttk.Button(manual_frame, text="Home (0,0)", 
                  command=self.goto_home).grid(row=3, column=0, columnspan=2, pady=5, sticky=(tk.W, tk.E))
        ttk.Button(manual_frame, text="Emergency Stop", 
                  command=self.emergency_stop).grid(row=3, column=2, columnspan=2, pady=5, sticky=(tk.W, tk.E))
        
        # Home position setting
        ttk.Button(manual_frame, text="Set Current as Home", 
                  command=self.set_current_as_home).grid(row=4, column=0, columnspan=4, pady=5, sticky=(tk.W, tk.E))
        
        ttk.Label(manual_frame, text="⚠ Elevation limits: -20 to +20", 
                 foreground="red", font=('Arial', 8)).grid(row=5, column=0, columnspan=4, pady=(2, 0))
        
        # TODO: Motor Control Settings (for future TCP/IP motor controllers)
        # motor_frame = ttk.LabelFrame(main_frame, text="Motor Control Settings", padding="10")
        # motor_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        # row += 1
        # 
        # motor_enable_check = ttk.Checkbutton(motor_frame, text="Enable Motor Control", 
        #                                      variable=self.motor_enabled)
        # motor_enable_check.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)
        # 
        # ttk.Label(motor_frame, text="Motor Controller IP:").grid(row=1, column=0, sticky=tk.W, pady=2)
        # ttk.Entry(motor_frame, textvariable=self.motor_ip, width=20).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        # 
        # ttk.Label(motor_frame, text="Motor Port:").grid(row=2, column=0, sticky=tk.W, pady=2)
        # ttk.Entry(motor_frame, textvariable=self.motor_port, width=20).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
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
        ttk.Label(param_frame, text="(S11/S22=Reflection, S21/S12=Transmission)").pack(side=tk.LEFT)
        
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
        
        # Info text
        info_frame = ttk.LabelFrame(main_frame, text="Information", padding="10")
        info_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        info_text = tk.Text(info_frame, height=8, width=70, wrap=tk.WORD)
        info_text.insert(1.0, 
            "Real-Time Signal Monitor with Motor Control Integration\n\n"
            "This tool continuously monitors signal amplitude at a target frequency\n"
            "with independent motor controls for antenna alignment.\n\n"
            "• Live plot window shows amplitude vs time\n"
            "• Data is continuously saved to CSV\n"
            "• Manual motor controls for azimuth/elevation positioning\n"
            "• 'Set Current as Home' allows calibrating reference position\n"
            "• Monitor and motor controls operate independently")
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
            
            # TODO: Validate motor parameters if enabled
            # if self.motor_enabled.get():
            #     # Validate motor IP and port
            #     pass
            
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
        
        # TODO: Add motor control arguments
        # if self.motor_enabled.get():
        #     cmd.extend(["--motor-ip", self.motor_ip.get()])
        #     cmd.extend(["--motor-port", self.motor_port.get()])
        
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
        
        # Run in thread
        thread = threading.Thread(target=self.run_monitor, args=(cmd,), daemon=True)
        thread.start()
    
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
            self.status_label.config(text="Stopping monitor...")
    
    # =========================================================================
    # Motor Controller Functions (from Antenna Aligner)
    # =========================================================================
    
    def refresh_motor_ports(self):
        """Scan for available serial ports."""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.motor_port_combo['values'] = ports
        if ports and not self.motor_port.get():
            self.motor_port.set(ports[0])
    
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
            else:
                # No valid response
                raise Exception(f"Arduino not responding properly. Got: {test_response or 'no response'}")
            
        except serial.SerialException as e:
            print(f"[Motor] Connection failed: {e}")
            self.root.after(0, self.connection_failed, port, str(e))
        except Exception as e:
            print(f"[Motor] Error: {e}")
            self.root.after(0, self.connection_failed, port, str(e))
    
    def connection_success(self, port):
        """Called from main thread when connection succeeds."""
        self.motor_connect_button.config(text="Disconnect Motor", state=tk.NORMAL)
        self.status_label.config(text=f"Motor controller connected on {port}")
        
        # Reset software home mode on new connection
        self.use_software_home = False
        self.home_offset_az = 0
        self.home_offset_el = 0
        
        messagebox.showinfo("Motor Connected", f"Successfully connected to motor controller on {port}")
    
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
        """Query current motor positions."""
        if not self.motor_connected:
            return
        
        response = self.send_motor_command("STATUS")
        if response and response.startswith("POS"):
            try:
                # Parse: "POS AZ:123 EL:456"
                parts = response.split()
                az = int(parts[1].split(':')[1])
                el = int(parts[2].split(':')[1])
                
                # Apply software home offset if in software mode
                if self.use_software_home:
                    az = az - self.home_offset_az
                    el = el - self.home_offset_el
                
                self.current_az.set(az)
                self.current_el.set(el)
                print(f"[Motor] Position updated: Az={az}, El={el}" + 
                      (f" (software offset: Az={self.home_offset_az}, El={self.home_offset_el})" if self.use_software_home else ""))
            except (IndexError, ValueError) as e:
                print(f"[Motor] Error parsing status: {response} - {e}")
                self.status_label.config(text=f"Error parsing motor status: {response}")
        elif response:
            print(f"[Motor] Unexpected STATUS response: {response}")
    
    def move_azimuth_absolute(self, target_az):
        """Move azimuth to absolute position."""
        response = self.send_motor_command(f"AZABS {target_az}")
        if response and response.startswith("OK"):
            self.status_label.config(text=f"Moving to azimuth {target_az}")
            # Wait for movement to complete (estimate based on speed)
            time.sleep(0.5)
            self.update_motor_position()
            return True
        else:
            self.status_label.config(text=f"Azimuth move failed: {response}")
            return False
    
    def move_elevation_absolute(self, target_el):
        """Move elevation to absolute position."""
        response = self.send_motor_command(f"ELABS {target_el}")
        if response and response.startswith("OK"):
            self.status_label.config(text=f"Moving to elevation {target_el}")
            time.sleep(0.5)
            self.update_motor_position()
            return True
        else:
            self.status_label.config(text=f"Elevation move failed: {response}")
            return False
    
    def manual_move(self, axis, steps):
        """Manual relative movement for azimuth or elevation."""
        if not self.motor_connected:
            messagebox.showwarning("Not Connected", "Motor controller not connected")
            return
        
        print(f"[Motor] Manual move: {axis} by {steps:+d} steps")
        
        if axis == 'az':
            response = self.send_motor_command(f"AZ {steps}")
            self.status_label.config(text=f"Azimuth move: {steps:+d} steps -> {response}")
        else:  # elevation
            response = self.send_motor_command(f"EL {steps}")
            self.status_label.config(text=f"Elevation move: {steps:+d} steps -> {response}")
        
        if response and response.startswith("OK"):
            # Update position after successful move
            self.root.after(300, self.update_motor_position)
        else:
            messagebox.showwarning("Motor Error", f"Motor did not respond properly.\nResponse: {response}")
    
    def goto_home(self):
        """Return to home position (0, 0)."""
        if not self.motor_connected:
            messagebox.showwarning("Not Connected", "Motor controller not connected")
            return
        
        print("[Motor] Homing to (0, 0)...")
        
        # If using software home, need to go to the offset position
        if self.use_software_home:
            print(f"[Motor] Software home mode: moving to Az={self.home_offset_az}, El={self.home_offset_el}")
            response1 = self.send_motor_command(f"AZABS {self.home_offset_az}")
            response2 = self.send_motor_command(f"ELABS {self.home_offset_el}")
            self.status_label.config(text=f"Homing (software mode) -> Az:{response1}, El:{response2}")
            
            if response1 and response1.startswith("OK") and response2 and response2.startswith("OK"):
                self.root.after(1000, self.update_motor_position)
            else:
                messagebox.showwarning("Motor Error", f"Home command failed.\\nAz: {response1}\\nEl: {response2}")
        else:
            # Use hardware HOME command
            response = self.send_motor_command("HOME")
            self.status_label.config(text=f"Homing -> {response}")
            
            if response and response.startswith("OK"):
                self.root.after(1000, self.update_motor_position)
            else:
                messagebox.showwarning("Motor Error", f"Home command failed.\\nResponse: {response}")
    
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
        current_az = self.current_az.get()
        current_el = self.current_el.get()
        
        # Confirm with user
        confirm = messagebox.askyesno(
            "Calibrate Home Position",
            f"Set current position as new home (0, 0)?\\n\\n"
            f"Current Position:\\n"
            f"  Azimuth: {current_az}°\\n"
            f"  Elevation: {current_el}°\\n\\n"
            f"This will reset the position tracking to zero.\\n"
            f"The 'Home (0,0)' button will return to this position.\\n\\n"
            f"Continue?"
        )
        
        if not confirm:
            self.status_label.config(text="Calibrate home cancelled")
            return
        
        print(f"[Motor] Attempting to calibrate home position (Az={current_az}, El={current_el})...")
        
        # Try hardware SETZERO command first
        response = self.send_motor_command("SETZERO")
        
        if response and ("OK" in response.upper()):
            # Hardware command successful
            print(f"[Motor] Hardware SETZERO successful: {response}")
            self.use_software_home = False
            self.home_offset_az = 0
            self.home_offset_el = 0
            self.status_label.config(text=f"Home calibrated via Arduino (was Az={current_az}, El={current_el})")
            messagebox.showinfo(
                "Home Position Calibrated",
                f"Home position set successfully via Arduino!\\n\\n"
                f"Position counters have been reset to (0, 0).\\n"
                f"Previous coordinates: Az={current_az}°, El={current_el}°\\n\\n"
                f"Use 'Home (0,0)' button to return to this position."
            )
            # Update position display - should now show (0, 0)
            self.current_az.set(0)
            self.current_el.set(0)
            self.root.after(100, self.update_motor_position)
            
        else:
            # Hardware command failed, use software fallback
            print(f"[Motor] Hardware SETZERO failed: {response}")
            print(f"[Motor] Using software-based home calibration")
            
            self.use_software_home = True
            self.home_offset_az = current_az
            self.home_offset_el = current_el
            
            # Immediately update display to show (0, 0)
            self.current_az.set(0)
            self.current_el.set(0)
            
            self.status_label.config(text=f"Home calibrated via software (was Az={current_az}, El={current_el})")
            messagebox.showinfo(
                "Home Position Calibrated (Software Mode)",
                f"Home position set successfully!\\n\\n"
                f"Using software-based tracking (Arduino firmware may be outdated).\\n"
                f"Position offsets saved: Az={current_az}°, El={current_el}°\\n\\n"
                f"Display now shows (0, 0).\\n"
                f"Use 'Home (0,0)' button to return to this position.\\n\\n"
                f"Note: To use hardware mode, upload the latest Arduino sketch from:\\n"
                f"arduino/antenna_controller/antenna_controller.ino"
            )
    
    # =========================================================================
    
    def show_help(self):
        """Show help dialog"""
        help_text = """ZNLE6 Real-Time Signal Monitor with Motor Controls

This tool continuously monitors signal amplitude at a single target frequency
with integrated motor control for automated antenna positioning.

FEATURES:
• Live plot showing amplitude vs time
• Continuous CSV data logging with timestamps
• Configurable S-parameter selection
• Adjustable update rate and smoothing
• Independent motor control section
• Manual motor positioning controls
• Configurable home position
• [TODO] Angle tracking and correlation
• [TODO] Automated scanning capabilities

SETUP:
1. Enter ZNLE6 IP address and port
2. Connect to motor controller (Arduino via serial port)
3. Specify target frequency in Hz (e.g., 977e6 = 977 MHz)
4. Select S-parameter:
   - S21: Transmission from port 1 to port 2 (two antennas)
   - S11: Reflection at port 1
   - S22: Reflection at port 2
5. Set update interval (500ms = 2 updates/second)
6. Configure smoothing window for noise reduction
7. Choose output directory and filename

USAGE:
• Click "Start Real-Time Monitor" to begin monitoring
• A plot window will open with live data
• Monitor continues until you close the plot window or click Stop
• Data is saved to CSV throughout monitoring
• Use motor controls independently to position antenna during monitoring

MOTOR CONTROLS:
• Connect/Disconnect: Establish serial connection to Arduino
• Manual Controls: Move azimuth/elevation in configurable steps
• Set Current as Home: Define current position as new (0, 0) reference (uses SETZERO command)
• Home (0,0): Return to home position
• Emergency Stop: Immediately halt all motor movement

HOME POSITION CALIBRATION:
The "Set Current as Home" feature allows you to redefine the home position:
1. Move antenna to desired starting position
2. Click "Set Current as Home"
3. Arduino resets position counters to (0, 0)
4. "Home (0,0)" button will return to this position

This uses the SETZERO command which resets the Arduino's internal position
tracking to zero at the current physical location.

This is useful for:
• Calibrating antenna alignment at startup
• Adjusting for equipment repositioning
• Setting reference point for measurement series

WORKFLOW:
1. Connect motor controller
2. Position antenna at desired starting point
3. Click "Set Current as Home" to calibrate
4. Start the real-time monitor
5. Use motor controls to adjust antenna position
6. Observe signal changes in real-time as antenna moves

S-PARAMETER GUIDE:
• S21: Best for antenna-to-antenna transmission testing
• S22: Good for single-antenna reception monitoring
• S11: For transmitter reflection measurements

TIPS:
• Faster update intervals (100-500ms) for dynamic signals
• Slower intervals (1000-2000ms) for stable signals or motor movement
• CSV file contains all data points with timestamps
• [TODO] Motor angles will be logged for each measurement
"""
        
        help_window = tk.Toplevel(self.root)
        help_window.title("Help - Real-Time Monitor with Motor Controls")
        help_window.geometry("700x700")
        
        text_widget = tk.Text(help_window, wrap=tk.WORD, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(help_window, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.insert(1.0, help_text)
        text_widget.config(state=tk.DISABLED)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)


def main():
    root = tk.Tk()
    app = RealtimeMonitorMotorGUI(root)
    
    # Cleanup on window close
    def on_closing():
        if app.motor_connected:
            app.disconnect_motor()
        if app.process:
            app.process.terminate()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
