#!/usr/bin/env python3
"""
R&S ZNLE6 control via PyVISA over TCP/IP.
Fetch formatted amplitude data (e.g., S21 in dB) and save CSV.

Usage:
  python3 znle_pyvisa.py --ip 192.168.15.90 --start 10e9 --stop 10.1e9 \
      --points 401 --param S21 --out s21.csv

Requires:
  pip install pyvisa pyvisa-py
"""
from __future__ import annotations
import argparse
import math
import sys

try:
    import pyvisa as visa
except Exception as exc:
    print("Error: pyvisa not installed. pip install pyvisa pyvisa-py", file=sys.stderr)
    raise


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip", default="192.168.15.90", help="Instrument IP")
    ap.add_argument("--port", default=5025, type=int, help="SCPI socket port (usually 5025)")
    ap.add_argument("--start", default=float(9e9), type=float, help="Start frequency (Hz)")
    ap.add_argument("--stop", default=float(11e9), type=float, help="Stop frequency (Hz)")
    ap.add_argument("--points", default=201, type=int, help="Sweep points")
    ap.add_argument("--param", default="S21", help="Trace parameter (S11/S21/S12/S22)")
    ap.add_argument("--out", default="trace.csv", help="Output CSV path")
    args = ap.parse_args()

    rm = visa.ResourceManager("@py")  # use pyvisa-py backend
    # Raw socket resource string; alternatively: f"TCPIP::{args.ip}::INSTR"
    resource = f"TCPIP0::{args.ip}::{args.port}::SOCKET"
    inst = rm.open_resource(resource)
    inst.timeout = 15000
    inst.write_termination = "\n"
    inst.read_termination = "\n"

    # Basic sanity
    idn = inst.query("*IDN?")
    print(f"Connected: {idn}")

    # Configure measurement
    inst.write("FORM:DATA ASCii")
    inst.write(f"CALC:PAR:DEF 'Trc1',{args.param}")
    inst.write("CALC:PAR:SEL 'Trc1'")
    inst.write(f"SENS:FREQ:STAR {args.start}")
    inst.write(f"SENS:FREQ:STOP {args.stop}")
    inst.write(f"SENSe:SWEep:POINts {args.points}")
    inst.write("CALC:FORM MLOG")  # log magnitude (dB)
    inst.write("INIT:CONT OFF")

    # Trigger and fetch formatted data
    inst.write("INIT")
    inst.query("*OPC?")  # wait for operation complete
    data_str = inst.query("CALC:DATA? FDATA")
    amps = [float(x) for x in data_str.strip().split(",") if x.strip()]

    if len(amps) != args.points:
        print(f"Warning: received {len(amps)} points, expected {args.points}")

    step = (args.stop - args.start) / (max(1, args.points - 1))

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("freq_Hz,amp_dB\n")
        for i, amp in enumerate(amps):
            freq = args.start + i * step
            f.write(f"{freq:.6f},{amp}\n")

    print(f"Saved trace to {args.out}")


if __name__ == "__main__":
    main()
