#!/bin/bash
set -e

echo "Setting up development environment..."

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p logs data/models

# Copy and configure environment
if [ ! -f .env ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo "Please update the .env file with your configuration"
fi

if [ ! -f config/config.yaml ]; then
    echo "Creating config file from example..."
    mkdir -p config
    cp config.example.yaml config/config.yaml
    echo "Please update the config/config.yaml file with your configuration"
fi

# Run tests
echo "Running tests..."
pytest tests/ -v

echo ""
echo "Setup complete! Activate the virtual environment with:"
echo "source venv/bin/activate"
echo ""
echo "Then start the application with:"
echo "uvicorn app:app --reload"
