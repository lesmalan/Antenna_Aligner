# Antenna Aligner Demo Data Guide

## Overview

The Antenna Aligner GUI now includes a **"Load Demo Data"** button that generates realistic fake test data for demonstration purposes. This feature is perfect for:

- Creating presentation screenshots
- Testing the plotting functionality without hardware
- Training new users on the interface
- Validating data analysis workflows

## How to Use Demo Data

### Step 1: Select Scan Mode

Before loading demo data, select the desired scan mode:

- **Azimuth Sweep (1D)**: Tests horizontal antenna pattern
- **Elevation Sweep (1D)**: Tests vertical antenna pattern  
- **2D Grid (Az × El)**: Tests full hemispherical pattern

### Step 2: Configure Parameters (Optional)

Adjust the scan parameters to customize the demo data range:

**For Azimuth Mode:**
- Start: -180 to 180 steps (default: -180)
- Stop: -180 to 180 steps (default: 180)
- Step: 1 to 50 steps (default: 10)

**For Elevation Mode:**
- Start: -20 to 20 steps (default: -20)
- Stop: -20 to 20 steps (default: 20)
- Step: 1 to 10 steps (default: 5)

**For 2D Mode:**
- Uses both azimuth and elevation ranges

### Step 3: Load Demo Data

Click the **"Load Demo Data"** button in the Scan Control panel. The system will:

1. Generate synthetic antenna pattern data based on the current scan mode
2. Populate the scan_data array with realistic measurements
3. Update the plot automatically
4. Display the number of data points loaded
5. Update the status to "Demo data loaded"

## Demo Data Characteristics

### Azimuth Scan Demo Data

The azimuth demo data simulates a directional antenna pattern with:

- **Main Lobe**: Gaussian peak at 0° azimuth (~-5 dB maximum)
- **Side Lobes**: Secondary peaks at ±45° (~-15 dB)
- **Noise Floor**: Random variations around -35 dB
- **Realistic Shape**: Smooth beam pattern with side lobes

**Use Case**: Demonstrates antenna directionality and beam width

### Elevation Scan Demo Data

The elevation demo data simulates a vertical beam pattern with:

- **Main Beam**: Gaussian peak at 0° elevation (~-8 dB maximum)
- **Noise Floor**: Random variations around -30 dB
- **Narrower Beamwidth**: Tighter pattern than azimuth

**Use Case**: Shows vertical antenna coverage and elevation alignment

### 2D Grid Demo Data

The 2D demo data creates a full 3D antenna pattern with:

- **Main Lobe**: Centered at (0°, 0°) with ~-5 dB peak
- **Side Lobes**: Two secondary peaks offset from center (~-18 dB)
- **Noise Floor**: Random variations around -40 dB
- **Heatmap Visualization**: Color-coded amplitude across az/el space

**Use Case**: Visualizes complete antenna radiation pattern

## Demo Data Generation Algorithm

The demo data uses NumPy to create realistic antenna patterns:

```python
# Main lobe (Gaussian function)
main_lobe = -5 * np.exp(-0.002 * (az - 0)**2)

# Side lobes (additional Gaussian peaks)
side_lobe1 = -15 * np.exp(-0.001 * (az - 45)**2)
side_lobe2 = -15 * np.exp(-0.001 * (az + 45)**2)

# Random noise for realism
noise = np.random.normal(-35, 1.5)

# Final amplitude
amplitude = max(main_lobe + side_lobe1 + side_lobe2, noise)
```

## Saving Demo Data

Once demo data is loaded, you can:

1. **Save to CSV**: Click "Save Data" to export data points
2. **Save Plot**: Plot is automatically saved as PNG alongside CSV
3. **Clear Data**: Click "Clear Data" to reset before loading new demo data

## Example Workflow

### Quick Demo (Azimuth Pattern)

1. Launch GUI: `python antenna_aligner_gui.py`
2. Leave default settings (Azimuth mode, -180 to 180, step 10)
3. Click "Load Demo Data"
4. View the antenna pattern plot with main lobe and side lobes
5. Click "Save Data" to export for presentation

### Advanced Demo (2D Pattern)

1. Select "2D Grid (Az × El)" mode
2. Set azimuth range: -90 to 90, step 10
3. Set elevation range: -20 to 20, step 5
4. Click "Load Demo Data"
5. View the 2D heatmap showing full antenna pattern
6. Save data and plot for documentation

## Technical Notes

### Data Format

All demo data uses the same format as real measurements:
- **Azimuth**: Position in steps (-180 to 180)
- **Elevation**: Position in steps (-20 to 20)
- **Amplitude**: Signal strength in dB (-40 to 0 typical range)

### Randomization

Each time you load demo data, the noise floor is randomized to simulate:
- Measurement uncertainty
- Environmental variations
- Thermal noise

This makes each demo dataset slightly unique while maintaining the overall pattern shape.

### Performance

Demo data generation is instant:
- 1D scans: ~37 points @ 10° steps
- 2D scans: ~400-800 points depending on resolution
- No hardware required
- No measurement delay

## Limitations

Demo data is for **demonstration only** and:

- Does not represent actual hardware measurements
- Cannot be used for calibration
- Should not be used for scientific analysis
- Is purely synthetic and mathematical

## Quick Reference Commands

```bash
# Launch GUI normally
python antenna_aligner_gui.py

# Launch with auto-demo (using test script)
python test_demo_data.py
```

## Screenshot Checklist

For creating professional demo screenshots:

- [ ] Select appropriate scan mode
- [ ] Set realistic parameter ranges
- [ ] Load demo data
- [ ] Verify plot shows clear patterns
- [ ] Check data point count is displayed
- [ ] Confirm status shows "Demo data loaded"
- [ ] Take screenshot at full window size
- [ ] Save both data and plot for consistency

---

**Last Updated**: February 24, 2026  
**UCO Senior Design Group 2**
