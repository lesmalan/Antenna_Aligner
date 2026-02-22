# Antenna Aligner

A Flutter application for microwave antenna signal alignment. This app guides technicians through the process of aligning antenna azimuth and elevation for optimal signal strength (RSL - Received Signal Level).

## Overview

The Antenna Aligner app connects to a Raspberry Pi via WebSocket to receive real-time RSL data from a signal analyzer. It guides technicians through a systematic alignment process for both sides of a microwave antenna link.

## Requirements

- **Flutter SDK**: 3.0 or higher
- **Raspberry Pi**: Running the WebSocket server (`pi_websocket_server.py`)
- **Signal Analyzer**: Connected to the Raspberry Pi for RSL measurements
- **Network**: Device and Raspberry Pi must be on the same network

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   flutter pub get
   ```
3. Run the app:
   ```bash
   flutter run
   ```

## How to Use

### Connection

1. Launch the app
2. The app will automatically attempt to connect to the Raspberry Pi at `ws://192.168.15.192:8000/ws`
3. Wait for the "Connected" status in the top-right corner
4. Once connected, the azimuth sweep screen will appear automatically

### Alignment Process

The alignment process consists of **two sides**, each with **two phases**:

#### Side 1

**Phase 1: Azimuth Sweep**
1. Press **"Start Recording"** to begin capturing RSL data
2. Slowly rotate the antenna from LEFT to RIGHT through its full range
3. Press **"Stop Recording"** when the sweep is complete
4. Press **"Sweep Complete"** to proceed
5. Enter the number of turnbuckles in your sweep
6. Press **"Submit"** to calculate alignment
7. Review the alignment instructions showing how many turns LEFT to reach maximum signal
8. Press **"Confirm Alignment"** to proceed

**Phase 2: Elevation Sweep**
1. Press **"Start Recording"** to begin capturing RSL data
2. Slowly adjust the antenna elevation from BOTTOM to TOP
3. Press **"Stop Recording"** when the sweep is complete
4. Press **"Sweep Complete"** to proceed
5. Enter the number of turnbuckles in your sweep
6. Press **"Submit"** to calculate alignment
7. Review the alignment instructions showing how many turns DOWN from the top to reach maximum signal
8. Press **"Confirm Alignment"** to complete Side 1

#### Side 2

Repeat the same azimuth and elevation sweep process for the other side of the antenna link.

### Completion

Once both sides are aligned, the app displays a completion screen confirming successful alignment.

## App Screens

| Screen | Description |
|--------|-------------|
| Connection | Displays while waiting for Raspberry Pi connection |
| Azimuth Sweep | Real-time graph and recording controls for horizontal alignment |
| Azimuth Complete | Enter turnbuckles and view alignment instructions |
| Elevation Sweep | Real-time graph and recording controls for vertical alignment |
| Elevation Complete | Enter turnbuckles and view alignment instructions |
| Completed | Confirmation that both sides are aligned |

## Support

Press the **phone icon** in the app bar to access the support helpline.

## Architecture

```
lib/
├── main.dart          # Main application with all UI and logic
└── vna_service.dart   # VNA (Vector Network Analyzer) service

scripts/
├── pi_websocket_server.py  # WebSocket server for Raspberry Pi
├── motor_controller.py     # Motor control utilities
└── ...                     # Additional Python scripts
```

## WebSocket Protocol

The app communicates with the Raspberry Pi using JSON messages:

**Request:**
```json
{"action": "start", "request": "rsl"}
```

**Response:**
```json
{
  "rsl": -85.5,
  "azimuth_turns_left": 3,
  "azimuth_turns_right": 0,
  "elevation_turns_left": 2,
  "elevation_turns_right": 0
}
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Offline" status | Check network connection and Raspberry Pi server |
| No data received | Verify signal analyzer is connected and configured |
| Connection timeout | Confirm IP address in code matches Raspberry Pi |
| App not responding | Use debug mode to test without hardware |

## License

See [LICENSE.txt](LICENSE.txt) for details.
