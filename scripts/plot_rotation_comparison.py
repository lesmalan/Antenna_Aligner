#!/usr/bin/env python3
"""
Plot rotation comparison data with smoothed trendlines.
"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import uniform_filter1d

# Read the CSV file
csv_file = "/home/sd2-group2/Desktop/Test 3 Rotations.csv"
df = pd.read_csv(csv_file)

# Extract data
time = df['time_s']
rotation_0 = df['0 degrees (dB)']
rotation_90 = df['90 degrees (dB)']
rotation_180 = df['180 degrees (dB)']

# Create smoothed trendlines using moving average
window_size = 5  # Adjust this for more or less smoothing
smooth_0 = uniform_filter1d(rotation_0, size=window_size)
smooth_90 = uniform_filter1d(rotation_90, size=window_size)
smooth_180 = uniform_filter1d(rotation_180, size=window_size)

# Create the plot
plt.figure(figsize=(12, 7))

# Plot original data with transparency
plt.plot(time, rotation_0, 'o', color='blue', alpha=0.3, markersize=3, label='0° (data)')
plt.plot(time, rotation_90, 'o', color='red', alpha=0.3, markersize=3, label='90° (data)')
plt.plot(time, rotation_180, 'o', color='green', alpha=0.3, markersize=3, label='180° (data)')

# Plot smoothed trendlines
plt.plot(time, smooth_0, '-', color='blue', linewidth=2.5, label='0° (trend)')
plt.plot(time, smooth_90, '-', color='red', linewidth=2.5, label='90° (trend)')
plt.plot(time, smooth_180, '-', color='green', linewidth=2.5, label='180° (trend)')

# Labels and formatting
plt.xlabel('Time (seconds)', fontsize=12)
plt.ylabel('Amplitude (dB)', fontsize=12)
plt.title('Antenna Rotation Comparison with Trendlines', fontsize=14, fontweight='bold')
plt.legend(loc='best', fontsize=10)
plt.grid(True, alpha=0.3)
plt.tight_layout()

# Save to desktop
output_file = "/home/sd2-group2/Desktop/rotation_comparison_plot.png"
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"Plot saved to: {output_file}")

# Calculate and print averages
print(f"\nAverage Amplitudes:")
print(f"  0°:   {rotation_0.mean():.2f} dB")
print(f"  90°:  {rotation_90.mean():.2f} dB")
print(f"  180°: {rotation_180.mean():.2f} dB")
