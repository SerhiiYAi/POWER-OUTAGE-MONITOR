#!/bin/bash
set -e

echo "Deploying power-outage-monitor package..."

# Check if we're in a clean git state
if [[ -n $(git status --porcelain) ]]; then
    echo "Error: Working directory is not clean. Please commit your changes first."
    exit 1
fi

# Run tests first
./scripts/test.sh

# Build the package
./scripts/build.sh

# Upload to PyPI (requires proper credentials)
echo "Uploading to PyPI..."
pip install --upgrade twine
twine check dist/*
twine upload dist/*

echo "Deployment completed successfully!"