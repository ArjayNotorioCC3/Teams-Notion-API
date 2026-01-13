#!/bin/bash

# Quick start script for Teams-Notion middleware local development
# This script helps set up and run the middleware with ngrok

set -e  # Exit on error

echo "=========================================="
echo "Teams-Notion Middleware Quick Start"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

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

print_info() {
    echo -e "${NC}ℹ $1${NC}"
}

# Check if .env file exists
if [ ! -f .env ]; then
    print_error ".env file not found!"
    print_info "Please create .env file from .env example:"
    print_info "  cp '.env example' .env"
    print_info "Then edit .env with your credentials"
    exit 1
fi

print_success "Found .env file"

# Check if venv exists
if [ ! -d "venv" ]; then
    print_warning "Virtual environment not found. Creating one..."
    python3 -m venv venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    print_warning "Dependencies not installed. Installing..."
    pip install -r requirements.txt
    print_success "Dependencies installed"
else
    print_success "Dependencies already installed"
fi

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    print_error "ngrok not found!"
    print_info "Please install ngrok from https://ngrok.com/download"
    exit 1
fi

print_success "ngrok found"

# Check if .env has required fields
print_info "Checking .env configuration..."

source .env

if [ -z "$MICROSOFT_CLIENT_ID" ] || [ "$MICROSOFT_CLIENT_ID" = "your_client_id_here" ]; then
    print_error "MICROSOFT_CLIENT_ID not configured"
    exit 1
fi

if [ -z "$WEBHOOK_NOTIFICATION_URL" ] || [[ "$WEBHOOK_NOTIFICATION_URL" == *"localhost"* ]]; then
    print_warning "WEBHOOK_NOTIFICATION_URL uses localhost"
    print_info "You'll need to update this with ngrok URL after starting ngrok"
fi

if [ -z "$WEBHOOK_CLIENT_STATE" ] || [ "$WEBHOOK_CLIENT_STATE" = "your_secret_client_state_here" ]; then
    print_warning "WEBHOOK_CLIENT_STATE not configured"
fi

print_success "Configuration check passed"
echo ""

# Ask if user wants to start ngrok
echo "=========================================="
read -p "Do you want to start ngrok now? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Starting ngrok on port 8000..."
    print_warning "Copy the HTTPS URL (e.g., https://abc123.ngrok.io)"
    print_info "Then update WEBHOOK_NOTIFICATION_URL in .env and restart the server"
    echo ""
    
    # Start ngrok in background
    ngrok http 8000
else
    print_info "Skipping ngrok. Please start it manually if needed:"
    print_info "  ngrok http 8000"
fi

echo ""
echo "=========================================="
print_info "To start the server:"
echo "  source venv/bin/activate"
echo "  uvicorn main:app --reload --host 0.0.0.0 --port 8000"
echo ""
print_info "To test the endpoints:"
echo "  python3 test_local.py"
echo ""
print_info "To create a subscription:"
echo "  curl -X POST 'http://localhost:8000/subscription/create' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"resource\": \"teams/{teamId}/channels/{channelId}/messages\", \"change_types\": [\"created\"], \"expiration_days\": 1}'"
echo "=========================================="
