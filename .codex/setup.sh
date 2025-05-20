#!/bin/bash
set -e

# Install system packages
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y curl python3 python3-pip python3-venv nodejs npm git

# Install yarn globally
npm install -g yarn

# Create Python virtual environment
python3 -m venv venv
. venv/bin/activate
pip install --upgrade pip
pip install -e pypi

# Install node dependencies
if [ -f yarn.lock ]; then
  yarn install --frozen-lockfile
fi
