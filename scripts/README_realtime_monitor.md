# ZNLE6 Real-Time Signal Monitor

Real-time continuous signal monitoring tool with live plot display.

## Overview

This tool continuously measures signal amplitude at a target frequency and displays results in a live-updating matplotlib plot. Ideal for antenna alignment, signal tracking, and dynamic signal analysis.

## Features

- **Live Plot Display**: Real-time amplitude vs time graph that updates continuously
- **S-Parameter Selection**: Choose S11, S12, S21, or S22 measurements
- **Continuous Data Logging**: All measurements saved to timestamped CSV file
- **Configurable Update Rate**: Adjust measurement interval from 100ms to 10 seconds
- **Graceful Shutdown**: Close plot window or click Stop button to end monitoring
- **Rolling Display**: Maintains last 1000 data points on screen (older data in CSV)

## Components

### 1. Backend Script: `znle_realtime_monitor.py`
Python script that handles VNA communication, data collection, and live plotting.

**Command Line Usage:**
```bash
python3 znle_realtime_monitor.py --freq 977e6 --param S21 --interval 500

# Optional arguments:
--ip IP_ADDRESS          # ZNLE6 IP (default: 192.168.15.90)
--port PORT              # SCPI port (default: 5025)
--freq FREQUENCY         # Target frequency in Hz (REQUIRED)
--param S_PARAMETER      # S11, S12, S21, or S22 (default: S22)
--csv-dir DIRECTORY      # Output directory for CSV (default: current dir)
--filename BASENAME      # CSV filename prefix (default: realtime_monitor)
--interval MILLISECONDS  # Update interval (default: 500ms)
--max-points COUNT       # Maximum points on plot (default: 1000)
```

**Examples:**
```bash
# Monitor S21 transmission at 977 MHz, update every 500ms
python3 znle_realtime_monitor.py --freq 977e6 --param S21

# Monitor S22 reflection at 2.4 GHz, update every 250ms
python3 znle_realtime_monitor.py --freq 2.4e9 --param S22 --interval 250

# Save to specific directory with custom filename
python3 znle_realtime_monitor.py --freq 977e6 --param S21 \
    --csv-dir /home/user/data --filename antenna_test
```

### 2. GUI Application: `znle_realtime_monitor_gui.py`
Graphical interface for easy configuration and launching.

**Launch Methods:**
```bash
# From terminal
python3 znle_realtime_monitor_gui.py

# Or double-click desktop launcher
ZNLE6_Realtime_Monitor.desktop
```

**GUI Controls:**
- **Connection Settings**: VNA IP address and port
- **Measurement Settings**:
  - Target Frequency: Single frequency to monitor (in Hz)
  - S-Parameter: Measurement type (S11, S12, S21, S22)
  - Update Interval: Time between measurements (in milliseconds)
- **Output Settings**: CSV directory and filename prefix
- **Control Buttons**: Start, Stop, Help

### 3. Desktop Launcher: `ZNLE6_Realtime_Monitor.desktop`
Desktop icon for one-click access to GUI.

## S-Parameter Guide

| Parameter | Description | Use Case |
|-----------|-------------|----------|
| **S21** | Transmission: Port 1 → Port 2 | Antenna-to-antenna transmission testing |
| **S12** | Reverse transmission: Port 2 → Port 1 | Reverse path analysis |
| **S11** | Reflection at Port 1 | Transmitter impedance matching |
| **S22** | Reflection at Port 2 | Receiver impedance, single-antenna reception |

## Hardware Setup Examples

### Two-Antenna Transmission Test (S21)
```
NanoVNA H4 Port 1 → Amplifier → TX Antenna
                                    |
                                 (air gap)
                                    |
RX Antenna → ZNLE6 Port 2
```
**Use S21 parameter** to measure transmitted signal strength.

### Single-Antenna Reception Test (S22)
```
External Signal Source
         |
      (air gap)
         |
RX Antenna → ZNLE6 Port 2
```
**Use S22 parameter** to measure received signal strength.

## Operation

### Starting a Monitoring Session

1. **Launch GUI**: Double-click desktop icon or run from terminal
2. **Configure Connection**: Enter ZNLE6 IP address (usually 192.168.15.90)
3. **Set Target Frequency**: Enter frequency in Hz (e.g., 977e6 for 977 MHz)
4. **Select S-Parameter**: Choose appropriate measurement type
5. **Set Update Rate**: 500ms (2 updates/sec) is typical
6. **Click "Start Real-Time Monitor"**

### During Monitoring

