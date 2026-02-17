# Antenna Aligner Combined GUI

## Overview

The Antenna Aligner GUI integrates VNA signal monitoring with motor control for automated antenna pattern characterization. This application allows you to:

- **Monitor signal strength** at a single frequency or across a frequency range
- **Automatically rotate** the receiver antenna through azimuth positions
- **Record and visualize** signal amplitude vs. antenna position
- **Export data** for further analysis

## Features

### VNA Control
- Connect to R&S ZNLE6 VNA over TCP/IP
- Monitor single frequency or frequency range (peak tracking)
- Configurable S-parameters (S11, S21, S12, S22)
- Real-time amplitude measurements

### Motor Control
- Arduino-based stepper motor control via serial
- Position tracking for azimuth and elevation
- Manual control with directional buttons
- Emergency stop and home functions

### Scan Modes
- **Azimuth Sweep (1D)**: Rotate horizontally at fixed elevation
- **Elevation Sweep (1D)**: Tilt vertically at current azimuth
- **2D Grid Scan**: Full azimuth × elevation mapping

### Data Acquisition
- Automated scanning: Move antenna → Measure signal → Record data
- Configurable scan parameters:
  - Start/stop angles for azimuth and elevation
  - Step size (resolution)
  - Measurement delay (for settling time)
- Real-time plotting during scan
- Supports 1D line plots and 2D heatmaps

### Data Export
- Save scan data to CSV (azimuth, elevation, amplitude)
- Automatically save plot images
- Timestamped filenames

## Hardware Requirements

1. **VNA**: R&S ZNLE6 Vector Network Analyzer
   - Default IP: 192.168.15.90
   - Port: 5025 (SCPI over TCP)

2. **Motor Controller**: Arduino Uno R3 + Adafruit Motor Shield v3
   - Default port: /dev/ttyACM0
   - Baudrate: 115200
   - Two NEMA17 stepper motors (azimuth and elevation)

3. **RF Hardware**:
   - Transmitter: NanoVNA-H4 with amplifier and antenna
   - Receiver: Pasco WA-9800A on motorized mount

## Installation

Ensure all dependencies are installed in your virtual environment:

```bash
cd /home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner
source .venv/bin/activate
pip install pyvisa pyvisa-py matplotlib pyserial
```

## Usage

### Launch the GUI

```bash
# From command line
python3 scripts/antenna_aligner_gui.py

# Or use the desktop launcher
./scripts/Antenna_Aligner.desktop
```

### Typical Workflow

1. **Connect Hardware**
   - Click "Connect Motor" to connect to Arduino
   - Click "Connect VNA" to connect to ZNLE6
   - Status messages appear in the activity log

2. **Configure Frequency**
   - **Single Frequency Mode**: Monitor one specific frequency
     - Select "Single Frequency" radio button
     - Enter frequency in MHz (e.g., 977 for 977 MHz)
   - **Range Mode**: Track peak across frequency range
     - Select "Frequency Range (Peak)" radio button
     - Enter start/stop frequencies and number of points
     - System will find and track peak amplitude

3. **Manual Motor Control (Optional)**
   - Use directional buttons to position antenna manually
   - Azimuth: CCW/CW buttons with configurable step size
   - Elevation: Down/Up buttons with configurable step size
   - Current position displayed in real-time
   - Home button returns to (0, 0)
   - Emergency Stop releases motors immediately

4. **Select Scan Mode**
   - **Azimuth Sweep**: Horizontal rotation at fixed elevation
     - Set azimuth start/stop/step
     - Set fixed elevation position
   - **Elevation Sweep**: Vertical tilt at current azimuth
     - Set elevation start/stop/step
     - Uses current azimuth position
   - **2D Grid**: Complete azimuth × elevation mapping
     - Set both azimuth and elevation ranges
     - Creates heatmap visualization

5. **Set Scan Parameters**
   Example for azimuth sweep:
   - Start Az: -180
   - Stop Az: 180
   - Step Size: 10 (yields 37 data points)
   - Fixed El: 0
   - Delay: 1.0 (allow antenna to settle)

6. **Run Scan**
   - Click "Start Scan"
   - Watch the plot update in real-time
   - Current position and data point count update
   - Click "Stop Scan" to abort if needed

7. **Save Results**
   - Click "Save Data" when scan completes
   - Choose filename and location
   - CSV file and plot PNG are saved automatically

## Operating Modes

### Scan Modes

#### Azimuth Sweep (1D)
- Rotates antenna horizontally through azimuth range
- Maintains fixed elevation position
- Fastest mode for horizontal pattern characterization
- Produces 1D line plot of signal vs. azimuth

**Use Case**: Determine optimal horizontal orientation for maximum signal at a specific elevation angle.

**Parameters**:
- Azimuth start/stop/step: Define horizontal sweep range
- Fixed elevation: Set vertical angle (typically 0 for horizontal)
- Delay: Settling time after each movement

#### Elevation Sweep (1D)
- Tilts antenna vertically through elevation range
- Maintains current azimuth position
- Useful for vertical beam pattern analysis
- Produces 1D line plot of signal vs. elevation

**Use Case**: Characterize vertical beam pattern at a specific horizontal orientation.

