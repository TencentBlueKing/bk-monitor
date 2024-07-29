#!/bin/bash

# Set up extra pip mirror
echo "extra-index-url = ${EXTRA_PIP_MIRROR}/\n" >> ~/.pip/pip.conf 

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

# Install dependencies
grep -v "dataclasses" requirements.txt | grep -v "#" | xargs pip install
pip install betterproto==2.0.0b5
