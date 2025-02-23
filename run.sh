#!/bin/bash

# Check if virtual environment already exists
if [ -d "./.venv" ]; then
    echo "Virtual environment already exists."
else
    echo "Creating virtual environment..."
	python -m venv --system-site-packages ./.venv
fi

# Activate the virtual environment
source ./.venv/bin/activate

# Install required packages
pip install -r requirements.txt

# Run the application
echo "Starting..."
python main.py
