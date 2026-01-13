#!/bin/bash

# Deployment script for Teams-Notion API on Azure VM
# This script handles git pull, dependency updates, and service restart

set -e  # Exit on error

echo "=========================================="
echo "Teams-Notion API Deployment Script"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/opt/teams-notion-api"
SERVICE_NAME="teams-notion-api.service"
VENV_PATH="$PROJECT_DIR/venv"

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    print_error "Please run as root or with sudo"
    exit 1
fi

# Navigate to project directory
if [ ! -d "$PROJECT_DIR" ]; then
    print_error "Project directory not found: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"
print_success "Changed to project directory: $PROJECT_DIR"

# Pull latest changes from git
echo ""
echo "Pulling latest changes from git..."
if git pull; then
    print_success "Git pull successful"
else
    print_error "Git pull failed"
    exit 1
fi

# Activate virtual environment and update dependencies
echo ""
echo "Updating dependencies..."
if [ ! -d "$VENV_PATH" ]; then
    print_warning "Virtual environment not found. Creating new one..."
    python3 -m venv "$VENV_PATH"
    print_success "Virtual environment created"
fi

source "$VENV_PATH/bin/activate"
print_success "Virtual environment activated"

# Upgrade pip
pip install --upgrade pip --quiet
print_success "pip upgraded"

# Install/update dependencies
if pip install -r requirements.txt --quiet; then
    print_success "Dependencies installed/updated"
else
    print_error "Failed to install dependencies"
    exit 1
fi

# Restart systemd service
echo ""
echo "Restarting service..."
if systemctl restart "$SERVICE_NAME"; then
    print_success "Service restarted successfully"
else
    print_error "Failed to restart service"
    exit 1
fi

# Check service status
echo ""
echo "Checking service status..."
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    print_success "Service is running"
    systemctl status "$SERVICE_NAME" --no-pager -l
else
    print_error "Service is not running"
    echo "Check logs with: journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

echo ""
print_success "Deployment completed successfully!"
echo ""
echo "Service logs: journalctl -u $SERVICE_NAME -f"
echo "Service status: systemctl status $SERVICE_NAME"
