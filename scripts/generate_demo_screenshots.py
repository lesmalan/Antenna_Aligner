#!/usr/bin/env python3
"""
Automated screenshot generator for antenna aligner demo.
This script launches the GUI, loads demo data for different modes,
and saves screenshots for documentation.
"""

import tkinter as tk
from PIL import ImageGrab
import time
import sys
import os

# Add the scripts directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from antenna_aligner_gui import AntennaAlignerGUI

def capture_screenshot(root, filename):
    """Capture screenshot of the GUI window."""
    try:
        # Get window geometry
        x = root.winfo_rootx()
        y = root.winfo_rooty()
        width = root.winfo_width()
        height = root.winfo_height()
        
        # Capture the window area
        screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        
        # Save to file
        output_path = os.path.join(os.path.dirname(__file__), "..", "Plots", filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        screenshot.save(output_path)
        print(f"Screenshot saved to: {output_path}")
        
    except Exception as e:
        print(f"Screenshot failed: {e}")
        print("Note: Screenshot requires display server (X11/Wayland)")

def generate_demo_screenshots():
    """Generate demo screenshots for all scan modes."""
    root = tk.Tk()
    app = AntennaAlignerGUI(root)
    
    screenshot_schedule = []
    
    # Schedule 1: Azimuth scan demo
    def demo_azimuth():
        print("=== Generating Azimuth Demo ===")
        app.scan_mode.set("azimuth")
        app.scan_start_az.set(-180)
        app.scan_stop_az.set(180)
        app.scan_step_az.set(10)
        app.load_demo_data()
        root.update()
        time.sleep(0.5)
        capture_screenshot(root, "demo_azimuth_scan.png")
        
        # Schedule next demo
        root.after(2000, demo_elevation)
    
    # Schedule 2: Elevation scan demo
    def demo_elevation():
        print("=== Generating Elevation Demo ===")
        app.scan_mode.set("elevation")
        app.scan_start_el.set(-20)
        app.scan_stop_el.set(20)
        app.scan_step_el.set(5)
        app.load_demo_data()
        root.update()
        time.sleep(0.5)
        capture_screenshot(root, "demo_elevation_scan.png")
        
        # Schedule next demo
        root.after(2000, demo_2d)
    
    # Schedule 3: 2D grid demo
    def demo_2d():
        print("=== Generating 2D Grid Demo ===")
        app.scan_mode.set("2d")
        app.scan_start_az.set(-90)
        app.scan_stop_az.set(90)
        app.scan_step_az.set(10)
        app.scan_start_el.set(-20)
        app.scan_stop_el.set(20)
        app.scan_step_el.set(5)
        app.load_demo_data()
        root.update()
        time.sleep(0.5)
        capture_screenshot(root, "demo_2d_grid_scan.png")
        
        # Done - schedule exit
        root.after(2000, root.quit)
    
    # Start the sequence after GUI is ready
    root.after(1000, demo_azimuth)
    
    # Run GUI
    root.mainloop()
    print("\n=== Demo screenshot generation complete ===")

if __name__ == "__main__":
    print("Antenna Aligner Demo Screenshot Generator")
    print("=========================================\n")
    generate_demo_screenshots()