- **Live Plot Window**: Opens automatically showing amplitude vs time
- **Plot Features**:
  - Blue line: Signal amplitude trace
  - Info box: Current value, elapsed time, point count
  - Auto-scaling: Y-axis adjusts to signal range
  - X-axis: Shows elapsed time in seconds
- **Console Output**: Prints measurement summary every 10 points
- **CSV Logging**: Data continuously written to file

### Stopping Monitoring

Two methods to stop:
1. **Close Plot Window**: Click X on plot window
2. **Stop Button**: Click Stop in GUI

Data is automatically saved to CSV when stopped.

## Output Files

### CSV Format
```csv
Timestamp,Elapsed_Time_s,Frequency_Hz,Amplitude_dB
2026-03-10 14:30:00.123,0.000,977000000,-45.23
2026-03-10 14:30:00.623,0.500,977000000,-45.18
2026-03-10 14:30:01.123,1.000,977000000,-45.21
...
```

**Columns:**
- `Timestamp`: Wall clock time (YYYY-MM-DD HH:MM:SS.mmm)
- `Elapsed_Time_s`: Seconds since monitoring started
- `Frequency_Hz`: Target frequency in Hz
- `Amplitude_dB`: Measured signal amplitude in dB

### Filename Convention
```
{filename}_{timestamp}.csv

Examples:
realtime_monitor_20260310_143000.csv
antenna_alignment_20260310_150525.csv
```

## Use Cases

### 1. Antenna Alignment
Monitor signal strength in real-time while adjusting antenna position:
- Set target frequency (e.g., 977 MHz)
- Use S21 for transmission measurements
- Watch live plot while rotating/tilting antenna
- Find position with maximum amplitude

### 2. Signal Stability Testing
Track signal variations over time:
- Set slower update rate (1000-2000ms)
- Monitor for extended periods
- Analyze CSV data for drift and noise

### 3. Dynamic Signal Tracking
Follow rapidly changing signals:
- Set fast update rate (100-250ms)
- Monitor during antenna movements
- Capture transient events

### 4. Amplifier Testing
Verify amplifier stability and gain:
- Connect amplifier between antennas
- Monitor output signal continuously
- Check for gain variations over time

## Troubleshooting

### Problem: Timeout errors
**Solution**: 
- Check VNA connection (IP address correct?)
- Verify VNA is powered on and network accessible
- Try slower update interval (increase from 500ms to 1000ms)

### Problem: Plot not updating
**Solution**:
- Ensure backend script is running (check console)
- Verify VNA is configured for continuous operation
- Check for error messages in console output

### Problem: Noisy/unstable readings
**Solution**:
- Increase update interval to average out noise
- Check antenna connections and cable integrity
- Verify signal source is stable
- Disable VNA averaging (script does this automatically)

### Problem: CSV file not created
**Solution**:
- Check write permissions in output directory
- Ensure directory exists (GUI creates automatically)
- Verify filename doesn't contain invalid characters

## Performance Notes

- **Update Interval**: 500ms (2 Hz) provides good balance of responsiveness and stability
- **Faster Updates**: 100-250ms possible for dynamic signals, may increase CPU load
- **Slower Updates**: 1000-2000ms for stable signals, reduces data volume
- **Maximum Points**: 1000 points displayed (older data automatically removed from plot)
- **CSV Data**: All measurements saved regardless of display limit

## Technical Details

### VNA Configuration
The script automatically configures the ZNLE6:
- Single frequency point measurement (CW mode)
- Averaging disabled for fast updates
- Log magnitude format (dB)
- ASCII data format
- Manual trigger mode

### Plot Auto-Scaling
- **Y-axis**: Centers on mean amplitude with ±5 dB margin (minimum)
- **X-axis**: Expands as time progresses
- **Range adjustment**: Increases margin for signals with large variations

### Data Buffer
- Uses Python `deque` for efficient FIFO buffer
- Maximum 1000 points in memory
- Automatic rollover when limit reached
- All data preserved in CSV file

## Dependencies

- Python 3.x
- pyvisa and pyvisa-py (VNA communication)
- matplotlib (live plotting)
- numpy (data handling)
- tkinter (GUI, included with Python)

## Related Tools

- **znle_gui.py**: Single-shot frequency sweep and monitor mode
- **frequency_scanner_gui.py**: Quiet frequency band detection
- **antenna_aligner_gui.py**: Automated antenna pattern scanning

## Version History

**v1.0 - March 10, 2026**
- Initial release
- Real-time plotting with matplotlib animation
- S-parameter selection (S11, S12, S21, S22)
- Continuous CSV logging
- Configurable update interval
- GUI and command-line interfaces
