# Contributing to Power Outage Monitor

Thank you for your interest in contributing! Here's how you can help:

## Development Setup

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/power-outage-monitor.git`
3. Create a virtual environment: `python -m venv venv`
4. Activate it: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
5. Install in development mode: `pip install -e ".[dev]"`

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=power_outage_monitor