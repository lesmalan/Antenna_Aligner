# Antenna Aligner

A comprehensive RF antenna alignment and characterization system with motor-controlled positioning and automated radiation pattern measurement capabilities.

## Project Acknowledgments

### Development Team
- **Ms Lorelei Potter** - CE
- **Mr Brett Bailey** - EE
- **Mr Les Malan** - ME

**University of Central Oklahoma**  
School of Engineering  
Senior Design II - Spring 2026

### Project Advisors
- **Dr Alaeddin Abuabed**
- **Dr Nasreen Alsbou**
- **Dr Mohammad Robi Hossan**

### Special Thanks
**Mr Cole Ranck, EE** - ASRC Federal

---

## Overview

The Antenna Aligner project provides tools for antenna alignment:

- **RSL Controller v01**: Primary motor control application with absolute and incremental positioning
- **Flutter App**: Mobile interface for guided antenna alignment using Received Signal Level (RSL)
- **Python Tools**: Optional desktop applications for advanced VNA control and pattern analysis
- **Raspberry Pi Server**: WebSocket/TCP server for real-time data streaming to mobile devices
- **Motor Control System**: Automated azimuth/elevation positioning with ±75° range


## Requirements

### For Flutter App
- **Flutter SDK**: 3.0 or higher
- **Raspberry Pi**: Running the WebSocket server (`pi_websocket_server.py`)
- **Network**: Device and Raspberry Pi must be on the same networkI was in the middle of somethi

### For Python Tools
- **Python**: 3.7 or higher
- **ZNLE6 VNA**: Connected via Ethernet for RF measurements
- **Arduino**: Motor controller (Uno R3) on `/dev/ttyACM0`
- **Raspberry Pi 5**: For server integration (optional but recommended)
- **Installed Dependencies**: See `requirements.txt` or individual tool documentation

## Installation

### Flutter App
1. Clone the repository
2. Install dependencies:
   ```bash
   flutter pub get
   ```
3. Run the app:
   ```bash
   flutter run
   ```

### Python Tools
1. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install required dependencies:
   ```bash
   pip install pyvisa pyvisa-py matplotlib numpy websockets
   ```
3. Launch tools via desktop launchers or command line (see Usage below)

## Available Tools

### Python Desktop Applications (in `scripts/` directory)

#### RSL Controller v01 (`RSL_controller_v01.py`)
Motor control GUI with absolute and incremental positioning.
- **Features**: 
  - Absolute position control (degree-based)
  - Incremental 2-step movements for smooth tracking
  - Real-time position display (azimuth, elevation)
  - Auto-connect motor on startup
  - Elevation range: ±75° (expanded for hemispherical coverage)
  - Progress percentage during movements
- **Launch**: Double-click "Motor Controller" desktop icon or run:
  ```bash
  python3 scripts/RSL_controller_v01.py
  ```

## Hardware Configuration

The system is configured for the following hardware setup:

### Transmitter
- **VNA**: NanoVNA-H4 (977 MHz, ±100 MHz range)
- **Amplifier**: 40dB amplifier (5V)
- **Antenna**: RFSpace UWB antenna (900-12000 MHz range)

### Receiver
- **Antenna**: RFSpace UWB antenna (900-12000 MHz range, motor-controlled)
- **Analyzer**: ZNLE6 connected via Ethernet to network
- **Motor System**: 
  - NEMA17 stepper motors (2x) for azimuth/elevation control
  - Arduino Uno R3 motor controller with Adafruit Motor Shield v2
    - Azimuth motor: Connected to M1 and M2
    - Elevation motor: Connected to M3 and M4
  - 3D-printed receiver mount assembly with elevation control

### Network
- **Router**: GL iNet AC1200 wireless router
- **Connections**:
  - ZNLE6: Ethernet (wired)
  - Raspberry Pi 5: Wireless or wired
  - Development computer: Wireless
  - Motor controller: Direct USB to Raspberry Pi

## How to Use

### RSL Controller v01 - Main Motor Control Application

This is the primary tool for antenna alignment and motor control.

#### Quick Start
1. Connect Arduino motor controller via USB to `/dev/ttyACM0`
2. **On Raspberry Pi 5**: Start the WebSocket server to allow connection from mobile devices/Flutter emulator:
   ```bash
   python3 pi_websocket_server.py
   ```
3. Launch the RSL Controller application:
   ```bash
   python3 scripts/RSL_controller_v01.py
   ```
   Or double-click "Motor Controller" desktop icon
4. Motor automatically connects on startup
5. Monitor real-time position display at top of window

#### Normal Operation

1. **Prepare Hardware**: Before opening the app, make sure that the Arduino and ZNLE6 are powered on and ready.

2. **Launch Application**: Open the RSL Controller v01 app. The motor should automatically connect and the real-time monitor should start.

