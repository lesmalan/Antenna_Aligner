#!/usr/bin/env python3
"""
Generate demonstration plots for the antenna aligner.
This creates standalone plot images without requiring the GUI to be running.
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import os
from datetime import datetime

# Create output directory
output_dir = os.path.join(os.path.dirname(__file__), "..", "Plots", "demo")
os.makedirs(output_dir, exist_ok=True)

def generate_azimuth_demo_plot():
    """Generate demo azimuth scan plot."""
    print("Generating azimuth scan demo plot...")
    
    # Parameters
    start_az = -180
    stop_az = 180
    step_az = 10
    
    azimuths = range(start_az, stop_az + 1, step_az)
    amplitudes = []
    
    # Generate realistic antenna pattern
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
        amplitudes.append(amplitude)
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(azimuths, amplitudes, 'b-o', linewidth=2, markersize=5, label='Signal Amplitude')
    
    # Mark peak
    peak_idx = amplitudes.index(max(amplitudes))
    peak_az = list(azimuths)[peak_idx]
    peak_amp = amplitudes[peak_idx]
    ax.plot(peak_az, peak_amp, 'r*', markersize=15, 
            label=f'Peak: {peak_amp:.2f} dB @ Az={peak_az}°')
    
    ax.set_xlabel("Azimuth (steps)", fontsize=12)
    ax.set_ylabel("Signal Amplitude (dB)", fontsize=12)
    ax.set_title("Azimuth Pattern - Demo Data", fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)
    
    # Save
    filename = os.path.join(output_dir, "demo_azimuth_pattern.png")
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"Saved: {filename}")
    plt.close()
    
    return list(azimuths), amplitudes

def generate_elevation_demo_plot():
    """Generate demo elevation scan plot."""
    print("Generating elevation scan demo plot...")
    
    # Parameters
    start_el = -20
    stop_el = 20
    step_el = 5
    
    elevations = range(start_el, stop_el + 1, step_el)
    amplitudes = []
    
    # Generate realistic antenna pattern
    for el in elevations:
        # Main beam pattern
        main_beam = -8 * np.exp(-0.01 * (el - 0)**2)
        
        # Noise floor
        noise = np.random.normal(-30, 1.0)
        
        amplitude = max(main_beam, noise)
        amplitudes.append(amplitude)
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(elevations, amplitudes, 'g-o', linewidth=2, markersize=5, label='Signal Amplitude')
    
    # Mark peak
    peak_idx = amplitudes.index(max(amplitudes))
    peak_el = list(elevations)[peak_idx]
    peak_amp = amplitudes[peak_idx]
    ax.plot(peak_el, peak_amp, 'r*', markersize=15, 
            label=f'Peak: {peak_amp:.2f} dB @ El={peak_el}°')
    
    ax.set_xlabel("Elevation (steps)", fontsize=12)
    ax.set_ylabel("Signal Amplitude (dB)", fontsize=12)
    ax.set_title("Elevation Pattern - Demo Data", fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)
    
    # Save
    filename = os.path.join(output_dir, "demo_elevation_pattern.png")
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"Saved: {filename}")
    plt.close()
    
    return list(elevations), amplitudes

def generate_2d_demo_plot():
    """Generate demo 2D grid scan plot."""
    print("Generating 2D grid scan demo plot...")
    
    # Parameters
    start_az = -90
    stop_az = 90
    step_az = 10
    start_el = -20
    stop_el = 20
    step_el = 5
    
    azimuths = list(range(start_az, stop_az + 1, step_az))
    elevations = list(range(start_el, stop_el + 1, step_el))
    
    # Generate 2D grid data
    scan_data = []
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
            scan_data.append((az, el, amplitude))
    
    # Create grid for plotting
    grid = np.full((len(elevations), len(azimuths)), np.nan)
    
    for az, el, amp in scan_data:
        az_idx = azimuths.index(az)
        el_idx = elevations.index(el)
        grid[el_idx, az_idx] = amp
    
    # Create plot
    fig, ax = plt.subplots(figsize=(12, 8))
    
    im = ax.imshow(grid, aspect='auto', origin='lower',
                   extent=[min(azimuths), max(azimuths), 
                          min(elevations), max(elevations)],
                   cmap='hot', interpolation='bilinear')
    
    # Add colorbar
    cbar = fig.colorbar(im, ax=ax, label='Amplitude (dB)')
    
    # Mark peak
    peak_amp = max([amp for az, el, amp in scan_data])
    peak_data = [(az, el) for az, el, amp in scan_data if amp == peak_amp][0]
    peak_az, peak_el = peak_data
    
    ax.plot(peak_az, peak_el, 'c*', markersize=20, 
            markeredgecolor='white', markeredgewidth=2,
            label=f'Peak: {peak_amp:.2f} dB')
    
    ax.set_xlabel("Azimuth (steps)", fontsize=12)
    ax.set_ylabel("Elevation (steps)", fontsize=12)
    ax.set_title("2D Antenna Pattern - Demo Data", fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    
    # Save
    filename = os.path.join(output_dir, "demo_2d_pattern.png")
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"Saved: {filename}")
    plt.close()
    
    return scan_data

def generate_all_demos():
    """Generate all demonstration plots."""
    print("\n" + "="*60)
    print("Antenna Aligner - Demo Plot Generator")
    print("="*60 + "\n")
    
    # Generate all three demo plots
    az_data = generate_azimuth_demo_plot()
    el_data = generate_elevation_demo_plot()
    grid_data = generate_2d_demo_plot()
    
    print("\n" + "="*60)
    print("Demo plots generated successfully!")
    print(f"Output directory: {output_dir}")
    print("="*60 + "\n")
    
    # List generated files
    print("Generated files:")
    for filename in os.listdir(output_dir):
        if filename.endswith('.png'):
            filepath = os.path.join(output_dir, filename)
            filesize = os.path.getsize(filepath) / 1024  # KB
            print(f"  - {filename} ({filesize:.1f} KB)")

if __name__ == "__main__":
    generate_all_demos()
