#!/usr/bin/env python3
"""
GUI for R&S ZNLE6 control via PyVISA over TCP/IP.
Provides easy access to frequency sweep and monitoring modes.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import os
import time
from datetime import datetime


class ZNLE_GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ZNLE6 Spectrum Analyzer Control")
        self.root.geometry("750x750")
        
        # Default parameters
        self.ip = tk.StringVar(value="192.168.15.90")
        self.port = tk.StringVar(value="5025")
        self.start_freq = tk.StringVar(value="900e6")
        self.stop_freq = tk.StringVar(value="1500e6")
        self.points = tk.StringVar(value="201")
        self.param = tk.StringVar(value="S11")
        self.sweep_time = tk.StringVar(value="")
        self.monitor_freq = tk.StringVar(value="900e6")
        self.monitor_duration = tk.StringVar(value="60")
        self.monitor_interval = tk.StringVar(value="1.0")
        
        # Set default directories and filename
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_dir = os.path.join(base_dir, "CSVs")
        plots_dir = os.path.join(base_dir, "Plots")
        os.makedirs(csv_dir, exist_ok=True)
        os.makedirs(plots_dir, exist_ok=True)
        
        self.csv_directory = tk.StringVar(value=csv_dir)
        self.plots_directory = tk.StringVar(value=plots_dir)
        self.filename = tk.StringVar(value="trace")
        
        self.running = False
        self.process = None
        self.monitor_start_time = None
        self.timer_update_id = None
        
        self.create_widgets()
    
    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title = ttk.Label(main_frame, text="ZNLE6 Spectrum Analyzer Control", 
                         font=("Arial", 16, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=10)
        
        # Connection settings frame
        conn_frame = ttk.LabelFrame(main_frame, text="Connection Settings", padding="10")
        conn_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(conn_frame, text="IP Address:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(conn_frame, textvariable=self.ip, width=20).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2, sticky=tk.W, pady=2, padx=(10, 0))
        ttk.Entry(conn_frame, textvariable=self.port, width=10).grid(row=0, column=3, sticky=tk.W, pady=2, padx=5)
        
        # Measurement settings frame
        meas_frame = ttk.LabelFrame(main_frame, text="Measurement Settings", padding="10")
        meas_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(meas_frame, text="Start Freq (Hz):").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(meas_frame, textvariable=self.start_freq, width=15).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(meas_frame, text="Stop Freq (Hz):").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(meas_frame, textvariable=self.stop_freq, width=15).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(meas_frame, text="Points:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(meas_frame, textvariable=self.points, width=15).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(meas_frame, text="Parameter:").grid(row=3, column=0, sticky=tk.W, pady=2)
        param_combo = ttk.Combobox(meas_frame, textvariable=self.param, 
                                   values=["S11", "S21", "S12", "S22"], width=13, state="readonly")
        param_combo.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(meas_frame, text="Sweep Time (s):").grid(row=4, column=0, sticky=tk.W, pady=2)
        ttk.Entry(meas_frame, textvariable=self.sweep_time, width=15).grid(row=4, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        ttk.Label(meas_frame, text="(optional)").grid(row=4, column=2, sticky=tk.W, pady=2, padx=5)
        
        # Monitor settings frame
        monitor_frame = ttk.LabelFrame(main_frame, text="Monitor Mode Settings", padding="10")
        monitor_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(monitor_frame, text="Monitor Freq (Hz):").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(monitor_frame, textvariable=self.monitor_freq, width=15).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(monitor_frame, text="Duration (s):").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(monitor_frame, textvariable=self.monitor_duration, width=15).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        ttk.Label(monitor_frame, text="Interval (s):").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(monitor_frame, textvariable=self.monitor_interval, width=15).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        # Output settings frame
        output_frame = ttk.LabelFrame(main_frame, text="Output Settings", padding="10")
        output_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(output_frame, text="CSV Directory:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(output_frame, textvariable=self.csv_directory, width=35).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        ttk.Button(output_frame, text="Browse...", command=self.browse_csv_dir).grid(row=0, column=2, pady=2, padx=5)
        
        ttk.Label(output_frame, text="Plots Directory:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(output_frame, textvariable=self.plots_directory, width=35).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        ttk.Button(output_frame, text="Browse...", command=self.browse_plots_dir).grid(row=1, column=2, pady=2, padx=5)
        
        ttk.Label(output_frame, text="Filename:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(output_frame, textvariable=self.filename, width=35).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        ttk.Label(output_frame, text="(without extension)").grid(row=2, column=2, sticky=tk.W, pady=2, padx=5)
        
        # Action buttons frame
        button_frame = ttk.Frame(main_frame, padding="10")
        button_frame.grid(row=5, column=0, columnspan=2, pady=10)
        
        self.freq_button = ttk.Button(button_frame, text="Run Frequency Mode", 
                                      command=self.run_frequency_mode, width=25)
        self.freq_button.grid(row=0, column=0, padx=5, pady=5)
        
        self.monitor_button = ttk.Button(button_frame, text="Run Monitor Mode", 
                                        command=self.run_monitor_mode, width=25)
        self.monitor_button.grid(row=0, column=1, padx=5, pady=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop", 
                                      command=self.stop_measurement, width=15, state=tk.DISABLED)
        self.stop_button.grid(row=1, column=0, columnspan=2, pady=5)
        
        # Timer display for monitor mode (using tk.Label for color support)
        self.timer_label = tk.Label(button_frame, text="", font=("Arial", 12, "bold"), fg="blue")
        self.timer_label.grid(row=2, column=0, columnspan=2, pady=5)
        
        # Status display
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.status_text = tk.Text(status_frame, height=10, width=70, wrap=tk.WORD)
        self.status_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=self.status_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.status_text['yscrollcommand'] = scrollbar.set
        
        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(6, weight=1)
        status_frame.columnconfigure(0, weight=1)
        status_frame.rowconfigure(0, weight=1)
    
    def log_status(self, message):
        """Add a message to the status display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.root.update_idletasks()
    
    def browse_csv_dir(self):
        """Open directory dialog to select CSV output directory."""
        directory = filedialog.askdirectory(
            initialdir=self.csv_directory.get(),
            title="Select CSV Output Directory"
        )
        if directory:
            self.csv_directory.set(directory)
    
    def browse_plots_dir(self):
        """Open directory dialog to select Plots output directory."""
        directory = filedialog.askdirectory(
            initialdir=self.plots_directory.get(),
            title="Select Plots Output Directory"
        )
        if directory:
            self.plots_directory.set(directory)
    
    def build_command(self, monitor_mode=False):
        """Build the command line for running znle_pyvisa.py."""
        script_path = os.path.join(os.path.dirname(__file__), "znle_pyvisa.py")
        
        # Use the virtual environment Python if it exists
        venv_python = "/home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner/.venv/bin/python"
        python_cmd = venv_python if os.path.exists(venv_python) else "python3"
        
        # Construct full output path from directory and filename
        csv_path = os.path.join(self.csv_directory.get(), self.filename.get() + ".csv")
        
        # Set environment variable for plots directory so script can find it
        os.environ['PLOTS_DIR'] = self.plots_directory.get()
        
        cmd = [
            python_cmd, script_path,
            "--ip", self.ip.get(),
            "--port", self.port.get(),
            "--start", self.start_freq.get(),
            "--stop", self.stop_freq.get(),
            "--points", self.points.get(),
            "--param", self.param.get(),
            "--out", csv_path,
            "--plot"
        ]
        
        if self.sweep_time.get().strip():
            cmd.extend(["--sweep-time", self.sweep_time.get()])
        
        if monitor_mode:
            cmd.extend([
                "--monitor",
                "--monitor-freq", self.monitor_freq.get(),
                "--duration", self.monitor_duration.get(),
                "--interval", self.monitor_interval.get()
            ])
        
        return cmd
    
    def run_command_thread(self, cmd):
        """Run the command in a separate thread."""
        try:
            # Log the command being executed
            self.root.after(0, self.log_status, f"Command: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            # Read output line by line from both stdout and stderr
            import select
            while True:
                if not self.running:
                    break
                
                # Read from stdout
                line = self.process.stdout.readline()
                if line:
                    self.root.after(0, self.log_status, line.strip())
                
                # Check if process has finished
                if self.process.poll() is not None:
                    # Read any remaining output
                    remaining_out = self.process.stdout.read()
                    remaining_err = self.process.stderr.read()
                    if remaining_out:
                        for line in remaining_out.strip().split('\n'):
                            if line:
                                self.root.after(0, self.log_status, line)
                    if remaining_err:
                        for line in remaining_err.strip().split('\n'):
                            if line:
                                self.root.after(0, self.log_status, f"ERROR: {line}")
                    break
            
            self.process.wait()
            
            if self.process.returncode == 0:
                self.root.after(0, self.log_status, "✓ Measurement completed successfully!")
                csv_path = os.path.join(self.csv_directory.get(), self.filename.get() + ".csv")
                plots_path = os.path.join(self.plots_directory.get(), self.filename.get() + "_plot.png")
                
                # Open the plot automatically
                try:
                    subprocess.Popen(["xdg-open", plots_path])
                except Exception as e:
                    self.root.after(0, self.log_status, f"Could not auto-open plot: {e}")
                
                self.root.after(0, messagebox.showinfo, "Success", 
                              f"Measurement completed!\nCSV: {csv_path}\nPlot: {plots_path}")
            elif self.running:  # Only show error if not manually stopped
                # Read stderr for error details
                stderr_output = self.process.stderr.read() if self.process.stderr else ""
                self.root.after(0, self.log_status, f"✗ Process exited with code {self.process.returncode}")
                if stderr_output:
                    self.root.after(0, self.log_status, f"Error details: {stderr_output}")
                error_msg = f"Measurement failed with exit code {self.process.returncode}"
                if stderr_output:
                    error_msg += f"\n\nError details:\n{stderr_output}"
                self.root.after(0, messagebox.showerror, "Error", error_msg)
        
        except Exception as e:
            self.root.after(0, self.log_status, f"✗ Error: {str(e)}")
            self.root.after(0, messagebox.showerror, "Error", f"Failed to run measurement:\n{str(e)}")
        
        finally:
            self.root.after(0, self.measurement_finished)
    
    def run_frequency_mode(self):
        """Run frequency sweep mode."""
        if self.running:
            messagebox.showwarning("Warning", "A measurement is already running!")
            return
        
        self.log_status("=" * 60)
        self.log_status("Starting Frequency Sweep Mode...")
        self.log_status(f"Frequency range: {self.start_freq.get()} - {self.stop_freq.get()} Hz")
        self.log_status(f"Points: {self.points.get()}, Parameter: {self.param.get()}")
        self.log_status("=" * 60)
        
        cmd = self.build_command(monitor_mode=False)
        self.running = True
        self.freq_button.config(state=tk.DISABLED)
        self.monitor_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        thread = threading.Thread(target=self.run_command_thread, args=(cmd,), daemon=True)
        thread.start()
    
    def run_monitor_mode(self):
        """Run monitor mode."""
        if self.running:
            messagebox.showwarning("Warning", "A measurement is already running!")
            return
        
        self.log_status("=" * 60)
        self.log_status("Starting Monitor Mode...")
        self.log_status(f"Monitor frequency: {self.monitor_freq.get()} Hz")
        self.log_status(f"Duration: {self.monitor_duration.get()} s, Interval: {self.monitor_interval.get()} s")
        self.log_status("=" * 60)
        
        cmd = self.build_command(monitor_mode=True)
        self.running = True
        self.monitor_start_time = time.time()
        self.freq_button.config(state=tk.DISABLED)
        self.monitor_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Start the countdown timer
        self.log_status(f"Starting countdown timer for {self.monitor_duration.get()} seconds")
        self.update_countdown_timer()
        
        thread = threading.Thread(target=self.run_command_thread, args=(cmd,), daemon=True)
        thread.start()
    
    def stop_measurement(self):
        """Stop the running measurement."""
        if self.process and self.running:
            self.log_status("Stopping measurement...")
            self.running = False
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                self.process.kill()
            self.log_status("✓ Measurement stopped by user")
    
    def measurement_finished(self):
        """Re-enable buttons after measurement finishes."""
        self.running = False
        self.monitor_start_time = None
        self.freq_button.config(state=tk.NORMAL)
        self.monitor_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.timer_label.config(text="")
        
        # Cancel any pending timer updates
        if self.timer_update_id:
            self.root.after_cancel(self.timer_update_id)
            self.timer_update_id = None


    def update_countdown_timer(self):
        """Update the countdown timer display."""
        if self.monitor_start_time and self.running:
            try:
                duration = float(self.monitor_duration.get())
                elapsed = time.time() - self.monitor_start_time
                remaining = max(0, duration - elapsed)
                
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                
                if remaining > 0:
                    timer_text = f"Time Remaining: {minutes:02d}:{seconds:02d}"
                    self.timer_label.config(text=timer_text)
                    self.timer_label.update_idletasks()  # Force display update
                    # Schedule next update in 1 second
                    self.timer_update_id = self.root.after(1000, self.update_countdown_timer)
                else:
                    self.timer_label.config(text="Completing...")
                    self.timer_label.update_idletasks()  # Force display update
            except ValueError as e:
                self.log_status(f"Timer error: {e}")


def main():
    root = tk.Tk()
    app = ZNLE_GUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
