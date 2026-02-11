UCO School of Engineering
Spring 2026
Senior Design II
Group 2

Collaborators:
Lorelei Potter
Brett Bailey
Les Malan

Project: LoS Antenna Alignment System

Description: In collaboration with the FAA, this project is to design a
device or system that will make the alignment process for line-of-sight 
antenna systems easier and less time consuming. The LoS antennas used by 
the FAA use microwave frequency to transmit data. The received signal
level, or RSL, of the signal is used to align the antennas. 

Deliverables:
1)     Connection from SMA connector on antenna to spectrum analyzer. 
2)     Device that gathers signal from spectrum analyzer, likely via USB/Network.
3)     Device must take data from spectrum analyzer and create an RSL meter/graph.
4)     Device must connect to phone/tablet to display RSL data to tech. 
        Connection mode might be Bluetooth, peer-to-peer wifi, or cellular data.
5)     App/browser page to display data to tech. 
6)     Documentation for spectrum analyzer, device, and app/browser.
7)     Test bed apparatus with fixed microwave transmitter, and a receiver 
       that can be adjusted for azimuth and elevation by means of turnbuckles and/or lead screw.  


Design:
The device will use a Raspberry Pi 5 to read the signal from a Rohde & Schwarz ZNLE6 Vector Network Analyzer. 
After computation, the device will upload the RSL readings via an app or web browser to be accessed by the tech
who is manually adjusting the antenna turnbuckles.


Hardware Configuration:
=======================

1. Transmitter Chain
   - Signal Generator: NanoVNA-H4
   - Operating Frequency: 977 MHz
   - Signal Amplifier: 40 dB amplifier circuit
   - Amplifier Power: 5V
   - Transmit Antenna: RFSpace TSA900 UWB (Ultra-Wideband)
   - Antenna Frequency Range: 900-12000 MHz
   - Purpose: Generates and transmits amplified RF signal for alignment testing

2. Receiver Chain
   - Receive Antenna: Pasco WA-9800A microwave receiver
   - Antenna Power: 9V adapter
   - Output Connection: Alligator clips to internal antenna output nodes
   - Signal Path: Alligator clips → adapters → ZNLE6 Port 1
   - Purpose: Captures transmitted signal for RSL measurements

3. Vector Network Analyzer
   - Model: Rohde & Schwarz ZNLE6
   - IP Address: 192.168.15.90
   - SCPI Port: 5025
   - Connection: Ethernet (TCP/IP)
   - Frequency Range: 9 kHz to 6 GHz
   - Input: Port 1 receives signal from WA-9800A receiver
   - Purpose: Measures received signal strength (RSL) for antenna alignment

4. Control Computer
   - Model: Raspberry Pi 5
   - Operating System: Linux (Raspberry Pi OS)
   - Network: Wireless connection to GL iNet router
   - Software: Python 3 with virtual environment
   - Purpose: Runs control scripts, GUI applications, and WebSocket server

5. Network Configuration
   - Router: GL iNet AC1200 wireless router
   - WAN Connection: Router connects to internet via WAN port
   - ZNLE6 VNA: 192.168.15.90:5025 (Ethernet connection to router)
   - Raspberry Pi 5: Wireless connection to router
   - Development PC: Wireless connection to router
   - Application Emulator: Wireless connection to router
   - Raspberry Pi WebSocket Server: Port 8000
   - TCP Control Server: Port 8000

6. Software Environment
   - Python Virtual Environment: .venv
   - Key Dependencies: pyvisa, pyvisa-py, matplotlib, numpy, tkinter, websockets
   - GUI Applications: znle_gui.py, frequency_scanner_gui.py
   - Backend Scripts: znle_pyvisa.py, find_quiet_frequencies.py, pi_tcp_server.py

7. Test Bed Apparatus
   - Fixed microwave transmitter position
   - 3D printed adjustable receiver mount with motorized azimuth and elevation control
   - Purpose: Controlled testing environment for antenna alignment system
   
   Receiver Mount Assembly:
   - Two 3D printed side brackets that cradle the Pasco WA-9800A receiver
   - U-shaped bracket arm connects to rotation points on side brackets
   - U-bracket enables up/down rotation for elevation adjustment
   
   Elevation Control (Up-Down Axis):
   - NEMA17 stepper motor mounted on left side of U-bracket arm
   - Motor shaft interfaces with left side bracket via keyed opening
   - Right side uses round pivot pin connecting to hole in right side bracket
   - Provides precise elevation angle control
   
   Azimuth Control (Rotational Axis):
   - NEMA17 stepper motor positioned vertically in center of base
   - Motor pin interfaces with keyed hole on base of U-bracket
   - Rotates entire receiver assembly left and right for azimuthal positioning
   
   Base Structure:
   - 3D printed base section with 4 legs for stability
   - Central mounting point for vertical azimuth motor
   - Supports full receiver assembly and rotation mechanisms