**Parameters**:
- Elevation start/stop/step: Define vertical sweep range (-20 to +20 limit)
- Current azimuth: Uses whatever azimuth position antenna is at
- Delay: Settling time after each movement

#### 2D Grid Scan
- Complete azimuth × elevation mapping
- Raster pattern: For each elevation, sweeps all azimuths
- Comprehensive pattern characterization
- Produces 2D heatmap visualization

**Use Case**: Full antenna radiation pattern characterization, finding global maximum, visualizing beam shape.

**Parameters**:
- Azimuth start/stop/step: Horizontal range
- Elevation start/stop/step: Vertical range
- Delay: Settling time (critical for accuracy in 2D)
- Total points = (az_points) × (el_points)

**Example**: 37 az points × 9 el points = 333 measurements

### Frequency Monitoring Modes

#### Single Frequency Monitoring
- Monitors signal strength at one specific frequency
- Fastest option for known transmitter frequency
- Best for antenna alignment tasks

**Use Case**: You have a transmitter at 977 MHz and want to find the receiver antenna orientation with maximum signal.

#### Frequency Range Peak Tracking
- Sweeps across frequency range and tracks peak amplitude
- Useful when transmitter frequency may vary slightly
- More robust to frequency drift

**Use Case**: Your transmitter may be anywhere from 950-1000 MHz, and you want to track the strongest signal regardless of exact frequency.

## Data Format

CSV output contains three columns:

```csv
azimuth_steps,elevation_steps,amplitude_dB
-180,0,-45.32
-170,0,-43.21
-160,0,-41.15
...
```

- **azimuth_steps**: Horizontal motor position in steps (not calibrated to degrees)
- **elevation_steps**: Vertical motor position in steps
- **amplitude_dB**: Signal amplitude in decibels

**Note**: For 1D scans, one coordinate remains constant:
- Azimuth scan: elevation column will all be the same (fixed elevation)
- Elevation scan: azimuth column will all be the same (current azimuth)

## Tips and Best Practices

### Scan Parameters
- **Smaller step sizes** → More data points, longer scan time
- **Larger delays** → Better settling, more accurate measurements
- **Typical delay**: 0.5-2.0 seconds depending on motor speed

### Frequency Selection
- Use **single frequency** when you know the transmitter frequency precisely
- Use **range mode** for robustness or when characterizing over bandwidth
- Frequency range should encompass expected signal bandwidth

### Motor Speed
- Set motor speed using Arduino motor controller (default: 30 RPM)
- Slower speeds may improve accuracy by reducing vibration
- Match delay time to motor settling characteristics

### Connection Issues
- If VNA connection fails, verify network connectivity:
  ```bash
  ping 192.168.15.90
  ```
- If motor controller fails, check Arduino serial port:
  ```bash
  ls -l /dev/ttyACM*
  ```

## Troubleshooting

### "Motor controller not connected"
- Ensure Arduino is plugged in via USB
- Check correct serial port selected (/dev/ttyACM0 or /dev/ttyUSB0)
- Verify Arduino has motor shield firmware loaded

### "VNA not connected"
- Verify VNA is powered on and network cable connected
- Check IP address (default: 192.168.15.90)
- Ensure firewall allows port 5025

### Plot not updating during scan
- This is normal - plot updates after each measurement
- If no updates at all, check activity log for errors

### Scan stops unexpectedly
- Check activity log for error messages
- Verify motor didn't hit physical limits
- Ensure VNA is responding (may timeout if busy)

## Technical Details

### Coordinate System
- **Azimuth**: Horizontal rotation (stepper motor steps)
  - Positive = Clockwise when viewed from above
  - Negative = Counterclockwise
  - Full range depends on mechanical limits
- **Elevation**: Vertical tilt (±20 step hardware limit)
  - Positive = Up (receiver tilts upward)
  - Negative = Down (receiver tilts downward)
  - Range: -20 to +20 steps from calibrated home

### VNA Configuration
- Amplitude format: MLOG (logarithmic magnitude in dB)
- Trigger mode: Single sweep (manual trigger)
- Data format: ASCII (human-readable)

### Threading
- Scan runs in separate thread to keep GUI responsive
- Motor and VNA commands are synchronous (blocking)
- Plot updates happen on main GUI thread

## Related Scripts

- **motor_controller_gui.py**: Standalone motor control (manual operation)
- **znle_pyvisa.py**: Standalone VNA control (command-line)
- **frequency_scanner_gui.py**: Frequency spectrum analysis

## Future Enhancements

Potential improvements:
- [x] Manual azimuth and elevation control
- [x] Elevation scan support
- [x] 2D pattern mapping (azimuth + elevation grid)
- [ ] Polar plot option (azimuth as angle, amplitude as radius)
- [ ] Real-time signal strength indicator
- [ ] Auto-peak seeking (move to maximum signal)
- [ ] Multi-frequency comparison mode
- [ ] 3D surface plot for 2D scans
- [ ] Contour plot overlay option

## Support

For issues or questions:
1. Check the activity log for error messages
2. Review this README
3. Consult CHANGES.txt for recent updates
4. Contact UCO Senior Design Group 2

---

**UCO Senior Design Group 2 - Spring 2026**
