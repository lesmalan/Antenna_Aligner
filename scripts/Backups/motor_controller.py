#!/usr/bin/env python3
"""
Motor Controller Interface for Arduino-based Antenna Aligner

This script provides a Python interface to control the stepper motors
via serial communication with an Arduino Uno R3 + Adafruit Motor Shield v3.

Hardware:
  - Arduino Uno R3 with Adafruit Motor Shield v3
  - Two NEMA17 stepper motors (azimuth and elevation)
  - USB serial connection to Raspberry Pi 5

Usage:
  python3 motor_controller.py [--port /dev/ttyUSB0]

Dependencies:
  pip install pyserial

UCO Senior Design Group 2 - Spring 2026
"""

import serial
import time
import argparse
import sys
from typing import Tuple, Optional


class MotorController:
    """
    Interface for controlling antenna alignment stepper motors.
    """
    
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, timeout=5):
        """
        Initialize serial connection to Arduino.
        
        Args:
            port: Serial port (e.g., /dev/ttyUSB0, /dev/ttyACM0)
            baudrate: Communication speed (default: 115200)
            timeout: Read timeout in seconds
        """
        try:
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
            time.sleep(2)  # Wait for Arduino reset after serial connection
            
            # Read startup message
            while self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8').strip()
                print(f"Arduino: {line}")
            
            print(f"Connected to Arduino on {port}")
            
        except serial.SerialException as e:
            print(f"Error: Could not open serial port {port}")
            print(f"Details: {e}")
            sys.exit(1)
    
    def send_command(self, command: str) -> str:
        """
        Send command to Arduino and wait for response.
        
        Args:
            command: Command string (e.g., "AZ 100", "STATUS")
        
        Returns:
            Response from Arduino
        """
        # Send command
        self.ser.write((command + '\n').encode('utf-8'))
        self.ser.flush()
        
        # Wait for response
        response = self.ser.readline().decode('utf-8').strip()
        
        return response
    
    def move_azimuth(self, steps: int) -> bool:
        """
        Move azimuth motor by specified steps.
        
        Args:
            steps: Number of steps (positive = clockwise, negative = counterclockwise)
        
        Returns:
            True if successful, False otherwise
        """
        response = self.send_command(f"AZ {steps}")
        success = response.startswith("OK")
        
        if success:
            print(f"Azimuth moved {steps} steps")
        else:
            print(f"Error: {response}")
        
        return success
    
    def move_elevation(self, steps: int) -> bool:
        """
        Move elevation motor by specified steps.
        
        Args:
            steps: Number of steps (positive = up, negative = down)
        
        Returns:
            True if successful, False otherwise
        """
        response = self.send_command(f"EL {steps}")
        success = response.startswith("OK")
        
        if success:
            print(f"Elevation moved {steps} steps")
        else:
            print(f"Error: {response}")
        
        return success
    
    def move_to_position(self, azimuth_steps: int, elevation_steps: int) -> bool:
        """
        Move to absolute position.
        
        Args:
            azimuth_steps: Target azimuth position in steps
            elevation_steps: Target elevation position in steps
        
        Returns:
            True if successful, False otherwise
        """
        # Move azimuth
        response1 = self.send_command(f"AZABS {azimuth_steps}")
        success1 = response1.startswith("OK")
        
        # Move elevation
        response2 = self.send_command(f"ELABS {elevation_steps}")
        success2 = response2.startswith("OK")
        
        if success1 and success2:
            print(f"Moved to position: AZ={azimuth_steps}, EL={elevation_steps}")
        else:
            print(f"Error: AZ={response1}, EL={response2}")
        
        return success1 and success2
    
    def home(self) -> bool:
        """
        Return both motors to home position (0, 0).
        
        Returns:
            True if successful, False otherwise
        """
        response = self.send_command("HOME")
        success = response.startswith("OK")
        
        if success:
            print("Motors homed")
        else:
            print(f"Error: {response}")
        
        return success
    
    def stop(self) -> bool:
        """
        Emergency stop - release all motors immediately.
        
        Returns:
            True if successful, False otherwise
        """
        response = self.send_command("STOP")
        success = response.startswith("OK")
        
        if success:
            print("Motors stopped")
        else:
            print(f"Error: {response}")
        
        return success
    
    def set_speed(self, rpm: int) -> bool:
        """
        Set motor speed in RPM.
        
        Args:
            rpm: Speed in revolutions per minute (1-100)
        
        Returns:
            True if successful, False otherwise
        """
        response = self.send_command(f"SPEED {rpm}")
        success = response.startswith("OK")
        
        if success:
            print(f"Speed set to {rpm} RPM")
        else:
            print(f"Error: {response}")
        
        return success
    
    def get_status(self) -> Optional[Tuple[int, int]]:
        """
        Get current motor positions.
        
        Returns:
            Tuple of (azimuth_position, elevation_position) or None on error
        """
        response = self.send_command("STATUS")
        
        if response.startswith("POS"):
            # Parse response: "POS AZ:123 EL:456"
            try:
                parts = response.split()
                az = int(parts[1].split(':')[1])
                el = int(parts[2].split(':')[1])
                return (az, el)
            except (IndexError, ValueError):
                print(f"Error parsing status: {response}")
                return None
        else:
            print(f"Error: {response}")
            return None
    
    def close(self):
        """Close serial connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Serial connection closed")


def interactive_mode(controller: MotorController):
    """
    Interactive command-line interface for motor control.
    
    Args:
        controller: MotorController instance
    """
    print("\n=== Antenna Aligner Motor Controller ===")
    print("Commands:")
    print("  az <steps>       - Move azimuth (e.g., 'az 100')")
    print("  el <steps>       - Move elevation (e.g., 'el -50')")
    print("  goto <az> <el>   - Move to absolute position")
    print("  home             - Return to home position")
    print("  speed <rpm>      - Set motor speed")
    print("  status           - Show current positions")
    print("  stop             - Emergency stop")
    print("  quit             - Exit program")
    print()
    
    while True:
        try:
            cmd = input(">>> ").strip().lower()
            
            if not cmd:
                continue
            
            if cmd == "quit" or cmd == "exit":
                break
            
            elif cmd == "home":
                controller.home()
            
            elif cmd == "stop":
                controller.stop()
            
            elif cmd == "status":
                status = controller.get_status()
                if status:
                    print(f"Position - Azimuth: {status[0]} steps, Elevation: {status[1]} steps")
            
            elif cmd.startswith("az "):
                steps = int(cmd.split()[1])
                controller.move_azimuth(steps)
            
            elif cmd.startswith("el "):
                steps = int(cmd.split()[1])
                controller.move_elevation(steps)
            
            elif cmd.startswith("goto "):
                parts = cmd.split()
                az_steps = int(parts[1])
                el_steps = int(parts[2])
                controller.move_to_position(az_steps, el_steps)
            
            elif cmd.startswith("speed "):
                rpm = int(cmd.split()[1])
                controller.set_speed(rpm)
            
            else:
                print(f"Unknown command: {cmd}")
        
        except KeyboardInterrupt:
            print("\nInterrupted")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Control antenna alignment stepper motors via Arduino"
    )
    parser.add_argument(
        "--port",
        default="/dev/ttyUSB0",
        help="Serial port (default: /dev/ttyUSB0)"
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=115200,
        help="Baud rate (default: 115200)"
    )
    
    args = parser.parse_args()
    
    # Create controller instance
    controller = MotorController(port=args.port, baudrate=args.baudrate)
    
    try:
        # Run interactive mode
        interactive_mode(controller)
    
    finally:
        # Clean up
        controller.close()


if __name__ == "__main__":
    main()
