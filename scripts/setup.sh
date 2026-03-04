#!/bin/bash
# Setup script for new developers

set -e  # Exit on error

echo "Setting up development environment..."

# Check Python version
echo "Checking Python version..."
python --version || python3 --version

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv || python3 -m venv venv
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Install package in development mode
echo "Installing package in development mode..."
pip install -e ".[dev]"

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "Please edit .env with your configuration."
else
    echo ".env already exists."
fi

# Create tmp directory
echo "Creating tmp directory..."
mkdir -p tmp

# Run tests to verify setup
echo ""
echo "Running tests to verify setup..."
pytest

echo ""
echo "Setup complete!"
echo "Activate the virtual environment with: source venv/bin/activate"
