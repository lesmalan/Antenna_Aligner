#!/usr/bin/env python3
"""
GUI for Antenna Aligner Motor Controller
Controls azimuth and elevation stepper motors via Arduino
"""
import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime


class MotorControllerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Antenna Aligner Motor Controller")
        self.root.geometry("650x700")
        
        # Serial connection
        self.ser = None
        self.connected = False
        
        # Variables
        self.port = tk.StringVar(value="/dev/ttyACM0")
        self.baudrate = tk.IntVar(value=115200)
        self.motor_speed = tk.IntVar(value=30)
        
        # Position tracking
        self.current_az = tk.StringVar(value="0")
        self.current_el = tk.StringVar(value="0")
        
        # Movement controls
        self.az_steps = tk.IntVar(value=10)
        self.el_steps = tk.IntVar(value=10)
        self.az_target = tk.IntVar(value=0)
        self.el_target = tk.IntVar(value=0)
        
        # Status monitoring
        self.auto_update_status = tk.BooleanVar(value=True)
        self.update_thread = None
        self.stop_update_thread = False
        
        self.create_widgets()
        self.refresh_ports()
        
        # Auto-connect after GUI is ready
        self.root.after(500, self.auto_connect)
    
    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        row = 0
        
        # Title
        title = ttk.Label(main_frame, text="Antenna Aligner Motor Controller", 
                         font=("Arial", 16, "bold"))
        title.grid(row=row, column=0, columnspan=3, pady=(0, 15))
        row += 1
        
        # Connection Frame
        conn_frame = ttk.LabelFrame(main_frame, text="Connection Settings", padding="10")
        conn_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        ttk.Label(conn_frame, text="Serial Port:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port, width=20)
        self.port_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Button(conn_frame, text="Refresh", command=self.refresh_ports).grid(row=0, column=2, pady=2, padx=5)
        
        ttk.Label(conn_frame, text="Baudrate:").grid(row=1, column=0, sticky=tk.W, pady=2)
        baudrate_combo = ttk.Combobox(conn_frame, textvariable=self.baudrate, 
                                      values=[9600, 19200, 38400, 57600, 115200], 
                                      width=20, state="readonly")
        baudrate_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        self.connect_button = ttk.Button(conn_frame, text="Connect", command=self.toggle_connection)
        self.connect_button.grid(row=1, column=2, pady=2, padx=5)
        
        conn_frame.columnconfigure(1, weight=1)
        
        # Status Display Frame
        status_frame = ttk.LabelFrame(main_frame, text="Current Position", padding="10")
        status_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        ttk.Label(status_frame, text="Azimuth:", font=("Arial", 12, "bold")).grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        az_display = ttk.Label(status_frame, textvariable=self.current_az, 
                              font=("Arial", 14), foreground="blue")
        az_display.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        ttk.Label(status_frame, text="steps").grid(row=0, column=2, sticky=tk.W, pady=5)
        
        ttk.Label(status_frame, text="Elevation:", font=("Arial", 12, "bold")).grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        el_display = ttk.Label(status_frame, textvariable=self.current_el, 
                              font=("Arial", 14), foreground="blue")
        el_display.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        ttk.Label(status_frame, text="steps").grid(row=1, column=2, sticky=tk.W, pady=5)
        
        ttk.Checkbutton(status_frame, text="Auto-update status", 
                       variable=self.auto_update_status,
                       command=self.toggle_auto_update).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Button(status_frame, text="Refresh Status", 
                  command=self.update_status).grid(row=2, column=2, pady=5)
        
        ttk.Label(status_frame, text="⚠ Elevation limits: -20 to +20 steps", 
                 foreground="red", font=('Arial', 9)).grid(row=3, column=0, columnspan=3, pady=(5, 0))
        
        # Motor Settings Frame
        settings_frame = ttk.LabelFrame(main_frame, text="Motor Settings", padding="10")
        settings_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        ttk.Label(settings_frame, text="Motor Speed (RPM):").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Scale(settings_frame, from_=10, to=100, variable=self.motor_speed, 
                 orient=tk.HORIZONTAL, length=200, command=lambda v: self.motor_speed.set(int(float(v) / 10) * 10)).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        ttk.Label(settings_frame, textvariable=self.motor_speed).grid(row=0, column=2, pady=2)
        ttk.Button(settings_frame, text="Apply Speed", 
                  command=self.set_speed).grid(row=0, column=3, pady=2, padx=5)
        
        settings_frame.columnconfigure(1, weight=1)
        
        # Relative Movement Frame
        rel_frame = ttk.LabelFrame(main_frame, text="Relative Movement (Steps)", padding="10")
        rel_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Azimuth relative controls
        ttk.Label(rel_frame, text="Azimuth:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(rel_frame, textvariable=self.az_steps, width=10).grid(row=0, column=1, pady=5, padx=5)
        ttk.Button(rel_frame, text="← CCW", 
                  command=lambda: self.move_relative('az', -self.az_steps.get())).grid(row=0, column=2, pady=5, padx=2)
        ttk.Button(rel_frame, text="CW →", 
                  command=lambda: self.move_relative('az', self.az_steps.get())).grid(row=0, column=3, pady=5, padx=2)
        
        # Elevation relative controls
        ttk.Label(rel_frame, text="Elevation:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(rel_frame, textvariable=self.el_steps, width=10).grid(row=1, column=1, pady=5, padx=5)
        ttk.Button(rel_frame, text="↓ Down", 
                  command=lambda: self.move_relative('el', -self.el_steps.get())).grid(row=1, column=2, pady=5, padx=2)
        ttk.Button(rel_frame, text="↑ Up", 
                  command=lambda: self.move_relative('el', self.el_steps.get())).grid(row=1, column=3, pady=5, padx=2)
        
        # Absolute Movement Frame
        abs_frame = ttk.LabelFrame(main_frame, text="Absolute Position (Steps)", padding="10")
        abs_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        ttk.Label(abs_frame, text="Target Azimuth:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(abs_frame, textvariable=self.az_target, width=15).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        ttk.Label(abs_frame, text="Target Elevation:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(abs_frame, textvariable=self.el_target, width=15).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        ttk.Button(abs_frame, text="Go To Position", 
                  command=self.goto_position, width=20).grid(row=2, column=0, columnspan=2, pady=10)
        
        abs_frame.columnconfigure(1, weight=1)
        
        # Quick Actions Frame
        actions_frame = ttk.LabelFrame(main_frame, text="Quick Actions", padding="10")
        actions_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        ttk.Button(actions_frame, text="Home (0, 0)", 
                  command=self.home, width=15).grid(row=0, column=0, pady=5, padx=5)
        ttk.Button(actions_frame, text="Set as Home", 
                  command=self.calibrate_home, width=15).grid(row=0, column=1, pady=5, padx=5)
        ttk.Button(actions_frame, text="STOP", 
                  command=self.emergency_stop, width=15).grid(row=0, column=2, pady=5, padx=5)
        
        # Log Frame
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="10")
        log_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        row += 1
        
        self.log_text = tk.Text(log_frame, height=10, width=70, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text['yscrollcommand'] = scrollbar.set
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(row-1, weight=1)
        
        self.log("GUI initialized. Connect to Arduino to begin.")
    
    def log(self, message):
        """Add timestamped message to log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def refresh_ports(self):
        """Scan for available serial ports."""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports and not self.port.get():
            self.port.set(ports[0])
        self.log(f"Found {len(ports)} serial port(s)")
    
    def toggle_connection(self):
        """Connect or disconnect from Arduino."""
        if self.connected:
            self.disconnect()
        else:
            self.connect()
    
    def auto_connect(self):
        """Automatically connect on startup."""
        if not self.connected:
            self.log("Attempting auto-connect...")
            self.connect()
    
    def prompt_calibration(self):
        """Prompt user to calibrate home position."""
        if messagebox.askyesno("Home Calibration", 
                               "Is the receiver currently at the horizontal home position?\n\n"
                               "Click 'Yes' to set this as home (0, 0).\n"
                               "Click 'No' to manually adjust first."):
            self.calibrate_home()
    
    def connect(self):
        """Establish serial connection to Arduino."""
        try:
            self.ser = serial.Serial(self.port.get(), self.baudrate.get(), timeout=2)
            time.sleep(2)  # Wait for Arduino reset
            
            # Read startup messages
            while self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8').strip()
                self.log(f"Arduino: {line}")
            
            self.connected = True
            self.connect_button.config(text="Disconnect")
            self.log(f"Connected to {self.port.get()}")
            
            # Get initial status
            self.update_status()
            
            # Prompt for home calibration
            self.prompt_calibration()
            
        except serial.SerialException as e:
            messagebox.showerror("Connection Error", f"Could not open {self.port.get()}\n\n{str(e)}")
            self.log(f"Connection failed: {e}")
    
    def disconnect(self):
        """Close serial connection."""
        if self.ser and self.ser.is_open:
            # Stop auto-update if running
            if self.auto_update_status.get():
                self.auto_update_status.set(False)
                self.toggle_auto_update()
            
            self.ser.close()
            self.connected = False
            self.connect_button.config(text="Connect")
            self.log("Disconnected from Arduino")
    
    def send_command(self, command):
        """Send command to Arduino and return response."""
        if not self.connected or not self.ser:
            messagebox.showwarning("Not Connected", "Please connect to Arduino first")
            return None
        
        try:
            self.ser.write((command + '\n').encode('utf-8'))
            self.ser.flush()
            response = self.ser.readline().decode('utf-8').strip()
            return response
        except Exception as e:
            self.log(f"Communication error: {e}")
            messagebox.showerror("Communication Error", str(e))
            return None
    
    def update_status(self):
        """Query and update current motor positions."""
        response = self.send_command("STATUS")
        if response and response.startswith("POS"):
            try:
                # Parse: "POS AZ:123 EL:456"
                parts = response.split()
                az = parts[1].split(':')[1]
                el = parts[2].split(':')[1]
                self.current_az.set(az)
                self.current_el.set(el)
            except (IndexError, ValueError) as e:
                self.log(f"Error parsing status: {response}")
    
    def toggle_auto_update(self):
        """Start or stop automatic status updates."""
        if self.auto_update_status.get():
            # Start update thread
            self.stop_update_thread = False
            self.update_thread = threading.Thread(target=self.auto_update_worker, daemon=True)
            self.update_thread.start()
            self.log("Auto-update enabled")
        else:
            # Stop update thread
            self.stop_update_thread = True
            if self.update_thread:
                self.update_thread.join(timeout=2)
            self.log("Auto-update disabled")
    
    def auto_update_worker(self):
        """Worker thread for automatic status updates."""
        while not self.stop_update_thread and self.connected:
            self.root.after(0, self.update_status)
            time.sleep(1)  # Update every second
    
    def move_relative(self, axis, steps):
        """Move motor by relative steps."""
        if axis == 'az':
            response = self.send_command(f"AZ {steps}")
            self.log(f"Azimuth move: {steps} steps → {response}")
        else:
            response = self.send_command(f"EL {steps}")
            self.log(f"Elevation move: {steps} steps → {response}")
        
        if response and response.startswith("OK"):
            # Update status after movement
            self.root.after(100, self.update_status)
    
    def goto_position(self):
        """Move to absolute position."""
        az_target = self.az_target.get()
        el_target = self.el_target.get()
        
        response1 = self.send_command(f"AZABS {az_target}")
        self.log(f"Azimuth to {az_target}: {response1}")
        
        response2 = self.send_command(f"ELABS {el_target}")
        self.log(f"Elevation to {el_target}: {response2}")
        
        # Update status after movement
        self.root.after(100, self.update_status)
    
    def home(self):
        """Return to home position (0, 0)."""
        response = self.send_command("HOME")
        self.log(f"Homing → {response}")
        
        if response and response.startswith("OK"):
            self.root.after(100, self.update_status)
    
    def calibrate_home(self):
        """Set current position as new home (0, 0)."""
        if messagebox.askyesno("Calibrate Home", 
                               "Set the current position as the new home (0, 0)?\n\n"
                               "This will reset the position counters to zero."):
            response = self.send_command("SETZERO")
            self.log(f"Calibrate home → {response}")
            
            if response and response.startswith("OK"):
                self.current_az.set("0")
                self.current_el.set("0")
                self.root.after(100, self.update_status)
    
    def set_speed(self):
        """Set motor speed."""
        speed = self.motor_speed.get()
        response = self.send_command(f"SPEED {speed}")
        self.log(f"Set speed to {speed} RPM → {response}")
    
    def emergency_stop(self):
        """Emergency stop all motors."""
        response = self.send_command("STOP")
        self.log(f"EMERGENCY STOP → {response}")
        self.root.after(100, self.update_status)


def main():
    root = tk.Tk()
    app = MotorControllerGUI(root)
    
    def on_closing():
        if app.connected:
            if messagebox.askokcancel("Quit", "Disconnect from Arduino and quit?"):
                app.disconnect()
                root.destroy()
        else:
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
