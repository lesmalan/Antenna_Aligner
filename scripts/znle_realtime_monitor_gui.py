#!/usr/bin/env python3
"""
GUI for ZNLE6 Real-Time Signal Monitor

Provides graphical interface for continuous signal monitoring with live plot.
Displays amplitude vs time for a target frequency in real-time.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import os
import sys
from datetime import datetime


class RealtimeMonitorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ZNLE6 Real-Time Signal Monitor")
        self.root.geometry("600x550")
        
        # Default parameters
        self.ip = tk.StringVar(value="192.168.15.90")
        self.port = tk.StringVar(value="5025")
        self.target_freq = tk.StringVar(value="977e6")
        self.param = tk.StringVar(value="S21")
        self.interval = tk.StringVar(value="500")
        self.smoothing_window = tk.StringVar(value="10")
        
        # Set default directories
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_dir = os.path.join(base_dir, "CSVs")
        plots_dir = os.path.join(base_dir, "Plots")
        os.makedirs(csv_dir, exist_ok=True)
        os.makedirs(plots_dir, exist_ok=True)
        
        self.csv_directory = tk.StringVar(value=csv_dir)
        self.plots_directory = tk.StringVar(value=plots_dir)
        self.filename = tk.StringVar(value="realtime_monitor")
        
        self.running = False
        self.process = None
        
        self.create_widgets()
    
    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        row = 0
        
        # Title
        title_label = ttk.Label(main_frame, text="ZNLE6 Real-Time Signal Monitor", 
                                font=('Arial', 14, 'bold'))
        title_label.grid(row=row, column=0, columnspan=2, pady=(0, 15))
        row += 1
        
        # Connection Settings
        conn_frame = ttk.LabelFrame(main_frame, text="Connection Settings", padding="10")
        conn_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        ttk.Label(conn_frame, text="ZNLE6 IP Address:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(conn_frame, textvariable=self.ip, width=20).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2, sticky=tk.W, pady=2, padx=(10, 0))
        ttk.Entry(conn_frame, textvariable=self.port, width=10).grid(row=0, column=3, sticky=tk.W, pady=2, padx=5)
        
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
        ttk.Entry(dir_frame, textvariable=self.csv_directory, width=35).pack(side=tk.LEFT)
        ttk.Button(dir_frame, text="Browse...", command=self.browse_csv_dir, width=8).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(output_frame, text="Filename:").grid(row=1, column=0, sticky=tk.W, pady=2)
        filename_frame = ttk.Frame(output_frame)
        filename_frame.grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Entry(filename_frame, textvariable=self.filename, width=25).pack(side=tk.LEFT)
        ttk.Label(filename_frame, text="(without extension)").pack(side=tk.LEFT, padx=5)
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=15)
        row += 1
        
        self.start_button = ttk.Button(button_frame, text="Start Real-Time Monitor", 
                                       command=self.start_monitor, width=25)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop", 
                                      command=self.stop_monitor, state=tk.DISABLED, width=15)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Help", command=self.show_help, width=10).pack(side=tk.LEFT, padx=5)
        
        # Status
        self.status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        row += 1
        
        # Info text
        info_frame = ttk.LabelFrame(main_frame, text="Information", padding="10")
        info_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        info_text = tk.Text(info_frame, height=6, width=65, wrap=tk.WORD)
        info_text.insert(1.0, 
            "This tool continuously monitors signal amplitude at a target frequency.\n\n"
            "• A live plot window will open showing amplitude vs time\n"
            "• Data is continuously saved to CSV\n"
            "• Close the plot window or click Stop to end monitoring\n"
            "• Use S21 for transmission measurements (two antennas)\n"
            "• Use S11/S22 for reflection measurements (single antenna)\n"
            "• Smoothing reduces noise by averaging multiple samples")
        info_text.config(state=tk.DISABLED)
        info_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
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
        script_path = os.path.join(script_dir, "znle_realtime_monitor.py")
        
        cmd = [sys.executable, script_path]
        cmd.extend(["--ip", self.ip.get()])
        cmd.extend(["--port", self.port.get()])
        cmd.extend(["--freq", self.target_freq.get()])
        cmd.extend(["--param", self.param.get()])
        cmd.extend(["--csv-dir", self.csv_directory.get()])
        cmd.extend(["--filename", self.filename.get()])
        cmd.extend(["--interval", self.interval.get()])
        cmd.extend(["--smoothing", self.smoothing_window.get()])
        
        return cmd
    
    def start_monitor(self):
        """Start the real-time monitor"""
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
    
    def show_help(self):
        """Show help dialog"""
        help_text = """ZNLE6 Real-Time Signal Monitor

This tool continuously monitors signal amplitude at a single target frequency
and displays results in a live-updating plot.

FEATURES:
• Live plot showing amplitude vs time
• Continuous CSV data logging
• Configurable S-parameter selection
• Adjustable update rate

SETUP:
1. Enter ZNLE6 IP address and port
2. Specify target frequency in Hz (e.g., 977e6 = 977 MHz)
3. Select S-parameter:
   - S21: Transmission from port 1 to port 2 (two antennas)
   - S11: Reflection at port 1
   - S22: Reflection at port 2
4. Set update interval (500ms = 2 updates/second)
5. Choose output directory and filename

USAGE:
• Click "Start Real-Time Monitor" to begin
• A plot window will open with live data
• Monitor continues until you close the plot window or click Stop
• Data is saved to CSV throughout monitoring

S-PARAMETER GUIDE:
• S21: Best for antenna-to-antenna transmission testing
• S22: Good for single-antenna reception monitoring
• S11: For transmitter reflection measurements

TIPS:
• Faster update intervals (100-500ms) for dynamic signals
• Slower intervals (1000-2000ms) for stable signals
• CSV file contains all data points with timestamps
"""
        
        help_window = tk.Toplevel(self.root)
        help_window.title("Help - Real-Time Monitor")
        help_window.geometry("650x600")
        
        text_widget = tk.Text(help_window, wrap=tk.WORD, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(help_window, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.insert(1.0, help_text)
        text_widget.config(state=tk.DISABLED)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)


def main():
    root = tk.Tk()
    app = RealtimeMonitorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
