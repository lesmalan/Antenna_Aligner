# Chat Log - February 11, 2026
## Hardware Documentation and Arduino Motor Controller Development

### Session Overview
This session focused on documenting hardware configuration, creating Arduino motor control system, and updating project documentation.

---

## 1. CHANGES.txt Update Request

**User Request:** Create new date entry in CHANGES.txt for today's work following previous formatting.

**Action:** Initially checked for changes - none committed yet. User asked to wait until changes were made.

---

## 2. README.txt Hardware Configuration Section

### Initial Request
**User:** Add "Hardware Configuration" section to README.txt to keep record of hardware setup.

**Details Provided:**
- Test bed has 3D printed receiver brackets cradling WA-9800A receiver
- U-shaped bracket arm for elevation control
- Left side: NEMA17 stepper motor with keyed connection
- Right side: Round pivot pin
- Base: Another NEMA17 motor (vertically positioned) for azimuth control
- 4-leg base structure

**Created:** Comprehensive Hardware Configuration section with 7 subsections:
1. Vector Network Analyzer (ZNLE6)
2. Transmitter Setup (NanoVNA-H4)
3. Receiver Setup (Pasco WA-9800A)
4. Control Computer (Raspberry Pi 5)
5. Network Configuration
6. Software Environment
7. Test Bed Apparatus

### Refinement: Elevation Axis Label
**User Request:** Change "Elevation Control (Left-Right Axis)" to "(Up-Down Axis)"

**Completed:** Updated axis description for clarity.

### Signal Chain Reorganization
**User Provided Full Signal Path:**

**Transmitter Chain:**
- NanoVNA H4 generates 977 MHz signal
- Signal goes to 40dB amplifier (5V powered)
- Amplifier outputs to RFSpace TSA900 UWB antenna (900-12000 MHz range)

**Receiver Chain:**
- Pasco WA-9800A microwave receiver (9V adapter powered)
- Alligator clips connect to internal antenna output nodes
- Clips connect via adapters to ZNLE6 Port 1

**Action:** Completely reorganized Hardware Configuration section to show proper signal flow:
1. Transmitter Chain (first)
2. Receiver Chain (second)
3. Vector Network Analyzer (third)
4. Remaining sections follow

### Network Infrastructure Update
**User Provided Network Details:**
- GL iNet AC1200 wireless router (central hub)
- ZNLE6: Ethernet connection to router
- Raspberry Pi 5: Wireless connection
- Application emulator: Wireless connection
- Development PC: Wireless connection
- Router has WAN connection to internet

**Action:** Updated Network Configuration section with complete topology.

---

## 3. CHANGES.txt Entry for Today

**Created comprehensive entry documenting:**

### Documentation Updates - 02/11/26
1. Hardware Configuration Documentation (README.txt)
   - Complete RF signal chain documentation
   - Transmitter: NanoVNA-H4 (977 MHz) → 40dB amplifier → RFSpace TSA900 antenna
   - Receiver: Pasco WA-9800A → adapters → ZNLE6 Port 1
   - ZNLE6 VNA specifications and network settings
   - Raspberry Pi 5 control computer configuration

2. Network Infrastructure Documentation
   - GL iNet AC1200 router as network hub
   - Device connections (Ethernet vs wireless)
   - Router WAN to internet

3. Test Bed Apparatus Specifications
   - 3D printed receiver mount assembly details
   - NEMA17 stepper motor specifications
   - Elevation control (Up-Down Axis)
   - Azimuth control (Rotational Axis)
   - Base structure with 4 legs

---

## 4. Arduino Motor Controller Development

### User Hardware Configuration
- Arduino Uno R3
- Adafruit Motor Shield v3 (soldered on top)
- Elevation motor: M3/M4 connector
- Azimuth motor: M1/M2 connector
- Variable voltage power supply to shield power block
- USB connection: Arduino → Raspberry Pi 5

### Created Files

#### A. antenna_controller.ino
**Location:** `arduino/antenna_controller/antenna_controller.ino`

**Features:**
- Controls two NEMA17 stepper motors (200 steps/rev)
- Serial communication at 115200 baud
- Adafruit Motor Shield v3 support

**Serial Commands:**
- `AZ <steps>` - Move azimuth (relative)
- `EL <steps>` - Move elevation (relative)
- `AZABS <steps>` - Move azimuth (absolute)
- `ELABS <steps>` - Move elevation (absolute)
- `HOME` - Return to (0, 0)
- `STOP` - Emergency stop
- `STATUS` - Report current positions
- `SPEED <rpm>` - Set motor speed (1-100 RPM)

**Responses:**
- `OK` - Command successful
- `OK AZ <steps>` - Azimuth move complete
- `OK EL <steps>` - Elevation move complete
- `POS AZ:<pos> EL:<pos>` - Position report
- `ERROR <msg>` - Error message

**Key Features:**
- Position tracking (absolute positions in steps)
- Configurable speed (default: 30 RPM)
- MICROSTEP mode for smooth movement
- Motors released after movement (power saving)
- Emergency stop functionality

#### B. motor_controller.py
**Location:** `scripts/motor_controller.py`

**Features:**
- Python interface for serial communication
- Easy-to-use MotorController class
- Interactive command-line mode
- Can be imported for integration

**Class Methods:**
- `move_azimuth(steps)` - Relative azimuth movement
- `move_elevation(steps)` - Relative elevation movement
- `move_to_position(az, el)` - Absolute positioning
- `home()` - Return to home position
- `stop()` - Emergency stop
- `set_speed(rpm)` - Adjust motor speed
- `get_status()` - Get current positions
- `close()` - Close serial connection

