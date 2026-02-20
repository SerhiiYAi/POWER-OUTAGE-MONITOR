#!/bin/bash
set -e

echo "Building power-outage-monitor package..."

# Clean previous builds
rm -rf build/ dist/ *.egg-info/

# Install build dependencies
pip install --upgrade pip setuptools wheel build

# Build the package
python -m build

echo "Build completed successfully!"
echo "Distribution files created in dist/"
ls -la dist/