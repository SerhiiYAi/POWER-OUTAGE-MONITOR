#!/bin/bash
set -e

echo "Running tests for power-outage-monitor..."

# Install test dependencies
pip install -e ".[test]"

# Run tests with coverage
pytest tests/ --cov=power_outage_monitor --cov-report=html --cov-report=term-missing

echo "Tests completed successfully!"