**Interactive Commands:**
```
>>> status          # Check position
>>> speed 20        # Set speed
>>> az 100          # Move azimuth
>>> el 50           # Move elevation
>>> goto 100 50     # Absolute position
>>> home            # Return home
>>> quit            # Exit
```

#### C. arduino/README.md
**Comprehensive documentation including:**

**Hardware Requirements:**
- Arduino Uno R3
- Adafruit Motor Shield v3
- Two NEMA17 stepper motors
- External power supply (12V, 2A+ recommended)
- USB cable to Raspberry Pi

**Pin Connections:**
- M1/M2: Azimuth motor
- M3/M4: Elevation motor
- Power block: External supply
- I2C: Automatic (A4/A5)

**Installation Instructions:**
1. Install Arduino IDE: `sudo apt install arduino`
2. Install Adafruit Motor Shield V2 Library
3. Upload sketch to Arduino
4. Install Python dependencies: `pip install pyserial`

**Testing Procedures:**
- Find serial port
- Test serial connection
- Run Python controller
- Try interactive commands

**Troubleshooting:**
- Motor shield not detected
- Motors not moving
- Erratic movement
- Serial connection issues
- Motor overheating

**Power Supply Guidelines:**
- Voltage: 5V-24V (12V recommended)
- Current: 2-4A minimum for two motors
- Safety notes

**Integration Examples:**
- Python code snippets for importing and using MotorController class

**Future Enhancements:**
- Limit switch support
- Acceleration curves
- Position feedback with encoders
- GUI for motor control
- VNA scanning automation
- Calibration routines

---

## 5. Arduino IDE Installation

**User Request:** How to install Arduino IDE from Linux terminal?

**Command Executed:**
```bash
sudo apt update && sudo apt install arduino -y
```

**Installed:**
- Arduino IDE version 1.8.19
- Java Runtime (OpenJDK 21)
- AVR toolchain (gcc-avr, avr-libc, binutils-avr)
- avrdude (programmer)
- 68 total packages

**Post-Installation Instructions:**
1. Add user to dialout group: `sudo usermod -a -G dialout $USER`
2. Log out and back in
3. Launch Arduino IDE: `arduino`
4. Install Adafruit Motor Shield V2 Library via Library Manager

---

## Summary of Created/Modified Files

### Created:
1. `arduino/antenna_controller/antenna_controller.ino` - Arduino sketch
2. `scripts/motor_controller.py` - Python interface
3. `arduino/README.md` - Complete Arduino documentation
4. `chat_logs/2026-02-11_hardware_documentation_and_motor_controller.md` - This file

### Modified:
1. `README.txt` - Added Hardware Configuration section
2. `CHANGES.txt` - Added entry for 02/11/26

---

## Key Technical Details

### Motor Configuration
- **NEMA17 Stepper Motors:** 200 steps/revolution (1.8° per step)
- **Azimuth Motor (M1/M2):** Left-right rotation
- **Elevation Motor (M3/M4):** Up-down rotation
- **Step Mode:** MICROSTEP (smoother movement)
- **Default Speed:** 30 RPM
- **Speed Range:** 1-100 RPM

### Communication Protocol
- **Baud Rate:** 115200
- **Connection:** USB serial (Arduino ↔ Raspberry Pi 5)
- **Format:** Text commands with newline termination
- **Response:** Immediate acknowledgment after command execution

### RF Signal Chain
**Transmit Path:**
NanoVNA-H4 (977 MHz) → 40dB Amp (5V) → TSA900 UWB Antenna

**Receive Path:**
Pasco WA-9800A (9V) → Alligator clips → Adapters → ZNLE6 Port 1

### Network Topology
```
                    [Internet]
                        |
                      (WAN)
                        |
              [GL iNet AC1200 Router]
                        |
         ┌──────────────┼──────────────┬──────────────┐
    (Ethernet)      (WiFi)         (WiFi)         (WiFi)
         |              |              |              |
     [ZNLE6]      [Pi 5]      [Dev PC]    [Emulator]
  192.168.15.90
```

---

## Next Steps (Suggested)

1. **Hardware Setup:**
   - Connect Arduino to Pi via USB
   - Connect motors to shield (M1/M2 and M3/M4)
   - Connect power supply to shield
   - Upload Arduino sketch

2. **Testing:**
   - Verify serial port (`ls -l /dev/ttyUSB*`)
   - Test motor movements with Python script
   - Calibrate step counts for desired angles
   - Test emergency stop functionality

3. **Integration:**
   - Add limit switches for safety
   - Create automated scanning routines
   - Integrate with VNA control scripts
   - Add to WebSocket server for Flutter app control

4. **Calibration:**
   - Map steps to degrees for both axes
   - Find optimal speed settings
   - Test range of motion limits
   - Document home position reference

---

## Commands Reference

### Arduino IDE
```bash
arduino                          # Launch Arduino IDE
sudo apt install arduino         # Install Arduino IDE
```

### Motor Controller
```bash
# Interactive mode
python3 scripts/motor_controller.py --port /dev/ttyUSB0

# Find serial port
ls -l /dev/ttyUSB* /dev/ttyACM*

# Add user to dialout group
sudo usermod -a -G dialout $USER
```

### Serial Monitoring
```bash
# Using screen
screen /dev/ttyUSB0 115200

# Using miniterm
python3 -m serial.tools.miniterm /dev/ttyUSB0 115200
```

---

## End of Session

**Date:** February 11, 2026
**Duration:** ~2 hours
**Status:** All code created and documented, Arduino IDE installed, ready for hardware testing
