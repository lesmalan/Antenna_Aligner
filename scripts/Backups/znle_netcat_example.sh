#!/usr/bin/env bash
set -euo pipefail

# ZNLE6 SCPI over TCP using netcat
# Usage:
#   ./znle_netcat_example.sh [IP] [PORT] [START_HZ] [STOP_HZ] [POINTS] [PARAM] [OUT_CSV]
# Defaults:
#   IP=192.168.15.90 PORT=5025 START=9e9 STOP=11e9 POINTS=201 PARAM=S21 OUT=trace.csv
# Example:
#   ./znle_netcat_example.sh 192.168.15.90 5025 10e9 10.1e9 401 S21 s21.csv

IP=${1:-192.168.15.90}
PORT=${2:-5025}
START_FREQ=${3:-9e9}
STOP_FREQ=${4:-11e9}
POINTS=${5:-201}
PARAM=${6:-S21}
OUT=${7:-trace.csv}

if ! command -v nc >/dev/null 2>&1; then
  echo "Error: netcat (nc) is required." >&2
  exit 1
fi

# Configure trace and sweep (no response expected)
nc -w 3 "$IP" "$PORT" <<EOF
FORM:DATA ASCii
CALC:PAR:DEF 'Trc1',$PARAM
CALC:PAR:SEL 'Trc1'
SENS:FREQ:STAR $START_FREQ
SENS:FREQ:STOP $STOP_FREQ
SENSe:SWEep:POINts $POINTS
CALC:FORM MLOG
INIT:CONT OFF
EOF

# Trigger sweep and fetch formatted amplitude data
DATA_LINE=$(nc -w 10 "$IP" "$PORT" <<EOF
INIT;*WAI
CALC:DATA? FDATA
EOF
)

# Parse comma-separated amplitudes and build frequency axis
IFS=',' read -r -a AMPS <<< "$DATA_LINE"

if [ "${#AMPS[@]}" -ne "$POINTS" ]; then
  echo "Warning: received \${#AMPS[@]} points, expected $POINTS" >&2
fi

STEP=$(awk "BEGIN{print ($STOP_FREQ-$START_FREQ)/($POINTS-1)}")

# Write CSV: freq_Hz,amp_dB
{
  echo "freq_Hz,amp_dB"
  for ((i=0;i<${#AMPS[@]};i++)); do
    FREQ=$(awk -v s="$START_FREQ" -v st="$STEP" -v idx="$i" 'BEGIN{printf("%0.6f", s + idx*st)}')
    AMP=$(echo "${AMPS[$i]}" | tr -d ' \r\n')
    echo "$FREQ,$AMP"
  done
} > "$OUT"

echo "Saved trace to $OUT"