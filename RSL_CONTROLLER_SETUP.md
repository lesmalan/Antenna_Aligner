# RSL Controller v01 - Setup & Usage Guide

## Quick Start

### Option 1: Desktop Icon (Recommended)
Double-click **`RSL_Controller_v01.desktop`** in the scripts folder to launch the application. The launcher will automatically:
- Verify the virtual environment exists
- Install/update all required dependencies
- Launch the GUI

### Option 2: Command Line
```bash
cd /home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner/scripts
./launch_rsl_controller.sh
```

### Option 3: Direct Python
```bash
cd /home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner
source .venv/bin/activate
python scripts/RSL_controller_v01.py
```

## Dependency Management

### Automatic Installation (Recommended)
Dependencies are automatically installed when using the desktop icon or launcher script. This ensures the application works after system reboots.

### Manual Setup (if needed)
```bash
cd /home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner/scripts
./setup_dependencies.sh
```

### Files Involved
- **requirements.txt** - Lists all required Python packages
- **launch_rsl_controller.sh** - Launcher script (verifies dependencies)
- **setup_dependencies.sh** - Manual setup/maintenance script
- **RSL_Controller_v01.desktop** - Desktop icon

## Required Dependencies

The following packages are automatically installed and maintained:

### Instrument Control
- `PyVISA` - ZNLE6 instrument communication
- `PyVISA-py` - PyVISA backend
- `pyserial` - Arduino/Motor controller communication

### Data Processing
- `numpy` - Numerical computations
- `pandas` - Data manipulation
- `scipy` - Scientific computing

### GUI & Visualization
- `matplotlib` - Real-time plotting
- `tkinter` - (built-in with Python)

### Web Services
- `fastapi` - API framework
- `uvicorn` - ASGI server
- `websockets` - WebSocket support

### Other Utilities
- `Pillow` - Image processing
- `pydantic` - Data validation
- `click` - CLI utilities

## Persistence After Reboot

The launcher script ensures dependencies persist across reboots by:

1. **Checking virtual environment** - Verifies .venv exists
2. **Activating venv** - Loads the isolated Python environment
3. **Installing/updating packages** - Runs `pip install -r requirements.txt`
4. **Launching the GUI** - Starts RSL_controller_v01.py

If you encounter issues after a reboot, run:
```bash
./setup_dependencies.sh
```

## Troubleshooting

### Desktop Icon Not Launching
1. Ensure the launcher script is executable:
   ```bash
   chmod +x launch_rsl_controller.sh
   ```

2. Try running manually:
   ```bash
   ./launch_rsl_controller.sh
   ```

### Missing Dependencies
If the application fails to start, manually run the setup:
```bash
./setup_dependencies.sh
```

### Virtual Environment Issues
1. Check if .venv exists:
   ```bash
   ls -la ~/.venv
   ```

2. If missing, recreate it:
   ```bash
   cd /home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner
   python3 -m venv .venv
   ```

3. Re-run setup:
   ```bash
   cd scripts
   ./setup_dependencies.sh
   ```

### Serial Port Issues
- Ensure Arduino is connected via USB
- Check available ports: `/dev/ttyACM0`, `/dev/ttyUSB0`, etc.
- Run `setup_dependencies.sh` again to ensure `pyserial` is installed

## Features Overview

**RSL Controller v01** provides:
- Real-time signal level monitoring (ZNLE6)
- Motor position display in **degrees** (not steps)
- **Auto-start** of monitoring on motor connection
- **Frequent position updates** (every 200ms)
- Scrollable interface for all parameters
- Manual motor controls
- CSV data logging

## File Locations

```
/home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner/
├── requirements.txt                    # Python dependencies
├── .venv/                              # Virtual environment
└── scripts/
    ├── RSL_controller_v01.py           # Main GUI application
    ├── RSL_Controller_v01.desktop      # Desktop icon
    ├── launch_rsl_controller.sh        # Launcher script
    └── setup_dependencies.sh           # Setup/maintenance script
```

## Support

For issues or questions:
1. Check the Help button in the GUI
2. Review the script output for error messages
3. Ensure virtual environment and dependencies are installed
4. Check hardware connections (ZNLE6, Arduino serial port)

---

**Created**: March 31, 2026
**Version**: RSL Controller v01
**Environment**: Python 3.13 with venv
