#!/usr/bin/env python3
"""
Antenna Aligner Combined GUI
Integrates VNA signal monitoring with motor control for antenna alignment

This application combines:
  - ZNLE6 VNA control for signal strength measurement
  - Arduino motor controller for antenna rotation
  - Real-time plotting of signal vs. azimuth angle

Features:
  - Monitor single frequency or frequency range
  - Automated azimuth sweeps with signal recording
  - Real-time plotting and data export
  - Manual motor control with live signal feedback

Hardware Requirements:
  - R&S ZNLE6 VNA (192.168.15.90 default)
  - Arduino Uno R3 with motor shield (/dev/ttyACM0 default)
  - NanoVNA-H4 transmitter
  - Pasco WA-9800A receiver on stepper motor mount

Dependencies:
  pip install pyvisa pyvisa-py matplotlib pyserial

UCO Senior Design Group 2 - Spring 2026
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
import os
import sys

# VNA control
try:
    import pyvisa as visa
except ImportError:
    print("Error: pyvisa not installed. Run: pip install pyvisa pyvisa-py", file=sys.stderr)
    sys.exit(1)

# Plotting
try:
    import matplotlib
    matplotlib.use('TkAgg')  # Tkinter backend for embedding in GUI
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
except ImportError:
    print("Error: matplotlib not installed. Run: pip install matplotlib", file=sys.stderr)
    sys.exit(1)


class AntennaAlignerGUI:
    """
    Combined GUI for VNA monitoring and motor control.
    """
    
    def __init__(self, root):
        self.root = root
        self.root.title("Antenna Aligner - VNA + Motor Control")
        self.root.geometry("1000x800")
        
        # ==================================================================
        # Motor Controller State
        # ==================================================================
        self.motor_ser = None
        self.motor_connected = False
        
        self.motor_port = tk.StringVar(value="/dev/ttyACM0")
        self.motor_baudrate = tk.IntVar(value=115200)
        self.motor_speed = tk.IntVar(value=30)
        self.current_az = tk.IntVar(value=0)
        self.current_el = tk.IntVar(value=0)
        
        # ==================================================================
        # VNA State
        # ==================================================================
        self.vna_inst = None
        self.vna_connected = False
        
        self.vna_ip = tk.StringVar(value="192.168.15.90")
        self.vna_port = tk.IntVar(value=5025)
        self.vna_param = tk.StringVar(value="S11")
        
        # ==================================================================
        # Measurement Parameters
        # ==================================================================
        self.monitor_mode = tk.StringVar(value="single")  # "single" or "range"
        self.monitor_freq = tk.DoubleVar(value=977e6)  # Single frequency (Hz)
        self.freq_start = tk.DoubleVar(value=900e6)    # Range start (Hz)
        self.freq_stop = tk.DoubleVar(value=1500e6)    # Range stop (Hz)
        self.sweep_points = tk.IntVar(value=201)
        
        # ==================================================================
        # Scan Parameters
        # ==================================================================
        self.scan_mode = tk.StringVar(value="azimuth")  # "azimuth", "elevation", "2d"
        
        # Azimuth scan
        self.scan_start_az = tk.IntVar(value=-180)
        self.scan_stop_az = tk.IntVar(value=180)
        self.scan_step_az = tk.IntVar(value=10)
        
        # Elevation scan
        self.scan_start_el = tk.IntVar(value=-20)
        self.scan_stop_el = tk.IntVar(value=20)
        self.scan_step_el = tk.IntVar(value=5)
        self.scan_el_fixed = tk.IntVar(value=0)  # Fixed elevation for azimuth-only scans
        
        self.scan_delay = tk.DoubleVar(value=1.0)  # Delay between measurements
        
        # Manual control
        self.manual_az_step = tk.IntVar(value=10)
        self.manual_el_step = tk.IntVar(value=5)
        
        # ==================================================================
        # Data Storage
        # ==================================================================
        self.scan_data = []  # List of (azimuth, elevation, amplitude) tuples
        self.scanning = False
        self.scan_thread = None
        
        # ==================================================================
        # Build GUI
        # ==================================================================
        self.create_widgets()
        self.refresh_motor_ports()
    
    def create_widgets(self):
        """Build the GUI layout."""
        
        # Main container with two columns: Controls (left) and Plot (right)
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Left column: Scrollable control panels
        # Create a canvas for scrolling
        left_canvas = tk.Canvas(main_frame, borderwidth=0, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        
        left_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        left_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S), padx=(0, 10))
        
        # Frame inside canvas for all controls
        left_frame = ttk.Frame(left_canvas)
        left_canvas_window = left_canvas.create_window((0, 0), window=left_frame, anchor="nw")
        
        # Configure canvas scrolling
        def configure_scroll_region(event=None):
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        
        def configure_canvas_width(event):
            canvas_width = event.width
            left_canvas.itemconfig(left_canvas_window, width=canvas_width)
        
        left_frame.bind("<Configure>", configure_scroll_region)
        left_canvas.bind("<Configure>", configure_canvas_width)
        
        # Enable mouse wheel scrolling
        def on_mousewheel(event):
            left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def on_mousewheel_linux(event):
            if event.num == 4:
                left_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                left_canvas.yview_scroll(1, "units")
        
        # Bind mouse wheel events
        left_canvas.bind_all("<MouseWheel>", on_mousewheel)  # Windows/Mac
        left_canvas.bind_all("<Button-4>", on_mousewheel_linux)  # Linux scroll up
        left_canvas.bind_all("<Button-5>", on_mousewheel_linux)  # Linux scroll down
        
        # Right column: Plot display
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # ==================================================================
        # LEFT COLUMN: Control Panels
        # ==================================================================
        
        row = 0
        
        # Title
        title = ttk.Label(left_frame, text="Antenna Aligner", 
                         font=("Arial", 16, "bold"))
        title.grid(row=row, column=0, columnspan=2, pady=(0, 15))
        row += 1
        
        # ---------------------------------------------------------------
        # Motor Controller Connection
        # ---------------------------------------------------------------
        motor_conn_frame = ttk.LabelFrame(left_frame, text="Motor Controller", padding="10")
        motor_conn_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        ttk.Label(motor_conn_frame, text="Port:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.motor_port_combo = ttk.Combobox(motor_conn_frame, textvariable=self.motor_port, width=15)
        self.motor_port_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        ttk.Button(motor_conn_frame, text="Refresh", 
                  command=self.refresh_motor_ports).grid(row=0, column=2, pady=2, padx=5)
        
        self.motor_connect_button = ttk.Button(motor_conn_frame, text="Connect Motor", 
                                              command=self.toggle_motor_connection)
        self.motor_connect_button.grid(row=1, column=0, columnspan=3, pady=5)
        
        motor_conn_frame.columnconfigure(1, weight=1)
        
        # ---------------------------------------------------------------
        # VNA Connection
        # ---------------------------------------------------------------
        vna_conn_frame = ttk.LabelFrame(left_frame, text="VNA Connection", padding="10")
        vna_conn_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        ttk.Label(vna_conn_frame, text="IP:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(vna_conn_frame, textvariable=self.vna_ip, width=15).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(vna_conn_frame, text="Port:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(vna_conn_frame, textvariable=self.vna_port, width=15).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(vna_conn_frame, text="S-Param:").grid(row=2, column=0, sticky=tk.W, pady=2)
        param_combo = ttk.Combobox(vna_conn_frame, textvariable=self.vna_param, 
                                   values=["S11", "S21", "S12", "S22"], 
                                   width=13, state="readonly")
        param_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        self.vna_connect_button = ttk.Button(vna_conn_frame, text="Connect VNA", 
                                            command=self.toggle_vna_connection)
        self.vna_connect_button.grid(row=3, column=0, columnspan=2, pady=5)
        
        vna_conn_frame.columnconfigure(1, weight=1)
        
        # ---------------------------------------------------------------
        # Frequency Configuration
        # ---------------------------------------------------------------
        freq_frame = ttk.LabelFrame(left_frame, text="Frequency Settings", padding="10")
        freq_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Mode selection
        ttk.Radiobutton(freq_frame, text="Single Frequency", 
                       variable=self.monitor_mode, value="single",
                       command=self.update_freq_mode).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Radiobutton(freq_frame, text="Frequency Range (Peak)", 
                       variable=self.monitor_mode, value="range",
                       command=self.update_freq_mode).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # Single frequency input
        ttk.Label(freq_frame, text="Freq (MHz):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.single_freq_entry = ttk.Entry(freq_frame, textvariable=self.monitor_freq, width=15)
        self.single_freq_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        # Frequency range inputs
        ttk.Label(freq_frame, text="Start (MHz):").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.range_start_entry = ttk.Entry(freq_frame, textvariable=self.freq_start, width=15, state="disabled")
        self.range_start_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(freq_frame, text="Stop (MHz):").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.range_stop_entry = ttk.Entry(freq_frame, textvariable=self.freq_stop, width=15, state="disabled")
        self.range_stop_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(freq_frame, text="Points:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.points_entry = ttk.Entry(freq_frame, textvariable=self.sweep_points, width=15, state="disabled")
        self.points_entry.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        freq_frame.columnconfigure(1, weight=1)
        
        # ---------------------------------------------------------------
        # Manual Motor Control
        # ---------------------------------------------------------------
        manual_frame = ttk.LabelFrame(left_frame, text="Manual Motor Control", padding="10")
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
        
        ttk.Label(manual_frame, text="⚠ Elevation limits: -20 to +20", 
                 foreground="red", font=('Arial', 8)).grid(row=4, column=0, columnspan=4, pady=(2, 0))
        
        # ---------------------------------------------------------------
        # Scan Parameters
        # ---------------------------------------------------------------
        scan_frame = ttk.LabelFrame(left_frame, text="Scan Settings", padding="10")
        scan_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # Scan mode selection
        ttk.Label(scan_frame, text="Scan Mode:", font=("Arial", 9, "bold")).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0,5))
        ttk.Radiobutton(scan_frame, text="Azimuth Sweep (1D)", 
                       variable=self.scan_mode, value="azimuth",
                       command=self.update_scan_mode).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=1)
        ttk.Radiobutton(scan_frame, text="Elevation Sweep (1D)", 
                       variable=self.scan_mode, value="elevation",
                       command=self.update_scan_mode).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=1)
        ttk.Radiobutton(scan_frame, text="2D Grid (Az × El)", 
                       variable=self.scan_mode, value="2d",
                       command=self.update_scan_mode).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=1)
        
        ttk.Separator(scan_frame, orient='horizontal').grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=8)
        
        # Azimuth parameters
        ttk.Label(scan_frame, text="Azimuth Range:", font=("Arial", 9, "bold")).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(0,2))
        ttk.Label(scan_frame, text="Start:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.scan_start_az_entry = ttk.Entry(scan_frame, textvariable=self.scan_start_az, width=15)
        self.scan_start_az_entry.grid(row=6, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(scan_frame, text="Stop:").grid(row=7, column=0, sticky=tk.W, pady=2)
        self.scan_stop_az_entry = ttk.Entry(scan_frame, textvariable=self.scan_stop_az, width=15)
        self.scan_stop_az_entry.grid(row=7, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(scan_frame, text="Step:").grid(row=8, column=0, sticky=tk.W, pady=2)
        self.scan_step_az_entry = ttk.Entry(scan_frame, textvariable=self.scan_step_az, width=15)
        self.scan_step_az_entry.grid(row=8, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Separator(scan_frame, orient='horizontal').grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=8)
        
        # Elevation parameters
        ttk.Label(scan_frame, text="Elevation Range:", font=("Arial", 9, "bold")).grid(row=10, column=0, columnspan=2, sticky=tk.W, pady=(0,2))
        ttk.Label(scan_frame, text="Start:").grid(row=11, column=0, sticky=tk.W, pady=2)
        self.scan_start_el_entry = ttk.Entry(scan_frame, textvariable=self.scan_start_el, width=15, state="disabled")
        self.scan_start_el_entry.grid(row=11, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(scan_frame, text="Stop:").grid(row=12, column=0, sticky=tk.W, pady=2)
        self.scan_stop_el_entry = ttk.Entry(scan_frame, textvariable=self.scan_stop_el, width=15, state="disabled")
        self.scan_stop_el_entry.grid(row=12, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(scan_frame, text="Step:").grid(row=13, column=0, sticky=tk.W, pady=2)
        self.scan_step_el_entry = ttk.Entry(scan_frame, textvariable=self.scan_step_el, width=15, state="disabled")
        self.scan_step_el_entry.grid(row=13, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        # Fixed elevation for azimuth-only scans
        ttk.Label(scan_frame, text="Fixed El:").grid(row=14, column=0, sticky=tk.W, pady=2)
        self.scan_el_fixed_entry = ttk.Entry(scan_frame, textvariable=self.scan_el_fixed, width=15)
        self.scan_el_fixed_entry.grid(row=14, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Separator(scan_frame, orient='horizontal').grid(row=15, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=8)
        
        # Timing
        ttk.Label(scan_frame, text="Delay (sec):").grid(row=16, column=0, sticky=tk.W, pady=2)
        ttk.Entry(scan_frame, textvariable=self.scan_delay, width=15).grid(row=16, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        scan_frame.columnconfigure(1, weight=1)
        
        # ---------------------------------------------------------------
        # Control Buttons
        # ---------------------------------------------------------------
        control_frame = ttk.LabelFrame(left_frame, text="Scan Control", padding="10")
        control_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        self.start_scan_button = ttk.Button(control_frame, text="Start Scan", 
                                           command=self.start_scan)
        self.start_scan_button.grid(row=0, column=0, pady=5, padx=5, sticky=(tk.W, tk.E))
        
        self.stop_scan_button = ttk.Button(control_frame, text="Stop Scan", 
                                          command=self.stop_scan, state="disabled")
        self.stop_scan_button.grid(row=0, column=1, pady=5, padx=5, sticky=(tk.W, tk.E))
        
        ttk.Button(control_frame, text="Clear Data", 
                  command=self.clear_data).grid(row=1, column=0, pady=5, padx=5, sticky=(tk.W, tk.E))
        
        ttk.Button(control_frame, text="Save Data", 
                  command=self.save_data).grid(row=1, column=1, pady=5, padx=5, sticky=(tk.W, tk.E))
        
        ttk.Button(control_frame, text="Load Demo Data", 
                  command=self.load_demo_data).grid(row=2, column=0, columnspan=2, pady=5, padx=5, sticky=(tk.W, tk.E))
        
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        
        # ---------------------------------------------------------------
        # Status Display
        # ---------------------------------------------------------------
        status_frame = ttk.LabelFrame(left_frame, text="Status", padding="10")
        status_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        self.status_label = ttk.Label(status_frame, text="Ready", 
                                     font=("Arial", 10), foreground="blue")
        self.status_label.grid(row=0, column=0, sticky=tk.W, pady=2)
        
        ttk.Label(status_frame, text="Scan Mode:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.scan_mode_display = ttk.Label(status_frame, text="Azimuth", 
                                          font=("Arial", 10), foreground="blue")
        self.scan_mode_display.grid(row=1, column=1, sticky=tk.W, pady=2, padx=5)
        
        ttk.Label(status_frame, text="Data Points:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.data_count_var = tk.StringVar(value="0")
        ttk.Label(status_frame, textvariable=self.data_count_var, 
                 font=("Arial", 12, "bold")).grid(row=2, column=1, sticky=tk.W, pady=2, padx=5)
        
        # ---------------------------------------------------------------
        # Activity Log
        # ---------------------------------------------------------------
        log_frame = ttk.LabelFrame(left_frame, text="Activity Log", padding="10")
        log_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        row += 1
        
        self.log_text = tk.Text(log_frame, height=8, width=50, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text['yscrollcommand'] = scrollbar.set
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # ==================================================================
        # RIGHT COLUMN: Plot Display
        # ==================================================================
        
        plot_frame = ttk.LabelFrame(right_frame, text="Signal vs. Azimuth", padding="10")
        plot_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create matplotlib figure
        self.fig = Figure(figsize=(6, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel("Azimuth (steps)")
        self.ax.set_ylabel("Signal Amplitude (dB)")
        self.ax.set_title("Antenna Pattern")
        self.ax.grid(True, alpha=0.3)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)
        
        # ==================================================================
        # Configure Grid Weights for Resizing
        # ==================================================================
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=0)  # Left canvas fixed width
        main_frame.columnconfigure(1, weight=0)  # Scrollbar
        main_frame.columnconfigure(2, weight=1)  # Right column expands
        main_frame.rowconfigure(0, weight=1)
        left_frame.rowconfigure(row-1, weight=1)  # Log expands
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)
        
        self.log("GUI initialized")
    
    # ==================================================================
    # LOGGING
    # ==================================================================
    
    def log(self, message):
        """Add timestamped message to activity log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    # ==================================================================
    # MOTOR CONTROLLER FUNCTIONS
    # ==================================================================
    
    def refresh_motor_ports(self):
        """Scan for available serial ports."""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.motor_port_combo['values'] = ports
        if ports and not self.motor_port.get():
            self.motor_port.set(ports[0])
        self.log(f"Found {len(ports)} serial port(s)")
    
    def toggle_motor_connection(self):
        """Connect or disconnect from Arduino motor controller."""
        if self.motor_connected:
            self.disconnect_motor()
        else:
            self.connect_motor()
    
    def connect_motor(self):
        """Establish serial connection to Arduino."""
        try:
            self.motor_ser = serial.Serial(self.motor_port.get(), 
                                          self.motor_baudrate.get(), 
                                          timeout=2)
            time.sleep(2)  # Wait for Arduino reset
            
            # Read startup messages
            while self.motor_ser.in_waiting > 0:
                line = self.motor_ser.readline().decode('utf-8').strip()
                self.log(f"Arduino: {line}")
            
            self.motor_connected = True
            self.motor_connect_button.config(text="Disconnect Motor")
            self.log(f"Motor controller connected on {self.motor_port.get()}")
            
            # Get initial position
            self.update_motor_position()
            
        except serial.SerialException as e:
            messagebox.showerror("Motor Connection Error", 
                               f"Could not open {self.motor_port.get()}\n\n{str(e)}")
            self.log(f"Motor connection failed: {e}")
    
    def disconnect_motor(self):
        """Close motor controller serial connection."""
        if self.motor_ser and self.motor_ser.is_open:
            self.motor_ser.close()
            self.motor_connected = False
            self.motor_connect_button.config(text="Connect Motor")
            self.log("Motor controller disconnected")
    
    def send_motor_command(self, command):
        """Send command to Arduino and return response."""
        if not self.motor_connected or not self.motor_ser:
            self.log("Error: Motor controller not connected")
            return None
        
        try:
            self.motor_ser.write((command + '\n').encode('utf-8'))
            self.motor_ser.flush()
            response = self.motor_ser.readline().decode('utf-8').strip()
            return response
        except Exception as e:
            self.log(f"Motor communication error: {e}")
            return None
    
    def update_motor_position(self):
        """Query current motor positions."""
        response = self.send_motor_command("STATUS")
        if response and response.startswith("POS"):
            try:
                # Parse: "POS AZ:123 EL:456"
                parts = response.split()
                az = int(parts[1].split(':')[1])
                el = int(parts[2].split(':')[1])
                self.current_az.set(az)
                self.current_el.set(el)
            except (IndexError, ValueError) as e:
                self.log(f"Error parsing motor status: {response}")
    
    def move_azimuth_absolute(self, target_az):
        """Move azimuth to absolute position."""
        response = self.send_motor_command(f"AZABS {target_az}")
        if response and response.startswith("OK"):
            self.log(f"Moving to azimuth {target_az}")
            # Wait for movement to complete (estimate based on speed)
            time.sleep(0.5)
            self.update_motor_position()
            return True
        else:
            self.log(f"Azimuth move failed: {response}")
            return False
    
    def move_elevation_absolute(self, target_el):
        """Move elevation to absolute position."""
        response = self.send_motor_command(f"ELABS {target_el}")
        if response and response.startswith("OK"):
            self.log(f"Moving to elevation {target_el}")
            time.sleep(0.5)
            self.update_motor_position()
            return True
        else:
            self.log(f"Elevation move failed: {response}")
            return False
    
    def manual_move(self, axis, steps):
        """Manual relative movement for azimuth or elevation."""
        if not self.motor_connected:
            messagebox.showwarning("Not Connected", "Motor controller not connected")
            return
        
        if axis == 'az':
            response = self.send_motor_command(f"AZ {steps}")
            self.log(f"Azimuth relative move: {steps:+d} steps -> {response}")
        else:  # elevation
            response = self.send_motor_command(f"EL {steps}")
            self.log(f"Elevation relative move: {steps:+d} steps -> {response}")
        
        if response and response.startswith("OK"):
            time.sleep(0.3)
            self.update_motor_position()
    
    def goto_home(self):
        """Return to home position (0, 0)."""
        if not self.motor_connected:
            messagebox.showwarning("Not Connected", "Motor controller not connected")
            return
        
        response = self.send_motor_command("HOME")
        self.log(f"Homing -> {response}")
        if response and response.startswith("OK"):
            time.sleep(1.0)
            self.update_motor_position()
    
    def emergency_stop(self):
        """Emergency stop all motors."""
        if not self.motor_connected:
            return
        
        response = self.send_motor_command("STOP")
        self.log(f"EMERGENCY STOP -> {response}")
        self.update_motor_position()
    
    # ==================================================================
    # VNA FUNCTIONS
    # ==================================================================
    
    def toggle_vna_connection(self):
        """Connect or disconnect from VNA."""
        if self.vna_connected:
            self.disconnect_vna()
        else:
            self.connect_vna()
    
    def connect_vna(self):
        """Establish connection to ZNLE6 VNA."""
        try:
            rm = visa.ResourceManager("@py")
            resource = f"TCPIP0::{self.vna_ip.get()}::{self.vna_port.get()}::SOCKET"
            self.vna_inst = rm.open_resource(resource)
            self.vna_inst.timeout = 15000
            self.vna_inst.write_termination = "\n"
            self.vna_inst.read_termination = "\n"
            
            # Verify connection
            idn = self.vna_inst.query("*IDN?")
            self.log(f"VNA connected: {idn}")
            
            # Configure VNA
            self.configure_vna()
            
            self.vna_connected = True
            self.vna_connect_button.config(text="Disconnect VNA")
            
        except Exception as e:
            messagebox.showerror("VNA Connection Error", 
                               f"Could not connect to VNA\n\n{str(e)}")
            self.log(f"VNA connection failed: {e}")
    
    def disconnect_vna(self):
        """Close VNA connection."""
        if self.vna_inst:
            try:
                self.vna_inst.close()
            except:
                pass
            self.vna_connected = False
            self.vna_connect_button.config(text="Connect VNA")
            self.log("VNA disconnected")
    
    def configure_vna(self):
        """Configure VNA measurement parameters."""
        if not self.vna_connected or not self.vna_inst:
            return
        
        try:
            # Set data format to ASCII
            self.vna_inst.write("FORM:DATA ASCii")
            
            # Configure port
            self.vna_inst.write("CALC:PAR:PORT 1")
            
            # Define measurement trace
            param = self.vna_param.get()
            self.vna_inst.write(f"CALC:PAR:DEF 'Trc1',{param}")
            self.vna_inst.write("CALC:PAR:SEL 'Trc1'")
            
            # Set frequency range
            start = self.freq_start.get() if self.monitor_mode.get() == "range" else self.monitor_freq.get()
            stop = self.freq_stop.get() if self.monitor_mode.get() == "range" else self.monitor_freq.get()
            points = self.sweep_points.get() if self.monitor_mode.get() == "range" else 1
            
            self.vna_inst.write(f"SENS:FREQ:STAR {start}")
            self.vna_inst.write(f"SENS:FREQ:STOP {stop}")
            self.vna_inst.write(f"SENSe:SWEep:POINts {points}")
            
            # Set amplitude format to dB
            self.vna_inst.write("CALC:FORM MLOG")
            
            # Disable continuous sweeping
            self.vna_inst.write("INIT:CONT OFF")
            
            self.log(f"VNA configured: {param}, {start/1e6:.1f}-{stop/1e6:.1f} MHz")
            
        except Exception as e:
            self.log(f"VNA configuration error: {e}")
    
    def measure_amplitude(self):
        """
        Perform single VNA measurement and return amplitude.
        
        Returns:
            float: Amplitude in dB (single freq or peak of range)
        """
        if not self.vna_connected or not self.vna_inst:
            self.log("Error: VNA not connected")
            return None
        
        try:
            # Trigger sweep
            self.vna_inst.write("INIT")
            self.vna_inst.query("*OPC?")
            
            # Retrieve amplitude data
            data_str = self.vna_inst.query("CALC:DATA? FDATA")
            amps = [float(x) for x in data_str.strip().split(",") if x.strip()]
            
            if not amps:
                self.log("Error: No amplitude data received")
                return None
            
            # Return single value or peak
            if self.monitor_mode.get() == "single":
                return amps[0]
            else:
                # Return maximum amplitude across frequency range
                return max(amps)
            
        except Exception as e:
            self.log(f"VNA measurement error: {e}")
            return None
    
    # ==================================================================
    # FREQUENCY MODE CONTROL
    # ==================================================================
    
    def update_freq_mode(self):
        """Enable/disable frequency inputs based on selected mode."""
        if self.monitor_mode.get() == "single":
            self.single_freq_entry.config(state="normal")
            self.range_start_entry.config(state="disabled")
            self.range_stop_entry.config(state="disabled")
            self.points_entry.config(state="disabled")
        else:
            self.single_freq_entry.config(state="disabled")
            self.range_start_entry.config(state="normal")
            self.range_stop_entry.config(state="normal")
            self.points_entry.config(state="normal")
    
    # ==================================================================
    # SCAN MODE CONTROL
    # ==================================================================
    
    def update_scan_mode(self):
        """Enable/disable scan inputs based on selected scan mode."""
        mode = self.scan_mode.get()
        
        # Update status display
        mode_text = {
            "azimuth": "Azimuth (1D)",
            "elevation": "Elevation (1D)",
            "2d": "2D Grid"
        }
        self.scan_mode_display.config(text=mode_text.get(mode, mode))
        
        if mode == "azimuth":
            # Enable azimuth, disable elevation start/stop/step, enable fixed elevation
            self.scan_start_az_entry.config(state="normal")
            self.scan_stop_az_entry.config(state="normal")
            self.scan_step_az_entry.config(state="normal")
            self.scan_start_el_entry.config(state="disabled")
            self.scan_stop_el_entry.config(state="disabled")
            self.scan_step_el_entry.config(state="disabled")
            self.scan_el_fixed_entry.config(state="normal")
            
        elif mode == "elevation":
            # Disable azimuth, enable elevation, disable fixed elevation
            self.scan_start_az_entry.config(state="disabled")
            self.scan_stop_az_entry.config(state="disabled")
            self.scan_step_az_entry.config(state="disabled")
            self.scan_start_el_entry.config(state="normal")
            self.scan_stop_el_entry.config(state="normal")
            self.scan_step_el_entry.config(state="normal")
            self.scan_el_fixed_entry.config(state="disabled")
            
        else:  # 2d mode
            # Enable both azimuth and elevation, disable fixed elevation
            self.scan_start_az_entry.config(state="normal")
            self.scan_stop_az_entry.config(state="normal")
            self.scan_step_az_entry.config(state="normal")
            self.scan_start_el_entry.config(state="normal")
            self.scan_stop_el_entry.config(state="normal")
            self.scan_step_el_entry.config(state="normal")
            self.scan_el_fixed_entry.config(state="disabled")
    
    # ==================================================================
    # SCANNING FUNCTIONS
    # ==================================================================
    
    def start_scan(self):
        """Start automated azimuth scan with signal monitoring."""
        
        # Validate connections
        if not self.motor_connected:
            messagebox.showerror("Error", "Motor controller not connected")
            return
        
        if not self.vna_connected:
            messagebox.showerror("Error", "VNA not connected")
            return
        
        # Reconfigure VNA with current settings
        self.configure_vna()
        
        # Clear previous data
        self.scan_data = []
        self.update_plot()
        
        # Update UI
        self.scanning = True
        self.start_scan_button.config(state="disabled")
        self.stop_scan_button.config(state="normal")
        self.status_label.config(text="Scanning...", foreground="red")
        
        # Start scan thread
        self.scan_thread = threading.Thread(target=self.scan_worker, daemon=True)
        self.scan_thread.start()
        
        self.log("Scan started")
    
    def stop_scan(self):
        """Stop ongoing scan."""
        self.scanning = False
        self.log("Scan stopped by user")
    
    def scan_worker(self):
        """
        Worker thread for automated scanning.
        Supports azimuth, elevation, and 2D scans.
        """
        mode = self.scan_mode.get()
        delay = self.scan_delay.get()
        
        if mode == "azimuth":
            # Azimuth sweep at fixed elevation
            self.scan_azimuth_1d(delay)
        elif mode == "elevation":
            # Elevation sweep at current azimuth
            self.scan_elevation_1d(delay)
        else:  # 2d mode
            # Grid scan: azimuth x elevation
            self.scan_2d_grid(delay)
        
        # Scan complete
        self.root.after(0, self.scan_complete)
    
    def scan_azimuth_1d(self, delay):
        """Perform 1D azimuth scan at fixed elevation."""
        start_az = self.scan_start_az.get()
        stop_az = self.scan_stop_az.get()
        step_az = self.scan_step_az.get()
        fixed_el = self.scan_el_fixed.get()
        
        # Move to fixed elevation first
        self.log(f"Setting fixed elevation: {fixed_el}")
        if not self.move_elevation_absolute(fixed_el):
            self.log("Failed to set elevation, stopping scan")
            return
        
        time.sleep(delay)
        
        # Generate azimuth positions
        if step_az > 0:
            positions = range(start_az, stop_az + 1, step_az)
        else:
            self.log("Error: Step size must be positive")
            return
        
        for az_pos in positions:
            if not self.scanning:
                break
            
            # Move to azimuth position
            success = self.move_azimuth_absolute(az_pos)
            if not success:
                self.log(f"Failed to move to azimuth {az_pos}, stopping scan")
                break
            
            # Wait for settling
            time.sleep(delay)
            
            # Measure signal amplitude
            amplitude = self.measure_amplitude()
            if amplitude is not None:
                # Store data point (azimuth, elevation, amplitude)
                self.scan_data.append((az_pos, fixed_el, amplitude))
                self.log(f"Az={az_pos}, El={fixed_el}, Amp={amplitude:.2f} dB")
                
                # Update plot
                self.root.after(0, self.update_plot)
                self.root.after(0, lambda: self.data_count_var.set(str(len(self.scan_data))))
            else:
                self.log(f"Measurement failed at azimuth {az_pos}")
    
    def scan_elevation_1d(self, delay):
        """Perform 1D elevation scan at current azimuth."""
        start_el = self.scan_start_el.get()
        stop_el = self.scan_stop_el.get()
        step_el = self.scan_step_el.get()
        
        # Get current azimuth position
        self.update_motor_position()
        current_az = self.current_az.get()
        self.log(f"Elevation scan at azimuth: {current_az}")
        
        # Generate elevation positions
        if step_el > 0:
            positions = range(start_el, stop_el + 1, step_el)
        else:
            self.log("Error: Step size must be positive")
            return
        
        for el_pos in positions:
            if not self.scanning:
                break
            
            # Move to elevation position
            success = self.move_elevation_absolute(el_pos)
            if not success:
                self.log(f"Failed to move to elevation {el_pos}, stopping scan")
                break
            
            # Wait for settling
            time.sleep(delay)
            
            # Measure signal amplitude
            amplitude = self.measure_amplitude()
            if amplitude is not None:
                # Store data point (azimuth, elevation, amplitude)
                self.scan_data.append((current_az, el_pos, amplitude))
                self.log(f"Az={current_az}, El={el_pos}, Amp={amplitude:.2f} dB")
                
                # Update plot
                self.root.after(0, self.update_plot)
                self.root.after(0, lambda: self.data_count_var.set(str(len(self.scan_data))))
            else:
                self.log(f"Measurement failed at elevation {el_pos}")
    
    def scan_2d_grid(self, delay):
        """Perform 2D grid scan over azimuth and elevation."""
        start_az = self.scan_start_az.get()
        stop_az = self.scan_stop_az.get()
        step_az = self.scan_step_az.get()
        start_el = self.scan_start_el.get()
        stop_el = self.scan_stop_el.get()
        step_el = self.scan_step_el.get()
        
        # Generate position grids
        if step_az <= 0 or step_el <= 0:
            self.log("Error: Step sizes must be positive")
            return
        
        az_positions = range(start_az, stop_az + 1, step_az)
        el_positions = range(start_el, stop_el + 1, step_el)
        
        total_points = len(list(az_positions)) * len(list(el_positions))
        self.log(f"2D scan: {len(list(az_positions))} az × {len(list(el_positions))} el = {total_points} points")
        
        point_count = 0
        
        # Scan in a raster pattern: for each elevation, sweep all azimuths
        for el_pos in el_positions:
            if not self.scanning:
                break
            
            # Move to elevation position
            success = self.move_elevation_absolute(el_pos)
            if not success:
                self.log(f"Failed to move to elevation {el_pos}, stopping scan")
                break
            
            time.sleep(delay)
            
            # Sweep azimuth at this elevation
            for az_pos in az_positions:
                if not self.scanning:
                    break
                
                # Move to azimuth position
                success = self.move_azimuth_absolute(az_pos)
                if not success:
                    self.log(f"Failed to move to azimuth {az_pos}, stopping scan")
                    break
                
                # Wait for settling
                time.sleep(delay)
                
                # Measure signal amplitude
                amplitude = self.measure_amplitude()
                if amplitude is not None:
                    point_count += 1
                    # Store data point (azimuth, elevation, amplitude)
                    self.scan_data.append((az_pos, el_pos, amplitude))
                    self.log(f"[{point_count}/{total_points}] Az={az_pos}, El={el_pos}, Amp={amplitude:.2f} dB")
                    
                    # Update plot periodically (every 5 points to reduce overhead)
                    if point_count % 5 == 0:
                        self.root.after(0, self.update_plot)
                    self.root.after(0, lambda: self.data_count_var.set(str(len(self.scan_data))))
                else:
                    self.log(f"Measurement failed at Az={az_pos}, El={el_pos}")
        
        # Final plot update
        self.root.after(0, self.update_plot)
    
    def scan_complete(self):
        """Clean up after scan completion."""
        self.scanning = False
        self.start_scan_button.config(state="normal")
        self.stop_scan_button.config(state="disabled")
        self.status_label.config(text="Scan complete", foreground="green")
        self.log(f"Scan complete: {len(self.scan_data)} data points")
    
    # ==================================================================
    # DATA MANAGEMENT
    # ==================================================================
    
    def clear_data(self):
        """Clear all scan data."""
        if messagebox.askyesno("Clear Data", "Clear all scan data?"):
            self.scan_data = []
            self.data_count_var.set("0")
            self.update_plot()
            self.log("Data cleared")
    
    def load_demo_data(self):
        """Load fake demonstration data based on current scan mode."""
        import numpy as np
        
        mode = self.scan_mode.get()
        self.scan_data = []
        
        if mode == "azimuth":
            # Generate azimuth sweep demo data (Gaussian-like pattern with noise)
            start_az = self.scan_start_az.get()
            stop_az = self.scan_stop_az.get()
            step_az = self.scan_step_az.get()
            fixed_el = self.scan_el_fixed.get()
            
            azimuths = range(start_az, stop_az + 1, step_az)
            
            # Create a Gaussian-like peak at 0 degrees azimuth
            for az in azimuths:
                # Main lobe: Gaussian centered at 0 degrees
                main_lobe = -5 * np.exp(-0.002 * (az - 0)**2)
                
                # Side lobes
                side_lobe1 = -15 * np.exp(-0.001 * (az - 45)**2)
                side_lobe2 = -15 * np.exp(-0.001 * (az + 45)**2)
                
                # Noise floor around -35 dB
                noise = np.random.normal(-35, 1.5)
                
                # Combine all components
                amplitude = max(main_lobe + side_lobe1 + side_lobe2, noise)
                
                self.scan_data.append((az, fixed_el, amplitude))
            
            self.log(f"Loaded demo azimuth scan: {len(self.scan_data)} points")
        
        elif mode == "elevation":
            # Generate elevation sweep demo data
            start_el = self.scan_start_el.get()
            stop_el = self.scan_stop_el.get()
            step_el = self.scan_step_el.get()
            current_az = self.current_az.get()
            
            elevations = range(start_el, stop_el + 1, step_el)
            
            # Create a pattern with peak around 0 degrees elevation
            for el in elevations:
                # Main beam pattern
                main_beam = -8 * np.exp(-0.01 * (el - 0)**2)
                
                # Noise floor
                noise = np.random.normal(-30, 1.0)
                
                amplitude = max(main_beam, noise)
                
                self.scan_data.append((current_az, el, amplitude))
            
            self.log(f"Loaded demo elevation scan: {len(self.scan_data)} points")
        
        else:  # 2D mode
            # Generate 2D grid demo data
            start_az = self.scan_start_az.get()
            stop_az = self.scan_stop_az.get()
            step_az = self.scan_step_az.get()
            start_el = self.scan_start_el.get()
            stop_el = self.scan_stop_el.get()
            step_el = self.scan_step_el.get()
            
            azimuths = range(start_az, stop_az + 1, step_az)
            elevations = range(start_el, stop_el + 1, step_el)
            
            # Create 2D antenna pattern with main lobe and side lobes
            for az in azimuths:
                for el in elevations:
                    # Main lobe at (0, 0)
                    main_lobe = -5 * np.exp(-0.002 * az**2 - 0.01 * el**2)
                    
                    # Side lobes
                    side_lobe1 = -18 * np.exp(-0.001 * (az - 30)**2 - 0.008 * (el - 5)**2)
                    side_lobe2 = -18 * np.exp(-0.001 * (az + 30)**2 - 0.008 * (el + 5)**2)
                    
                    # Noise floor
                    noise = np.random.normal(-40, 2.0)
                    
                    amplitude = max(main_lobe + side_lobe1 + side_lobe2, noise)
                    
                    self.scan_data.append((az, el, amplitude))
            
            self.log(f"Loaded demo 2D scan: {len(self.scan_data)} points")
        
        # Update display
        self.data_count_var.set(str(len(self.scan_data)))
        self.update_plot()
        self.status_label.config(text="Demo data loaded", foreground="blue")
        
        # Update scan mode display
        mode_display = {"azimuth": "Azimuth", "elevation": "Elevation", "2d": "2D Grid"}[mode]
        self.scan_mode_display.config(text=mode_display)
    
    def save_data(self):
        """Save scan data to CSV file."""
        if not self.scan_data:
            messagebox.showwarning("No Data", "No scan data to save")
            return
        
        # Generate default filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode = self.scan_mode.get()
        default_name = f"antenna_scan_{mode}_{timestamp}.csv"
        
        # Ask user for save location
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        try:
            with open(filename, "w", encoding="utf-8") as f:
                # Write header with all three columns
                f.write("azimuth_steps,elevation_steps,amplitude_dB\n")
                for az, el, amp in self.scan_data:
                    f.write(f"{az},{el},{amp}\n")
            
            self.log(f"Data saved to {filename}")
            
            # Also save plot
            plot_filename = filename.rsplit('.', 1)[0] + '_plot.png'
            self.fig.savefig(plot_filename, dpi=150, bbox_inches='tight')
            self.log(f"Plot saved to {plot_filename}")
            
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save data:\n{str(e)}")
            self.log(f"Save error: {e}")
    
    def update_plot(self):
        """Update the plot based on scan mode."""
        self.ax.clear()
        
        if not self.scan_data:
            self.ax.set_xlabel("Position")
            self.ax.set_ylabel("Signal Amplitude (dB)")
            self.ax.set_title("Antenna Pattern")
            self.ax.grid(True, alpha=0.3)
            self.canvas.draw()
            return
        
        mode = self.scan_mode.get()
        
        # Extract data
        azimuths = [az for az, el, amp in self.scan_data]
        elevations = [el for az, el, amp in self.scan_data]
        amplitudes = [amp for az, el, amp in self.scan_data]
        
        if mode == "azimuth":
            # Plot azimuth vs amplitude
            self.ax.plot(azimuths, amplitudes, 'b-o', linewidth=2, markersize=5)
            self.ax.set_xlabel("Azimuth (steps)")
            self.ax.set_ylabel("Signal Amplitude (dB)")
            self.ax.set_title("Azimuth Pattern")
            
            # Mark peak
            if amplitudes:
                peak_idx = amplitudes.index(max(amplitudes))
                peak_az = azimuths[peak_idx]
                peak_amp = amplitudes[peak_idx]
                self.ax.plot(peak_az, peak_amp, 'r*', markersize=15, 
                           label=f'Peak: {peak_amp:.2f} dB @ Az={peak_az}')
                self.ax.legend()
        
        elif mode == "elevation":
            # Plot elevation vs amplitude
            self.ax.plot(elevations, amplitudes, 'g-o', linewidth=2, markersize=5)
            self.ax.set_xlabel("Elevation (steps)")
            self.ax.set_ylabel("Signal Amplitude (dB)")
            self.ax.set_title("Elevation Pattern")
            
            # Mark peak
            if amplitudes:
                peak_idx = amplitudes.index(max(amplitudes))
                peak_el = elevations[peak_idx]
                peak_amp = amplitudes[peak_idx]
                self.ax.plot(peak_el, peak_amp, 'r*', markersize=15, 
                           label=f'Peak: {peak_amp:.2f} dB @ El={peak_el}')
                self.ax.legend()
        
        else:  # 2d mode
            # Create 2D heatmap
            try:
                # Import numpy for 2D plotting (only needed for 2D mode)
                import numpy as np
                
                # Get unique az and el values
                unique_az = sorted(list(set(azimuths)))
                unique_el = sorted(list(set(elevations)))
                
                # Create grid
                grid = np.full((len(unique_el), len(unique_az)), np.nan)
                
                # Fill grid with data
                for az, el, amp in self.scan_data:
                    az_idx = unique_az.index(az)
                    el_idx = unique_el.index(el)
                    grid[el_idx, az_idx] = amp
                
                # Plot heatmap
                im = self.ax.imshow(grid, aspect='auto', origin='lower',
                                   extent=[min(unique_az), max(unique_az), 
                                          min(unique_el), max(unique_el)],
                                   cmap='hot', interpolation='bilinear')
                
                # Add colorbar
                self.fig.colorbar(im, ax=self.ax, label='Amplitude (dB)')
                
                # Mark peak
                if amplitudes:
                    peak_idx = amplitudes.index(max(amplitudes))
                    peak_az = azimuths[peak_idx]
                    peak_el = elevations[peak_idx]
                    peak_amp = amplitudes[peak_idx]
                    self.ax.plot(peak_az, peak_el, 'c*', markersize=15, 
                               markeredgecolor='white', markeredgewidth=1.5,
                               label=f'Peak: {peak_amp:.2f} dB')
                    self.ax.legend()
                
                self.ax.set_xlabel("Azimuth (steps)")
                self.ax.set_ylabel("Elevation (steps)")
                self.ax.set_title("2D Antenna Pattern")
                
            except ImportError:
                # Fallback: just plot points
                scatter = self.ax.scatter(azimuths, elevations, c=amplitudes, 
                                        cmap='hot', s=50, edgecolors='black', linewidth=0.5)
                self.fig.colorbar(scatter, ax=self.ax, label='Amplitude (dB)')
                self.ax.set_xlabel("Azimuth (steps)")
                self.ax.set_ylabel("Elevation (steps)")
                self.ax.set_title("2D Antenna Pattern")
        
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()


def main():
    """Main entry point."""
    root = tk.Tk()
    app = AntennaAlignerGUI(root)
    
    def on_closing():
        """Handle window close event."""
        if app.scanning:
            if not messagebox.askokcancel("Scan In Progress", 
                                         "A scan is in progress. Stop and quit?"):
                return
            app.scanning = False
        
        # Disconnect devices
        if app.motor_connected:
            app.disconnect_motor()
        if app.vna_connected:
            app.disconnect_vna()
        
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
