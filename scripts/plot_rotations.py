#!/usr/bin/env python3
"""
Plot amplitude vs time for different rotation angles from CSV data.
"""
import pandas as pd
import matplotlib.pyplot as plt
import sys

# Read the CSV file
csv_path = "/home/sd2-group2/Desktop/Test 3 Rotations.csv"
df = pd.read_csv(csv_path)

# Create the plot
plt.figure(figsize=(12, 7))

# Plot each rotation angle with different colors
plt.plot(df['time_s'], df['0 degrees (dB)'], 'b-', linewidth=2, marker='o', markersize=4, label='0 degrees', alpha=0.7)
plt.plot(df['time_s'], df['90 degrees (dB)'], 'r-', linewidth=2, marker='s', markersize=4, label='90 degrees', alpha=0.7)
plt.plot(df['time_s'], df['180 degrees (dB)'], 'g-', linewidth=2, marker='^', markersize=4, label='180 degrees', alpha=0.7)

# Customize the plot
plt.xlabel('Time (seconds)', fontsize=12)
plt.ylabel('Amplitude (dB)', fontsize=12)
plt.title('Antenna Signal Amplitude vs Time for Different Rotations', fontsize=14, fontweight='bold')
plt.legend(loc='best', fontsize=11)
plt.grid(True, alpha=0.3)
plt.tight_layout()

# Save the plot
output_path = "/home/sd2-group2/Desktop/rotation_comparison_plot.png"
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"Plot saved to: {output_path}")

# Display the plot
plt.show()
