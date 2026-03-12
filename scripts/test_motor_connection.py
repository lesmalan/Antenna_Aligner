#!/usr/bin/env python3
"""
Simple Motor Controller Connection Test

This script tests the connection to the Arduino motor controller
and verifies basic communication.
"""
import serial
import serial.tools.list_ports
import time
import sys


def list_serial_ports():
    """List all available serial ports."""
    print("\n=== Available Serial Ports ===")
    ports = serial.tools.list_ports.comports()
    
    if not ports:
        print("No serial ports found!")
        return []
    
    for i, port in enumerate(ports, 1):
        print(f"{i}. {port.device}")
        print(f"   Description: {port.description}")
        print(f"   Hardware ID: {port.hwid}")
    
    return [port.device for port in ports]


def test_connection(port, baudrate=115200):
    """Test connection to motor controller."""
    print(f"\n=== Testing Connection to {port} ===")
    print(f"Baudrate: {baudrate}")
    
    try:
        print("Opening serial port...")
        ser = serial.Serial(port, baudrate, timeout=2)
        print("✓ Serial port opened")
        
        print("Waiting for Arduino reset (2 seconds)...")
        time.sleep(2)
        
        # Read any startup messages
        print("\nStartup messages:")
        while ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').strip()
            print(f"  Arduino: {line}")
        
        # Test STATUS command
        print("\nSending STATUS command...")
        ser.write(b"STATUS\n")
        ser.flush()
        time.sleep(0.5)
        
        if ser.in_waiting > 0:
            response = ser.readline().decode('utf-8').strip()
            print(f"✓ Response: {response}")
            
            if response.startswith("POS"):
                print("✓ Motor controller is responding correctly!")
                return ser
            else:
                print("⚠ Unexpected response format")
                return ser
        else:
            print("✗ No response from Arduino")
            print("\nPossible issues:")
            print("  1. Wrong serial port selected")
            print("  2. Motor controller sketch not uploaded to Arduino")
            print("  3. Wrong baudrate (expecting 115200)")
            print("  4. Arduino not powered or reset")
            ser.close()
            return None
            
    except serial.SerialException as e:
        print(f"✗ Serial connection error: {e}")
        print("\nPossible issues:")
        print("  1. Port is already in use by another program")
        print("  2. No permission to access the port (try with sudo)")
        print("  3. Arduino not connected")
        return None
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return None


def interactive_test(ser):
    """Interactive motor testing."""
    if not ser:
        return
    
    print("\n=== Interactive Motor Test ===")
    print("Commands:")
    print("  STATUS - Get current position")
    print("  AZ <steps> - Move azimuth (e.g., AZ 10)")
    print("  EL <steps> - Move elevation (e.g., EL 5)")
    print("  HOME - Return to home position")
    print("  SETZERO - Set current position as new home (0, 0)")
    print("  STOP - Emergency stop")
    print("  quit - Exit test")
    print()
    
    try:
        while True:
            cmd = input("Enter command: ").strip()
            
            if cmd.lower() == 'quit':
                break
            
            if not cmd:
                continue
            
            print(f"Sending: {cmd}")
            ser.write((cmd + "\n").encode('utf-8'))
            ser.flush()
            time.sleep(0.5)
            
            if ser.in_waiting > 0:
                response = ser.readline().decode('utf-8').strip()
                print(f"Response: {response}")
            else:
                print("No response")
    
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    finally:
        ser.close()
        print("Serial port closed")


def main():
    """Main test routine."""
    print("=" * 50)
    print("Motor Controller Connection Test")
    print("=" * 50)
    
    # List available ports
    ports = list_serial_ports()
    
    if not ports:
        print("\nNo serial ports found. Make sure Arduino is connected.")
        return
    
    # Get user's port selection
    print("\nSelect port number or enter path (default: /dev/ttyACM0):")
    selection = input("> ").strip()
    
    if not selection:
        port = "/dev/ttyACM0"
    elif selection.isdigit() and 1 <= int(selection) <= len(ports):
        port = ports[int(selection) - 1]
    else:
        port = selection
    
    # Test connection
    ser = test_connection(port)
    
    # If connection successful, offer interactive test
    if ser:
        print("\nConnection successful!")
        response = input("\nRun interactive test? (y/n): ").strip().lower()
        if response == 'y':
            interactive_test(ser)
        else:
            ser.close()
            print("Serial port closed")
    else:
        print("\nConnection test failed.")
        print("Please check Arduino connection and try again.")


if __name__ == "__main__":
    main()
