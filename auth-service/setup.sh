#!/bin/bash

# WordPress Auth Service Setup Script
# Run this script to install dependencies and start the service

echo "WordPress Auth Service Setup"
echo "============================"
echo ""

# Check if Python is installed
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.9 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "Found: $PYTHON_VERSION"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies"
    exit 1
fi
echo "Dependencies installed successfully"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.example .env
    echo ".env file created. Please edit it with your WordPress site details."
    echo "You can configure it through the admin interface after starting the service."
else
    echo ""
    echo ".env file already exists"
fi

# Start the service
echo ""
echo "Starting WordPress Auth Service..."
echo "The service will be available at http://localhost:8000"
echo "Press Ctrl+C to stop the service"
echo ""

python3 -m wp_auth_service.main
