/*
 * Antenna Aligner - Arduino Stepper Motor Controller
 * 
 * Hardware:
 *   - Arduino Uno R3
 *   - Adafruit Motor Shield v3
 *   - NEMA17 Stepper Motors (200 steps/rev typical)
 *     * Azimuth Motor: M1/M2 connector (left-right rotation)
 *     * Elevation Motor: M3/M4 connector (up-down rotation)
 *   - USB connection to Raspberry Pi 5
 *   - External power supply to Motor Shield power block
 * 
 * Serial Communication Protocol:
 *   Commands from Raspberry Pi:
 *     AZ <steps>     - Move azimuth motor (positive = clockwise, negative = counterclockwise)
 *     EL <steps>     - Move elevation motor (positive = up, negative = down)
 *     AZABS <steps>  - Move azimuth to absolute position
 *     ELABS <steps>  - Move elevation to absolute position
 *     HOME           - Return both motors to home position (0, 0)
 *     SETZERO        - Set current position as new home (0, 0) - calibration
 *     STOP           - Emergency stop all motors
 *     STATUS         - Report current positions
 *     SPEED <rpm>    - Set motor speed (RPM)
 * 
 *   Responses to Raspberry Pi:
 *     OK             - Command executed successfully
 *     POS AZ:<pos> EL:<pos> - Position report
 *     ERROR <msg>    - Error message
 * 
 * UCO Senior Design Group 2 - Spring 2026
 */

#include <Wire.h>
#include <Adafruit_MotorShield.h>

// ==================================================================
// HARDWARE CONFIGURATION
// ==================================================================

// Create Motor Shield object with default I2C address (0x60)
Adafruit_MotorShield AFMS = Adafruit_MotorShield();

// Connect stepper motors (200 steps/rev for NEMA17)
// Motor 1: Azimuth (M1/M2 connector)
// Motor 2: Elevation (M3/M4 connector)
Adafruit_StepperMotor *azimuthMotor = AFMS.getStepper(200, 1);
Adafruit_StepperMotor *elevationMotor = AFMS.getStepper(200, 2);

// ==================================================================
// CONFIGURATION PARAMETERS
// ==================================================================

// Motor speed in RPM (revolutions per minute)
int motorSpeed = 30;  // Default: 30 RPM (adjust for your application)

// Current absolute positions (in steps)
long azimuthPosition = 0;
long elevationPosition = 0;

// Motor movement parameters
const int STEPS_PER_REV = 200;    // NEMA17 standard (1.8° per step)
const int MAX_SPEED = 100;         // Maximum RPM
const int MIN_SPEED = 1;           // Minimum RPM

// Elevation limits (due to mounting hardware geometry)
const long MAX_ELEVATION = 20;     // Maximum elevation steps (up from zero)
const long MIN_ELEVATION = -20;    // Minimum elevation steps (down from zero)

// Serial communication buffer
String inputString = "";
boolean stringComplete = false;

// Emergency stop flag
boolean emergencyStop = false;

// ==================================================================
// SETUP - Initialize hardware and serial communication
// ==================================================================

void setup() {
  // Initialize serial communication at 115200 baud
  Serial.begin(115200);
  
  // Reserve 100 bytes for input string
  inputString.reserve(100);
  
  // Initialize Motor Shield
  if (!AFMS.begin()) {
    Serial.println("ERROR Motor Shield not found. Check wiring.");
    while (1);  // Halt execution if shield not detected
  }
  
  // Set initial motor speed
  azimuthMotor->setSpeed(motorSpeed);
  elevationMotor->setSpeed(motorSpeed);
  
  // Release motors (no holding torque at startup)
  azimuthMotor->release();
  elevationMotor->release();
  
  // Startup message
  Serial.println("Antenna Aligner Controller Ready");
  Serial.println("Azimuth: M1/M2, Elevation: M3/M4");
  Serial.print("Motor Speed: ");
  Serial.print(motorSpeed);
  Serial.println(" RPM");
}

// ==================================================================
// MAIN LOOP - Process serial commands
// ==================================================================

void loop() {
  // Check for completed serial commands
  if (stringComplete) {
    processCommand(inputString);
    
    // Clear the string for next command
    inputString = "";
    stringComplete = false;
  }
  
  // Check for emergency stop
  if (emergencyStop) {
    azimuthMotor->release();
    elevationMotor->release();
    emergencyStop = false;  // Reset after stopping
  }
}

// ==================================================================
// SERIAL EVENT - Read incoming data from Raspberry Pi
// ==================================================================

void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    
    // Check for newline (command complete)
    if (inChar == '\n' || inChar == '\r') {
      if (inputString.length() > 0) {
        stringComplete = true;
      }
    } else {
      inputString += inChar;
    }
  }
}

