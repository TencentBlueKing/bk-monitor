#!/bin/bash

# Install virtualenv
pip install virtualenv

# Change to the project directory
cd /app/code/bkmonitor

# Create virtual environment
if [ ! -d "venv" ]; then
  virtualenv venv
fi

# Set up environment variables
source /app/code/bkmonitor/venv/bin/activate

python -m ensurepip --default-pip

pip install -r requirements_dev.txt
