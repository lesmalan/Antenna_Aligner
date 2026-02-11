# Arduino Motor Controller Setup

## Hardware Requirements

- **Arduino Uno R3**
- **Adafruit Motor Shield v3** (soldered on top of Uno)
- **Two NEMA17 Stepper Motors**
  - Azimuth Motor: Connected to M1/M2 terminal
  - Elevation Motor: Connected to M3/M4 terminal
- **External Power Supply** (connected to Motor Shield power block)
  - Recommended: 12V, 2A minimum
  - Variable voltage supply allows motor power adjustment
- **USB Cable** (Arduino to Raspberry Pi 5)

## Pin Connections

### Motor Shield Connections
- **M1/M2**: Azimuth stepper motor (left-right rotation)
- **M3/M4**: Elevation stepper motor (up-down rotation)
- **Power Block**: External power supply (+/- terminals)
- **I2C**: Uses Arduino pins A4 (SDA) and A5 (SCL) automatically

### USB Connection
- Arduino USB port → Raspberry Pi 5 USB port
- Provides serial communication at 115200 baud

## Software Installation

### 1. Install Arduino IDE
On Raspberry Pi 5:
```bash
sudo apt update
sudo apt install arduino
```

### 2. Install Required Libraries
Open Arduino IDE and install the Adafruit Motor Shield V2 library with its dependencies:

**Primary Library:**
- **Adafruit Motor Shield V2 Library** - Main library for controlling the motor shield

**Required Dependency:**
- **Adafruit Bus IO** - I2C/SPI communication library (required dependency)

**Installation Steps:**
1. Go to **Sketch → Include Library → Manage Libraries**
2. Search for "Adafruit Motor Shield V2 Library"
3. Click **Install**
4. Arduino IDE will automatically prompt to install the required "Adafruit Bus IO" dependency
5. Click **Install All** to install both libraries

**Manual Installation (if auto-install fails):**
- If the dependency doesn't install automatically:
  - Search for "Adafruit Bus IO" in Library Manager
  - Click **Install**

### 3. Upload Arduino Sketch
1. Open `antenna_controller.ino` in Arduino IDE
2. Select **Tools → Board → Arduino Uno**
3. Select **Tools → Port → /dev/ttyUSB0** (or /dev/ttyACM0)
4. Click **Upload** button

### 4. Install Python Dependencies
On Raspberry Pi 5:
```bash
cd /home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner
source .venv/bin/activate
pip install pyserial
```

## Testing the System

### 1. Find Serial Port
```bash
ls -l /dev/ttyUSB* /dev/ttyACM*
```
Common ports: `/dev/ttyUSB0` or `/dev/ttyACM0`

### 2. Test Serial Connection
```bash
# View Arduino output
screen /dev/ttyUSB0 115200

# Or use Python serial monitor
python3 -m serial.tools.miniterm /dev/ttyUSB0 115200
```

### 3. Run Python Controller
```bash
cd scripts
python3 motor_controller.py --port /dev/ttyUSB0
```

### 4. Interactive Commands
Once in interactive mode, try these commands:
```
>>> status          # Check current position
>>> speed 20        # Set speed to 20 RPM
>>> az 100          # Move azimuth 100 steps clockwise
>>> el 50           # Move elevation 50 steps up
>>> status          # Verify new position
>>> home            # Return to home position
>>> quit            # Exit
```

## Serial Communication Protocol

### Commands (Raspberry Pi → Arduino)
- `AZ <steps>` - Move azimuth by relative steps
- `EL <steps>` - Move elevation by relative steps
- `AZABS <steps>` - Move azimuth to absolute position
- `ELABS <steps>` - Move elevation to absolute position
- `HOME` - Return both motors to (0, 0)
- `STOP` - Emergency stop all motors
- `STATUS` - Report current positions
- `SPEED <rpm>` - Set motor speed (1-100 RPM)

### Responses (Arduino → Raspberry Pi)
- `OK` - Command executed successfully
- `OK AZ <steps>` - Azimuth move completed
- `OK EL <steps>` - Elevation move completed
- `POS AZ:<pos> EL:<pos>` - Position report
- `ERROR <message>` - Error description

## Motor Movement Details

### Step Calculations
- NEMA17 motors: 200 steps per revolution (1.8° per step)
- Using MICROSTEP mode for smoother motion
- Direction: FORWARD (positive steps), BACKWARD (negative steps)

### Coordinate System
- **Azimuth**: 
  - Positive steps = Clockwise rotation (looking from top)
  - Negative steps = Counterclockwise rotation
  - Zero position = Home/starting position

- **Elevation**:
  - Positive steps = Upward rotation
  - Negative steps = Downward rotation
  - Zero position = Home/starting position

### Converting Steps to Degrees
```
degrees = (steps / 200) * 360
steps = (degrees / 360) * 200
```

Example: 50 steps = (50/200) * 360 = 90 degrees

## Troubleshooting

### Motor Shield Not Detected
- **Error**: "Motor Shield not found. Check wiring."
- **Solution**: Check that shield is properly seated on Arduino
- Verify I2C address (default: 0x60)

### Motors Not Moving
- Check external power supply is connected and turned on
- Verify motor wires are connected to correct terminals
- Ensure motor coils are connected properly (check wire order)

### Erratic Motor Movement
- Reduce motor speed: `speed 10`
- Check power supply voltage (12V recommended for NEMA17)
- Ensure adequate current capacity (2A+ recommended)

### Serial Connection Issues
- Check USB cable connection
- Verify correct serial port: `ls -l /dev/tty*`
- Try different USB port on Raspberry Pi
- Check permissions: `sudo usermod -a -G dialout $USER`

### Motor Overheating
- Reduce holding current (motors release after each move)
- Improve cooling (add heatsinks or small fan)
- Reduce speed or step rate

## Power Supply Guidelines

### Voltage Selection
- **5V**: Very low torque, not recommended
- **9V**: Low torque, slow movements
- **12V**: Recommended for NEMA17, good torque
- **24V**: High torque, faster movements, check motor specs

### Current Requirements
- Each NEMA17: ~1-2A per motor
- Total for 2 motors: 2-4A minimum
- Recommended supply: 12V, 5A for margin

## Integration with Antenna Aligner System

The `motor_controller.py` script can be imported and used by other Python scripts:

```python
from motor_controller import MotorController

# Initialize controller
mc = MotorController(port='/dev/ttyUSB0')

# Move to position
mc.move_to_position(azimuth_steps=100, elevation_steps=50)

# Check position
az, el = mc.get_status()
print(f"Current position: AZ={az}, EL={el}")

# Return home
mc.home()

# Close connection
mc.close()
```

## Safety Notes

1. **Emergency Stop**: Always have `STOP` command ready
2. **Mechanical Limits**: Implement limit switches to prevent over-rotation
3. **Power Supply**: Use appropriate voltage/current to prevent damage
4. **Motor Torque**: NEMA17 motors are strong - ensure secure mounting
5. **Cooling**: Motors and drivers can get hot during extended operation

## Future Enhancements

- [ ] Add limit switch support for homing
- [ ] Implement acceleration/deceleration curves
- [ ] Add position feedback with encoders
- [ ] Create GUI for motor control
- [ ] Integrate with VNA scanning automation
- [ ] Add calibration routine for angle mapping
