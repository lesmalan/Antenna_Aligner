# Antenna Aligner GUI - Demo Data Update Summary

## What Was Added

### 1. Load Demo Data Button
A new "Load Demo Data" button has been added to the Scan Control panel of the antenna aligner GUI. This button allows users to generate and visualize realistic fake test data without requiring any hardware connections.

**Location**: Scan Control panel, below the "Save Data" button

### 2. Demo Data Generation Method
A new method `load_demo_data()` was added to the `AntennaAlignerGUI` class that:

- Generates realistic antenna pattern data based on the current scan mode (Azimuth, Elevation, or 2D)
- Uses NumPy to create Gaussian-shaped beam patterns with side lobes
- Adds random noise to simulate real measurement conditions
- Automatically updates the plot and data counter

### 3. Demo Plot Generator Script
A standalone script `generate_demo_plots.py` was created to:

- Generate demonstration plots independently of the GUI
- Create three plot types: Azimuth, Elevation, and 2D patterns
- Save high-quality PNG images (150 dpi) for presentations
- Output files to `/Plots/demo/` directory

### 4. Documentation
Two comprehensive documentation files were created:

#### DEMO_DATA_GUIDE.md
- Complete guide on using the demo data feature
- Explains the characteristics of each scan mode's demo data
- Provides step-by-step instructions
- Describes the data generation algorithm
- Includes technical notes and limitations

#### README_antenna_aligner.md (Updated)
- Added "Demo Data" section to the features list
- Links to detailed demo data guide

## Generated Demo Plots

Three demonstration plots have been created and saved to `/Plots/demo/`:

1. **demo_azimuth_pattern.png** (66.7 KB)
   - Shows azimuth sweep from -180° to 180° (10° steps)
   - Main lobe at 0° with peak ~-5 dB
   - Side lobes at ±45° with ~-15 dB
   - Noise floor around -35 dB

2. **demo_elevation_pattern.png** (70.7 KB)
   - Shows elevation sweep from -20° to 20° (5° steps)
   - Main beam at 0° with peak ~-8 dB
   - Narrower beamwidth than azimuth
   - Noise floor around -30 dB

3. **demo_2d_pattern.png** (191.1 KB)
   - Shows 2D heatmap (azimuth -90° to 90°, elevation -20° to 20°)
   - Main lobe centered at (0°, 0°)
   - Two side lobes visible
   - Color-coded amplitude from hot (high) to dark (low)

## How to Use

### Using the GUI
1. Launch the antenna aligner GUI: `python antenna_aligner_gui.py`
2. Select a scan mode (Azimuth, Elevation, or 2D)
3. Optionally adjust scan parameters
4. Click "Load Demo Data"
5. View the plot and save if desired

### Generating Standalone Plots
```bash
python scripts/generate_demo_plots.py
```

This will create all three demo plots in `/Plots/demo/` without launching the GUI.

## Technical Details

### Demo Data Algorithm

**Azimuth Pattern**:
```python
main_lobe = -5 * np.exp(-0.002 * (az - 0)**2)
side_lobe1 = -15 * np.exp(-0.001 * (az - 45)**2)
side_lobe2 = -15 * np.exp(-0.001 * (az + 45)**2)
noise = np.random.normal(-35, 1.5)
amplitude = max(main_lobe + side_lobe1 + side_lobe2, noise)
```

**Elevation Pattern**:
```python
main_beam = -8 * np.exp(-0.01 * (el - 0)**2)
noise = np.random.normal(-30, 1.0)
amplitude = max(main_beam, noise)
```

**2D Pattern**:
```python
main_lobe = -5 * np.exp(-0.002 * az**2 - 0.01 * el**2)
side_lobe1 = -18 * np.exp(-0.001 * (az - 30)**2 - 0.008 * (el - 5)**2)
side_lobe2 = -18 * np.exp(-0.001 * (az + 30)**2 - 0.008 * (el + 5)**2)
noise = np.random.normal(-40, 2.0)
amplitude = max(main_lobe + side_lobe1 + side_lobe2, noise)
```

## Files Modified

1. **antenna_aligner_gui.py**
   - Added "Load Demo Data" button to control frame
   - Added `load_demo_data()` method with NumPy-based data generation

2. **README_antenna_aligner.md**
   - Added demo data feature to features list

## Files Created

1. **DEMO_DATA_GUIDE.md** - Comprehensive demo data usage guide
2. **generate_demo_plots.py** - Standalone plot generator
3. **test_demo_data.py** - Test script for auto-loading demo data
4. **generate_demo_screenshots.py** - Screenshot automation (for systems with display)

## Benefits

- **No Hardware Required**: Test and demonstrate the GUI without VNA or motors
- **Training Tool**: Train new users on the interface safely
- **Presentations**: Generate professional-looking plots for reports and presentations
- **Testing**: Validate data export and plotting functionality
- **Reproducible**: Generate consistent demo patterns for documentation

## Use Cases

1. **Project Presentations**: Use demo plots in slideshows
2. **User Training**: Show students how the system works before hardware access
3. **Software Testing**: Test plot rendering and data export without hardware
4. **Documentation**: Create screenshots and examples for manuals
5. **Debugging**: Verify plotting logic with known data patterns

---

**Generated**: February 24, 2026  
**UCO Senior Design Group 2**
