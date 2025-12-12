#!/bin/bash
#
# SeekMateAI VPS Server Setup Script
# Run this script on your Ubuntu/Debian VPS to install all dependencies
#
# Usage: bash server_setup.sh

set -e  # Exit on error

echo "=========================================="
echo "SeekMateAI VPS Server Setup"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Please do not run as root. Run as a regular user with sudo privileges.${NC}"
   exit 1
fi

echo -e "${GREEN}Step 1: Updating system packages...${NC}"
sudo apt update && sudo apt upgrade -y

echo -e "${GREEN}Step 2: Installing essential tools...${NC}"
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    wget \
    curl \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    unzip \
    htop

echo -e "${GREEN}Step 3: Installing Google Chrome...${NC}"
if command -v google-chrome &> /dev/null; then
    echo -e "${YELLOW}Chrome already installed, skipping...${NC}"
    google-chrome --version
else
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
    sudo apt update
    sudo apt install -y google-chrome-stable
    
    echo -e "${GREEN}Chrome installed successfully!${NC}"
    google-chrome --version
fi

echo -e "${GREEN}Step 4: Creating application directory...${NC}"
mkdir -p ~/seekmateai
cd ~/seekmateai

echo -e "${GREEN}Step 5: Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}Virtual environment created${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists${NC}"
fi

source venv/bin/activate

echo -e "${GREEN}Step 6: Upgrading pip...${NC}"
pip install --upgrade pip

echo -e "${GREEN}Step 7: Installing Python dependencies...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}Dependencies installed${NC}"
else
    echo -e "${YELLOW}requirements.txt not found. Please add it to ~/seekmateai/${NC}"
fi

echo ""
echo -e "${GREEN}=========================================="
echo -e "Setup completed successfully!${NC}"
echo -e "${GREEN}=========================================="
echo ""
echo "Next steps:"
echo "1. Upload your SeekMateAI files to ~/seekmateai/"
echo "2. Create or copy your config.json file"
echo "3. Test the installation:"
echo "   cd ~/seekmateai"
echo "   source venv/bin/activate"
echo "   export RUN_HEADLESS=true"
echo "   python main.py"
echo "4. Set up the systemd service:"
echo "   sudo cp seekmateai.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable seekmateai"
echo "   sudo systemctl start seekmateai"
echo ""
echo -e "${YELLOW}Note: Remember to update the paths in seekmateai.service${NC}"
echo -e "${YELLOW}to match your username and directory structure!${NC}"
echo ""

