# Arduino Motor Controller Firmware Update Instructions

## Issue: SETZERO Command Not Working

If you're getting an error that says "Arduino doesn't support SETZERO command", your Arduino may have an older version of the firmware.

## Current Firmware Features

The latest firmware (Feb 17, 2026) in `antenna_controller/antenna_controller.ino` supports:

- `AZ <steps>` - Move azimuth relative
- `EL <steps>` - Move elevation relative  
- `AZABS <steps>` - Move azimuth absolute
- `ELABS <steps>` - Move elevation absolute
- `HOME` - Return to home position
- **`SETZERO`** - Set current position as new home (0, 0)
- `STOP` - Emergency stop
- `STATUS` - Get current positions
- `SPEED <rpm>` - Set motor speed

## How to Update Arduino Firmware

### Option 1: Using Arduino IDE (Recommended)

1. **Install Arduino IDE** if not already installed:
   ```bash
   sudo apt install arduino
   ```

2. **Open the sketch**:
   ```bash
   arduino /home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner/arduino/antenna_controller/antenna_controller.ino
   ```

3. **Install required library**:
   - Go to: Sketch → Include Library → Manage Libraries
   - Search for "Adafruit Motor Shield V2"
   - Click Install

4. **Connect Arduino**:
   - Plug Arduino into USB port
   - Select: Tools → Board → Arduino Uno
   - Select: Tools → Port → /dev/ttyACM0 (or similar)

5. **Upload**:
   - Click the Upload button (→) or Sketch → Upload
   - Wait for "Done uploading" message

6. **Verify**:
   - Open Serial Monitor (Tools → Serial Monitor)
   - Set baud rate to 115200
   - You should see: "Antenna Aligner Controller Ready"
   - Type `SETZERO` and press Enter
   - Should respond: "OK SETZERO - Current position set as home (0, 0)"

### Option 2: Using arduino-cli (Command Line)

```bash
# Install arduino-cli
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

# Install board support
arduino-cli core update-index
arduino-cli core install arduino:avr

# Install library
arduino-cli lib install "Adafruit Motor Shield V2 Library"

# Compile and upload
cd /home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner/arduino/antenna_controller
arduino-cli compile --fqbn arduino:avr:uno antenna_controller.ino
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno antenna_controller.ino
```

## Software Fallback Mode

If you can't update the firmware right now, the Python GUI now has a **software fallback mode** that works automatically:

1. When you click "Set Current as Home", it tries the SETZERO command
2. If that fails, it automatically switches to software-based tracking
3. Your positions are tracked in software with offsets
4. Everything works the same from your perspective
5. You'll see a message: "Using software-based tracking"

### Differences in Software Mode:
- **Advantage**: Works with any firmware version
- **Disadvantage**: Position tracking resets if Arduino restarts
- **Recommendation**: Update firmware when convenient for best reliability

## Testing SETZERO Command

Use the test script to verify SETZERO works:

```bash
cd /home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner
python3 scripts/test_motor_connection.py
```

Select your port, connect, and in interactive mode type:
```
SETZERO
```

Expected response:
```
OK SETZERO - Current position set as home (0, 0)
```

If you get "ERROR Unknown command: SETZERO", you need to update firmware.

## Need Help?

Check that:
1. Arduino is powered and connected via USB
2. Correct port is selected (usually /dev/ttyACM0)
3. Adafruit Motor Shield library is installed
4. External power is connected to Motor Shield power terminal
5. Serial monitor is closed (only one program can use the port at a time)
