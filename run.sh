#!/bin/bash

cd "$(dirname "$0")"

# Check if virtual environment already exists
if [ -d "./.venv" ]; then
    echo "Virtual environment already exists."
else
    echo "Creating virtual environment..."
	python -m venv --system-site-packages ./.venv
fi

export PYTHONUNBUFFERED=1

# Activate the virtual environment
source ./.venv/bin/activate

# Install required packages
pip install -r requirements.txt

# Run the application
echo "Starting..."
python main.py &> ipmpv.log