3. **Set Home Position**: Manually position the antenna in the desired position and click the "Set Current As Home" button to establish an origin position.

4. **Enter Target Position**: Enter a Target Azimuth or Elevation angle and click the corresponding "Go To" button to move the antenna to the target position.

#### Manual Motor Control
- **Absolute Positioning**: 
  - Enter target degrees in "Absolute Position" section (e.g., 45.5°)
  - Click "Go To Az Position" or "Go To El Position"
  - Watch progress percentage and real-time position updates
  - Motor moves in 2-step increments for fine control

- **Relative Adjustments**:
  - Use directional buttons: CCW/CW (azimuth), Up/Down (elevation)
  - Each click moves the specified step size
  - Useful for fine-tuning antenna alignment

#### Special Functions
- **Home Position**: Press "Goto Home" to return to (0°, 0°)
  - Uses either hardware SETZERO command or software offset
  - Calibration prompts appear on first use
- **Set Current as Home**: Establishes new reference point at current position
- **Emergency Stop**: Immediately halts any motor movement

#### Position Range
- **Azimuth**: 360° rotation (0° = reference, CCW = positive)
- **Elevation**: ±75° (expanded for hemispherical coverage)
- **Home Calibration**: Hardware (SETZERO) or software offset modes

#### Monitor Settings
- Motor status updates automatically every ~100ms
- Connection settings at bottom of window (rarely changed after setup)
- Speed control slider for movement velocity adjustment

### Flutter App - Mobile Antenna Alignment

The Flutter app provides a mobile interface for guided alignment using RSL (Received Signal Level):

1. Ensure Raspberry Pi WebSocket server is running
2. Launch Flutter app on mobile device
3. Follow the two-sided alignment process (azimuth then elevation sweeps)
4. App calculates optimal turnbuckle adjustments

## App Screens

### RSL Controller v01 - Main Application
| Component | Description |
|-----------|-------------|
| Current Position Display | Large, bold azimuth/elevation in degrees (real-time) |
| Absolute Position Controls | Input fields for target degrees, "Go To" buttons |
| Relative Movement Buttons | CCW/CW, Up/Down for fine adjustments |
| Quick Actions | Home button, Emergency Stop, Speed control |
| Status Bar | Movement progress, completion percentage |
| Connection Panel | VNA and Arduino status indicators |

### Flutter App Screens
| Screen | Description |
|--------|-------------|
| Connection | Displays while waiting for Raspberry Pi connection |
| Azimuth Sweep | Real-time graph and recording controls for horizontal alignment |
| Azimuth Complete | Enter turnbuckles and view alignment instructions |
| Elevation Sweep | Real-time graph and recording controls for vertical alignment |
| Elevation Complete | Enter turnbuckles and view alignment instructions |
| Completed | Confirmation that both sides are aligned |

### Optional Desktop Tool Windows
| Tool | Primary Window | Features |
|------|---|---|
| Antenna Aligner Combined | Dual pane (plot + controls) | Radiation pattern visualization, scan mode selection, data export |
| ZNLE6 Controller | Configurable analysis panel | Frequency input, S-parameter selection, measurement mode |

## Support

Press the **phone icon** in the app bar to access the support helpline.

## Architecture

```
Antenna_Aligner/
├── lib/
│   ├── main.dart                          # Flutter app with UI and logic
│   └── vna_service.dart                   # VNA WebSocket client service
│
├── scripts/
│   ├── RSL_controller_v01.py              # Main motor control GUI (ACTIVE)
│   ├── antenna_aligner_gui.py             # Combined VNA + motor control GUI (optional)
│   ├── znle_gui.py                        # ZNLE6 VNA controller GUI (optional)
│   ├── znle_pyvisa.py                     # Low-level VNA communication (SCPI)
│   ├── motor_controller.py                # Arduino motor control library
│   ├── pi_tcp_server.py                   # Raspberry Pi TCP/WebSocket server
│   ├── pi_websocket_server.py             # Raspberry Pi WebSocket server
│   └── test_motor_connection.py           # Motor controller testing utility
│
├── arduino/
│   ├── antenna_controller.ino             # Motor controller firmware
│   └── FIRMWARE_UPDATE_INSTRUCTIONS.md    # Arduino programming guide
│
├── docs/
│   └── app_flowchart.md                   # Application architecture diagram
│
├── CSVs/                                  # Output directory for data files
├── Plots/                                 # Output directory for plot images
│
├── README.md                              # This file
├── CHANGES.txt                            # Detailed development history
├── TURNBUCKLE_LEAD_SCREW_CONVERSION_INSTRUCTIONS.txt  # Hardware guide
└── [desktop launcher files]               # .desktop files for desktop shortcuts

Data Flow:
  ZNLE6 VNA (Ethernet) ──> Raspberry Pi ──> WebSocket Server
                               ↓
                         Arduino Motor Controller (USB)
                               ↓
                         Motor-controlled Test Bed
```

