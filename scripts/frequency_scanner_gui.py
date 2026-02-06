#!/usr/bin/env python3
"""
GUI for ZNLE6 Quiet Frequency Scanner
Helps identify quiet RF bands for transmission experiments
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import os
import sys
from datetime import datetime


class FrequencyScannerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ZNLE6 Quiet Frequency Scanner")
        self.root.geometry("700x850")
        
        # Default parameters
        self.ip = tk.StringVar(value="192.168.15.90")
        self.port = tk.StringVar(value="5025")
        
        # Frequency mode
        self.freq_mode = tk.StringVar(value="center_span")
        
        # Center/Span mode
        self.center_freq = tk.StringVar(value="900e6")
        self.span_freq = tk.StringVar(value="200e6")
        
        # Start/Stop mode
        self.start_freq = tk.StringVar(value="800e6")
        self.stop_freq = tk.StringVar(value="1000e6")
        
        # Scan parameters
        self.points = tk.StringVar(value="401")
        self.receiver_port = tk.StringVar(value="1")
        self.threshold_db = tk.StringVar(value="5.0")
        self.min_bandwidth = tk.StringVar(value="10.0")
        
        # Options
        self.save_csv = tk.BooleanVar(value=True)
        
        # Set default directories
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_dir = os.path.join(base_dir, "CSVs")
        plots_dir = os.path.join(base_dir, "Plots")
        os.makedirs(csv_dir, exist_ok=True)
        os.makedirs(plots_dir, exist_ok=True)
        
        self.csv_directory = tk.StringVar(value=csv_dir)
        self.plots_directory = tk.StringVar(value=plots_dir)
        
        self.running = False
        self.process = None
        
        self.create_widgets()
    
    def create_widgets(self):
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        row = 0
        
        # Title
        title_label = ttk.Label(main_frame, text="ZNLE6 Quiet Frequency Band Scanner", 
                                font=('Arial', 14, 'bold'))
        title_label.grid(row=row, column=0, columnspan=2, pady=(0, 15))
        row += 1
        
        # Connection Settings
        ttk.Label(main_frame, text="Connection Settings", 
                  font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(5, 5))
        row += 1
        
        ttk.Label(main_frame, text="ZNLE6 IP Address:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(main_frame, textvariable=self.ip, width=30).grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1
        
        ttk.Label(main_frame, text="Port:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(main_frame, textvariable=self.port, width=30).grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1
        
        ttk.Label(main_frame, text="Receiver Port:").grid(row=row, column=0, sticky=tk.W, pady=2)
        port_frame = ttk.Frame(main_frame)
        port_frame.grid(row=row, column=1, sticky=tk.W, pady=2)
        ttk.Radiobutton(port_frame, text="Port 1", variable=self.receiver_port, 
                        value="1").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(port_frame, text="Port 2", variable=self.receiver_port, 
                        value="2").pack(side=tk.LEFT, padx=5)
        row += 1
        
        # Separator
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, 
                                                              sticky=(tk.W, tk.E), pady=10)
        row += 1
        
        # Frequency Settings
        ttk.Label(main_frame, text="Frequency Settings", 
                  font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(5, 5))
        row += 1
        
        # Frequency mode selection
        mode_frame = ttk.Frame(main_frame)
        mode_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Radiobutton(mode_frame, text="Center + Span", variable=self.freq_mode, 
                        value="center_span", command=self.update_freq_mode).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(mode_frame, text="Start + Stop", variable=self.freq_mode, 
                        value="start_stop", command=self.update_freq_mode).pack(side=tk.LEFT, padx=10)
        row += 1
        
        # Center/Span frame
        self.center_span_frame = ttk.LabelFrame(main_frame, text="Center + Span Mode", padding="5")
        self.center_span_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(self.center_span_frame, text="Center Frequency (Hz):").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.center_span_frame, textvariable=self.center_freq, width=25).grid(row=0, column=1, sticky=tk.W, pady=2, padx=5)
        ttk.Label(self.center_span_frame, text="e.g., 900e6 = 900 MHz").grid(row=0, column=2, sticky=tk.W, pady=2)
        
        ttk.Label(self.center_span_frame, text="Span (Hz):").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.center_span_frame, textvariable=self.span_freq, width=25).grid(row=1, column=1, sticky=tk.W, pady=2, padx=5)
        ttk.Label(self.center_span_frame, text="e.g., 200e6 = 200 MHz").grid(row=1, column=2, sticky=tk.W, pady=2)
        
        row += 1
        
        # Start/Stop frame
        self.start_stop_frame = ttk.LabelFrame(main_frame, text="Start + Stop Mode", padding="5")
        self.start_stop_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(self.start_stop_frame, text="Start Frequency (Hz):").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.start_stop_frame, textvariable=self.start_freq, width=25).grid(row=0, column=1, sticky=tk.W, pady=2, padx=5)
        ttk.Label(self.start_stop_frame, text="e.g., 800e6 = 800 MHz").grid(row=0, column=2, sticky=tk.W, pady=2)
        
        ttk.Label(self.start_stop_frame, text="Stop Frequency (Hz):").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.start_stop_frame, textvariable=self.stop_freq, width=25).grid(row=1, column=1, sticky=tk.W, pady=2, padx=5)
        ttk.Label(self.start_stop_frame, text="e.g., 1000e6 = 1 GHz").grid(row=1, column=2, sticky=tk.W, pady=2)
        
        row += 1
        
        # Quick presets
        preset_frame = ttk.Frame(main_frame)
        preset_frame.grid(row=row, column=0, columnspan=2, pady=10)
        ttk.Label(preset_frame, text="Quick Presets:").pack(side=tk.LEFT, padx=5)
        ttk.Button(preset_frame, text="900 MHz ±100 MHz", 
                   command=lambda: self.apply_preset(900e6, 200e6)).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="2.4 GHz ±100 MHz", 
                   command=lambda: self.apply_preset(2.4e9, 200e6)).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="5 GHz ±200 MHz", 
                   command=lambda: self.apply_preset(5e9, 400e6)).pack(side=tk.LEFT, padx=2)
        row += 1
        
        # Separator
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, 
                                                              sticky=(tk.W, tk.E), pady=10)
        row += 1
        
        # Scan Parameters
        ttk.Label(main_frame, text="Scan Parameters", 
                  font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(5, 5))
        row += 1
        
        ttk.Label(main_frame, text="Number of Points:").grid(row=row, column=0, sticky=tk.W, pady=2)
        points_frame = ttk.Frame(main_frame)
        points_frame.grid(row=row, column=1, sticky=tk.W, pady=2)
        ttk.Entry(points_frame, textvariable=self.points, width=15).pack(side=tk.LEFT)
        ttk.Label(points_frame, text="(more points = better resolution, slower scan)").pack(side=tk.LEFT, padx=5)
        row += 1
        
        ttk.Label(main_frame, text="Quiet Threshold (dB):").grid(row=row, column=0, sticky=tk.W, pady=2)
        threshold_frame = ttk.Frame(main_frame)
        threshold_frame.grid(row=row, column=1, sticky=tk.W, pady=2)
        ttk.Entry(threshold_frame, textvariable=self.threshold_db, width=15).pack(side=tk.LEFT)
        ttk.Label(threshold_frame, text="dB below median noise").pack(side=tk.LEFT, padx=5)
        row += 1
        
        ttk.Label(main_frame, text="Min Bandwidth (MHz):").grid(row=row, column=0, sticky=tk.W, pady=2)
        bw_frame = ttk.Frame(main_frame)
        bw_frame.grid(row=row, column=1, sticky=tk.W, pady=2)
        ttk.Entry(bw_frame, textvariable=self.min_bandwidth, width=15).pack(side=tk.LEFT)
        ttk.Label(bw_frame, text="minimum width for a quiet band").pack(side=tk.LEFT, padx=5)
        row += 1
        
        # Separator
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, 
                                                              sticky=(tk.W, tk.E), pady=10)
        row += 1
        
        # Output Options
        ttk.Label(main_frame, text="Output Options", 
                  font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(5, 5))
        row += 1
        
        ttk.Checkbutton(main_frame, text="Save CSV data", 
                        variable=self.save_csv).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        row += 1
        
        # Directory settings
        ttk.Label(main_frame, text="CSV Directory:").grid(row=row, column=0, sticky=tk.W, pady=2)
        dir_frame = ttk.Frame(main_frame)
        dir_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        ttk.Entry(dir_frame, textvariable=self.csv_directory, width=30).pack(side=tk.LEFT)
        ttk.Button(dir_frame, text="Browse...", command=self.browse_csv_dir, width=8).pack(side=tk.LEFT, padx=5)
        row += 1
        
        ttk.Label(main_frame, text="Plots Directory:").grid(row=row, column=0, sticky=tk.W, pady=2)
        dir_frame2 = ttk.Frame(main_frame)
        dir_frame2.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        ttk.Entry(dir_frame2, textvariable=self.plots_directory, width=30).pack(side=tk.LEFT)
        ttk.Button(dir_frame2, text="Browse...", command=self.browse_plots_dir, width=8).pack(side=tk.LEFT, padx=5)
        row += 1
        
        # Separator
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, 
                                                              sticky=(tk.W, tk.E), pady=10)
        row += 1
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=10)
        
        self.scan_button = ttk.Button(button_frame, text="Start Scan", 
                                       command=self.start_scan, width=15)
        self.scan_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop", 
                                       command=self.stop_scan, state=tk.DISABLED, width=15)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Help", command=self.show_help, width=15).pack(side=tk.LEFT, padx=5)
        row += 1
        
        # Status
        self.status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        row += 1
        
        # Output text area
        output_frame = ttk.LabelFrame(main_frame, text="Scan Output", padding="5")
        output_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.output_text = tk.Text(output_frame, height=10, width=80, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=scrollbar.set)
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(row, weight=1)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        
        # Initialize frequency mode
        self.update_freq_mode()
    
    def update_freq_mode(self):
        """Update which frequency input frame is active"""
        if self.freq_mode.get() == "center_span":
            self.center_span_frame.config(relief=tk.SOLID, borderwidth=2)
            self.start_stop_frame.config(relief=tk.FLAT, borderwidth=1)
        else:
            self.center_span_frame.config(relief=tk.FLAT, borderwidth=1)
            self.start_stop_frame.config(relief=tk.SOLID, borderwidth=2)
    
    def apply_preset(self, center, span):
        """Apply a frequency preset"""
        self.freq_mode.set("center_span")
        self.center_freq.set(f"{center:.0f}")
        self.span_freq.set(f"{span:.0f}")
        self.update_freq_mode()
    
    def browse_csv_dir(self):
        directory = filedialog.askdirectory(initialdir=self.csv_directory.get())
        if directory:
            self.csv_directory.set(directory)
    
    def browse_plots_dir(self):
        directory = filedialog.askdirectory(initialdir=self.plots_directory.get())
        if directory:
            self.plots_directory.set(directory)
    
    def build_command(self):
        """Build the command line for find_quiet_frequencies.py"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "find_quiet_frequencies.py")
        
        cmd = [sys.executable, script_path]
        cmd.extend(["--ip", self.ip.get()])
        cmd.extend(["--port", self.port.get()])
        
        # Frequency settings
        if self.freq_mode.get() == "center_span":
            cmd.extend(["--center", self.center_freq.get()])
            cmd.extend(["--span", self.span_freq.get()])
        else:
            cmd.extend(["--start", self.start_freq.get()])
            cmd.extend(["--stop", self.stop_freq.get()])
        
        # Scan parameters
        cmd.extend(["--points", self.points.get()])
        cmd.extend(["--receiver-port", self.receiver_port.get()])
        cmd.extend(["--threshold-db", self.threshold_db.get()])
        cmd.extend(["--min-bandwidth", self.min_bandwidth.get()])
        
        # Output options
        if self.save_csv.get():
            cmd.append("--save-csv")
        
        return cmd
    
    def start_scan(self):
        """Start the frequency scan"""
        if self.running:
            return
        
        try:
            # Validate inputs
            float(self.center_freq.get()) if self.freq_mode.get() == "center_span" else float(self.start_freq.get())
            float(self.span_freq.get()) if self.freq_mode.get() == "center_span" else float(self.stop_freq.get())
            int(self.points.get())
            float(self.threshold_db.get())
            float(self.min_bandwidth.get())
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please check your input values:\n{e}")
            return
        
        # Clear output
        self.output_text.delete(1.0, tk.END)
        
        # Change to output directories
        os.chdir(self.csv_directory.get())
        
        # Build and run command
        cmd = self.build_command()
        
        self.output_text.insert(tk.END, f"Running: {' '.join(cmd)}\n\n")
        self.output_text.see(tk.END)
        
        self.running = True
        self.scan_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_label.config(text="Scanning...")
        
        # Run in thread
        thread = threading.Thread(target=self.run_scan, args=(cmd,), daemon=True)
        thread.start()
    
    def run_scan(self, cmd):
        """Run the scan in a separate thread"""
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Read output line by line
            for line in self.process.stdout:
                self.root.after(0, self.append_output, line)
            
            self.process.wait()
            return_code = self.process.returncode
            
            if return_code == 0:
                self.root.after(0, self.scan_complete, True)
            else:
                self.root.after(0, self.scan_complete, False)
        
        except Exception as e:
            self.root.after(0, self.append_output, f"\nError: {e}\n")
            self.root.after(0, self.scan_complete, False)
    
    def append_output(self, text):
        """Append text to output area (called from main thread)"""
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
    
    def scan_complete(self, success):
        """Called when scan completes"""
        self.running = False
        self.scan_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        if success:
            self.status_label.config(text="Scan complete!")
            messagebox.showinfo("Scan Complete", "Frequency scan completed successfully!\nCheck the plot window for results.")
        else:
            self.status_label.config(text="Scan failed")
            messagebox.showerror("Scan Failed", "The scan encountered an error. Check the output for details.")
    
    def stop_scan(self):
        """Stop the running scan"""
        if self.process:
            self.process.terminate()
            self.append_output("\n\n=== Scan stopped by user ===\n")
            self.scan_complete(False)
    
    def show_help(self):
        """Show help dialog"""
        help_text = """ZNLE6 Quiet Frequency Scanner

This tool scans for quiet (low-noise) frequency bands that are ideal for RF transmission experiments.

HOW IT WORKS:
1. The ZNLE6 VNA measures background RF noise across a frequency range
2. The script identifies frequency bands with low noise levels
3. Results are displayed graphically and can be saved to CSV

PARAMETERS:
- Center + Span: Define range by center frequency and total span
- Start + Stop: Define range by start and stop frequencies  
- Points: More points = better resolution (but slower scan)
- Quiet Threshold: How many dB below median noise = "quiet"
- Min Bandwidth: Minimum width in MHz for a quiet band

TIPS:
- Start with a wide scan (e.g., 800-1000 MHz) to find quietest regions
- Use Quick Presets for common frequency bands
- Higher point counts (401-801) give better detail
- Check that Pasco receiver is connected to correct VNA port

OUTPUT:
- Plot shows noise floor with quiet bands highlighted in green
- CSV contains frequency vs. power data for further analysis
- Script recommends best frequency for your transmission
"""
        
        help_window = tk.Toplevel(self.root)
        help_window.title("Help")
        help_window.geometry("600x500")
        
        text_widget = tk.Text(help_window, wrap=tk.WORD, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(help_window, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.insert(1.0, help_text)
        text_widget.config(state=tk.DISABLED)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)


def main():
    root = tk.Tk()
    app = FrequencyScannerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
