#!/usr/bin/env python3
"""
Test script to demonstrate the antenna aligner GUI with fake data.
This script launches the GUI, loads demo data, and captures screenshots.
"""

import tkinter as tk
import time
import sys
import os

# Add the scripts directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the GUI
from antenna_aligner_gui import AntennaAlignerGUI

def main():
    """Launch GUI and load demo data automatically."""
    root = tk.Tk()
    app = AntennaAlignerGUI(root)
    
    # Schedule demo data loading after GUI is fully initialized
    def load_demo_after_init():
        print("Loading demo data for azimuth scan...")
        app.scan_mode.set("azimuth")
        app.load_demo_data()
        
    # Load demo data after 1 second
    root.after(1000, load_demo_after_init)
    
    # Run the GUI
    root.mainloop()

if __name__ == "__main__":
    main()
