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
2)     Device that gathers signal from spectrum analyzer, likely via USB.
3)     Device must take data from spectrum analyzer and create an RSL meter/graph.
4)     Device must connect to phone/tablet to display RSL data to tech. 
        Connection mode might be Bluetooth, peer-to-peer wifi, or cellular data.
5)     App/browser page to display data to tech. 
6)     Documentation for spectrum analyzer, device, and app/browser.
7)     Test bed apparatus with fixed microwave transmitter, and a receiver 
       that can be adjusted for azimuth and elevation by means of turnbuckles and lead screw.  


Design:
The device will use a Raspberry Pi 5 to read the signal from a Rohde & Schwarz ZNLE6 Vector Network Analyzer. 
After computation, the device will upload the RSL readings via an app or web browser to be accessed by the tech
who is manually adjusting the antenna turnbuckles.