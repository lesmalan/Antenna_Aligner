#!/bin/bash
# RSL Controller v01 - Launcher Script
# This script ensures all dependencies are installed before running the GUI
# It allows the application to work correctly after system reboots

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$PROJECT_ROOT/.venv"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}RSL Controller v01 - Launcher${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}Error: Virtual environment not found at $VENV_PATH${NC}"
    echo -e "${YELLOW}Please run: cd $PROJECT_ROOT && python3 -m venv .venv${NC}"
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source "$VENV_PATH/bin/activate"

# Check if requirements.txt exists
REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
if [ -f "$REQUIREMENTS_FILE" ]; then
    echo -e "${YELLOW}Checking dependencies...${NC}"
    
    # Install or update requirements
    pip install --quiet -q --upgrade pip setuptools wheel 2>/dev/null || true
    
    echo -e "${YELLOW}Installing/updating required packages...${NC}"
    pip install -q -r "$REQUIREMENTS_FILE" --quiet 2>&1 | grep -v "already satisfied" || true
    
    echo -e "${GREEN}Dependencies ready!${NC}"
else
    echo -e "${YELLOW}Warning: requirements.txt not found at $REQUIREMENTS_FILE${NC}"
    echo -e "${YELLOW}Installing default packages...${NC}"
    pip install -q numpy pandas scipy PyVISA PyVISA-py pyserial matplotlib fastapi uvicorn websockets simple-websocket-server --quiet 2>&1 | grep -v "already satisfied" || true
fi

echo ""
echo -e "${GREEN}Starting RSL Controller v01...${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# Run the GUI
python "$SCRIPT_DIR/RSL_controller_v01.py"