// ==================================================================
// COMMAND PROCESSING - Parse and execute commands
// ==================================================================

void processCommand(String command) {
  command.trim();  // Remove whitespace
  command.toUpperCase();  // Convert to uppercase for consistency
  
  // Emergency stop
  if (command == "STOP") {
    emergencyStop = true;
    Serial.println("OK STOP");
    return;
  }
  
  // Status request
  if (command == "STATUS") {
    reportStatus();
    return;
  }
  
  // Home command
  if (command == "HOME") {
    moveToHome();
    return;
  }
  
  // Set current position as zero (calibration)
  if (command == "SETZERO") {
    azimuthPosition = 0;
    elevationPosition = 0;
    Serial.println("OK SETZERO - Current position set as home (0, 0)");
    return;
  }
  
  // Speed setting: SPEED <rpm>
  if (command.startsWith("SPEED ")) {
    int speed = command.substring(6).toInt();
    if (speed >= MIN_SPEED && speed <= MAX_SPEED) {
      motorSpeed = speed;
      azimuthMotor->setSpeed(motorSpeed);
      elevationMotor->setSpeed(motorSpeed);
      Serial.print("OK SPEED ");
      Serial.println(motorSpeed);
    } else {
      Serial.print("ERROR Speed must be between ");
      Serial.print(MIN_SPEED);
      Serial.print(" and ");
      Serial.println(MAX_SPEED);
    }
    return;
  }
  
  // Azimuth relative move: AZ <steps>
  if (command.startsWith("AZ ")) {
    long steps = command.substring(3).toInt();
    moveAzimuth(steps);
    return;
  }
  
  // Elevation relative move: EL <steps>
  if (command.startsWith("EL ")) {
    long steps = command.substring(3).toInt();
    moveElevation(steps);
    return;
  }
  
  // Azimuth absolute move: AZABS <steps>
  if (command.startsWith("AZABS ")) {
    long targetPosition = command.substring(6).toInt();
    long steps = targetPosition - azimuthPosition;
    moveAzimuth(steps);
    return;
  }
  
  // Elevation absolute move: ELABS <steps>
  if (command.startsWith("ELABS ")) {
    long targetPosition = command.substring(6).toInt();
    long steps = targetPosition - elevationPosition;
    moveElevation(steps);
    return;
  }
  
  // Unknown command
  Serial.print("ERROR Unknown command: ");
  Serial.println(command);
}

// ==================================================================
// MOTOR MOVEMENT FUNCTIONS
// ==================================================================

void moveAzimuth(long steps) {
  if (steps == 0) {
    Serial.println("OK AZ 0");
    return;
  }
  
  // Determine direction
  uint8_t direction = (steps > 0) ? FORWARD : BACKWARD;
  long absSteps = abs(steps);
  
  // Move motor
  azimuthMotor->step(absSteps, direction, MICROSTEP);
  
  // Update position
  azimuthPosition += steps;
  
  // Motor holds position after movement (holding torque maintained)
  
  // Confirm completion
  Serial.print("OK AZ ");
  Serial.println(steps);
}

void moveElevation(long steps) {
  if (steps == 0) {
    Serial.println("OK EL 0");
    return;
  }
  
  // Check if movement would exceed limits
  long newPosition = elevationPosition + steps;
  if (newPosition > MAX_ELEVATION) {
    Serial.print("ERROR Elevation limit: Cannot exceed +");
    Serial.print(MAX_ELEVATION);
    Serial.print(" steps (requested: ");
    Serial.print(newPosition);
    Serial.println(")");
    return;
  }
  if (newPosition < MIN_ELEVATION) {
    Serial.print("ERROR Elevation limit: Cannot go below ");
    Serial.print(MIN_ELEVATION);
    Serial.print(" steps (requested: ");
    Serial.print(newPosition);
    Serial.println(")");
    return;
  }
  
  // Determine direction
  uint8_t direction = (steps > 0) ? FORWARD : BACKWARD;
  long absSteps = abs(steps);
  
  // Move motor
  elevationMotor->step(absSteps, direction, MICROSTEP);
  
  // Update position
  elevationPosition += steps;
  
  // Motor holds position after movement (holding torque maintained)
  
  // Confirm completion
  Serial.print("OK EL ");
  Serial.println(steps);
}

void moveToHome() {
  Serial.println("Homing...");
  
  // Move azimuth to zero
  moveAzimuth(-azimuthPosition);
  
  // Move elevation to zero
  moveElevation(-elevationPosition);
  
  Serial.println("OK HOME");
}

// ==================================================================
// STATUS REPORTING
// ==================================================================

void reportStatus() {
  Serial.print("POS AZ:");
  Serial.print(azimuthPosition);
  Serial.print(" EL:");
  Serial.println(elevationPosition);
}