### Communication Protocols

- **VNA Communication**: PyVISA with SCPI commands (TCP/IP)
- **Motor Control**: Serial communication at 115200 baud (USB)
- **Flutter to Server**: WebSocket (JSON messages)
- **Server Management**: TCP socket interface for testing/debugging

## WebSocket Protocol

### Flutter to Server Communication

The app communicates with the Raspberry Pi server using JSON messages:

**RSL Data Request:**
```json
{"action": "start", "request": "rsl"}
```

**RSL Data Response:**
```json
{
  "rsl": -85.5,
  "azimuth_turns_left": 3,
  "azimuth_turns_right": 0,
  "elevation_turns_left": 2,
  "elevation_turns_right": 0
}
```

### Server Commands

The pi_tcp_server.py supports these commands via plain TCP:
- `PING` - Connection test
- `STATUS` - Server health check and job listing
- `RUN` - Start VNA measurement
- `QUIT`/`EXIT` - Close connection

## Key Features

### RSL Controller v01 - Main Motor Control Application
- **Absolute Positioning**: Enter target degrees directly (e.g., 45.5°)
- **Incremental Movements**: 2-step increments for fine-grained position tracking
- **Position Verification**: Software confirms motor reached target position
- **Extended Range**: Elevation ±75° for hemispherical coverage
- **Auto-Home Calibration**: Hardware SETZERO or software offset modes
- **Visual Feedback**: Large, bold position display with real-time updates
- **Progress Tracking**: Percentage display during movements
- **Auto-Connect**: Motor automatically connects on startup

### Optional: Automated Scanning (Antenna Aligner GUI)
- **1D Scans**: Azimuth or elevation sweeps for 1D radiation patterns
- **2D Grid Scans**: Full 2D pattern mapping with heatmap visualization
- **Peak Detection**: Automatic identification of maximum signal points
- **Configurable Parameters**: Start/stop positions, step size, measurement delay
- **Data Export**: CSV with all measurements, PNG plots with peak markers

## Data Files and Output

### Output Directories

- **CSVs/**: Measurement data in comma-separated format
  - Columns: Timestamp, Elapsed_Time_s, Frequency_Hz, Amplitude_Raw_dB, Amplitude_Smoothed_dB
  - Timestamped filenames for organization
  
- **Plots/**: Graph images from analysis tools
  - Format: PNG images for easy viewing
  - Include axis labels, legends, and peak markers
  - Suitable for reports and documentation

### File Naming Convention

Most tools use timestamped filenames:
```
{base_filename}_{YYYY-MM-DD_HH-MM-SS}.csv
{base_filename}_{YYYY-MM-DD_HH-MM-SS}.png
```

This prevents accidental overwriting and creates a chronological record.

### Arduino Configuration

Default motor parameters:
- **Serial Port**: `/dev/ttyACM0`
- **Baud Rate**: 115200
- **Step Size**: 10 steps (configurable)
- **Default Speed**: 30 RPM
- **Elevation Limits**: ±75° (±420 steps) from calibrated home

## Documentation

Additional documentation files are available:

- **CHANGES.txt**: Complete development history with feature details
- **TURNBUCKLE_LEAD_SCREW_CONVERSION_INSTRUCTIONS.txt**: Hardware conversion guide
- **docs/app_flowchart.md**: Application architecture and flow diagrams
- **arduino/FIRMWARE_UPDATE_INSTRUCTIONS.md**: Arduino programming guide

## Troubleshooting

### Flutter App Issues
| Issue | Solution |
|-------|----------|
| "Offline" status | Check network connection and Raspberry Pi server |
| No data received | Verify signal analyzer is connected and configured |
| Connection timeout | Confirm IP address in code matches Raspberry Pi |
| App not responding | Use debug mode to test without hardware |

### Python Tools Issues
| Issue | Solution |
|-------|----------|
| VNA connection fails | Check VNA IP address (default 192.168.15.90) and network connectivity |
| "VI_ERROR_TMO" timeout | VNA is busy; increase timeout or try again |
| Motor not responding | Verify Arduino at /dev/ttyACM0 is connected; check USB cable |
| "Permission denied" on /dev/ttyACM0 | Add user to dialout group: `sudo usermod -aG dialout $USER` |
| Import errors for pyvisa/matplotlib | Ensure virtual environment is activated and dependencies installed |
| Plot not displaying | Check if X11 forwarding is enabled (for remote systems) |
| Motor movements jerky or slow | Reduce speed control value or increase step size |

## License

See [LICENSE.txt](LICENSE.txt) for details.
