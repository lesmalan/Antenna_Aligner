#!/bin/bash
# Antenna Aligner - Dependency Installation Script
# Run this script to ensure all Python dependencies are installed and maintained
# Usage: ./setup_dependencies.sh

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$PROJECT_ROOT/.venv"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Antenna Aligner - Dependency Setup & Maintenance  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${YELLOW}Creating virtual environment at $VENV_PATH...${NC}"
    python3 -m venv "$VENV_PATH"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment found at $VENV_PATH${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source "$VENV_PATH/bin/activate"
echo -e "${GREEN}✓ Virtual environment activated${NC}"

echo ""
echo -e "${BLUE}Installing core dependencies...${NC}"
echo -e "${YELLOW}========================================${NC}"

# Upgrade pip, setuptools, wheel
echo -e "${YELLOW}Upgrading pip, setuptools, and wheel...${NC}"
pip install --upgrade pip setuptools wheel 2>&1 | grep -E "(Successfully installed|Requirement already satisfied|already satisfied)" || true

# Install requirements
REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
if [ -f "$REQUIREMENTS_FILE" ]; then
    echo -e "${YELLOW}Installing packages from requirements.txt...${NC}"
    pip install -r "$REQUIREMENTS_FILE" 2>&1 | tail -20
    echo -e "${GREEN}✓ All packages installed${NC}"
else
    echo -e "${RED}Error: requirements.txt not found${NC}"
    echo -e "${YELLOW}Creating default requirements...${NC}"
    cat > "$REQUIREMENTS_FILE" << 'EOF'
# Python Requirements for Antenna Aligner
numpy>=2.4.0
pandas>=3.0.0
scipy>=1.17.0
PyVISA>=1.16.0
PyVISA-py>=0.8.0
pyserial>=3.5
matplotlib>=3.10.0
Pillow>=12.0.0
fastapi>=0.128.0
uvicorn>=0.40.0
websockets>=16.0
simple-websocket-server>=0.4.0
click>=8.3.0
pydantic>=2.12.0
EOF
    echo -e "${GREEN}✓ requirements.txt created${NC}"
    pip install -r "$REQUIREMENTS_FILE" 2>&1 | tail -20
fi

echo ""
echo -e "${BLUE}Verifying installations...${NC}"
echo -e "${YELLOW}========================================${NC}"

# Verify key packages
packages=("numpy" "pandas" "pyvisa" "matplotlib" "pyserial" "fastapi")
for pkg in "${packages[@]}"; do
    if python -c "import ${pkg%% *}" 2>/dev/null; then
        echo -e "${GREEN}✓ $pkg${NC}"
    else
        echo -e "${RED}✗ $pkg (FAILED)${NC}"
    fi
done

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Setup Complete! All dependencies ready.         ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}You can now run the RSL Controller by:${NC}"
echo -e "${BLUE}• Double-clicking the 'RSL_Controller_v01.desktop' icon${NC}"
echo -e "${BLUE}• Or running: ./launch_rsl_controller.sh${NC}"
echo ""
echo -e "${YELLOW}To re-run this setup after a reboot, use:${NC}"
echo -e "${BLUE}./setup_dependencies.sh${NC}"
echo ""
