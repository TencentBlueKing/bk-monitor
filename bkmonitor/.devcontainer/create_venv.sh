#!/bin/bash

# Set up extra pip mirror
echo "extra-index-url = ${EXTRA_PIP_MIRROR}/\n" >> ~/.pip/pip.conf 

# Install virtualenv
pip install virtualenv

# Change to the project directory
cd /app/code/bkmonitor

# Create virtual environment
virtualenv venv
source venv/bin/activate

# Install dependencies
grep -v "dataclasses" requirements.txt | grep -v "#" | xargs pip install
pip install betterproto==2.0.0b5

# Set up environment variables
export VIRTUAL_ENV=/app/code/bkmonitor/venv
export PATH="$VIRTUAL_ENV/bin:$PATH"
