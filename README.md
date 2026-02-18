# Power Outage Monitor

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests](https://img.shields.io/badge/tests-pytest-green.svg)](https://pytest.org/)

Automated monitoring
 and calendar integration system for power outage schedules from the Lviv energy company website. Fetches, parses, and stores outage schedules, and generates Google Calendar-compatible ICS files with Ukraine timezone support.

## 🚀 Features

- 🔍 **Web Scraping**: Extracts power outage schedules from https://poweron.loe.lviv.ua/
- 🌐 **JavaScript Support**: Handles JavaScript-rendered content using Selenium WebDriver
- 🇺🇦 **Ukrainian Text Processing**: Parses Ukrainian text and normalizes dates/times
- 💾 **Database Storage**: Stores all data in a local SQLite database with event tracking
- 📅 **Calendar Integration**: Generates individual and combined ICS files for Google Calendar
- ⏰ **Flexible Events**: Supports both all-day and timed events
- 🔄 **State Management**: Maintains event state and handles event deletions
- 🎯 **Group Filtering**: Filter monitoring by specific group codes via CLI or JSON file
- 🔁 **Continuous Monitoring**: Configurable interval monitoring mode
- 📊 **Data Export**: Export data to CSV format
- 📝 **Comprehensive Logging**: Detailed logging and error handling
- 🌍 **Timezone Support**: Proper Ukraine timezone handling

## 📋 Table of Contents

- [Installation](#installation)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Output Files](#output-files)
- [Python API](#python-api)
- [Command Line Interface](#command-line-interface)
- [Development](#development)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## 📦 Installation

### From PyPI (when published)
```bash
pip install power-outage-monitor
From Source
bash


# Clone the repository
git clone https://github.com/yourusername/power-outage-monitor.git
cd power-outage-monitor

# Install in development mode
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
Using pip from GitHub
bash


pip install git+https://github.com/yourusername/power-outage-monitor.git
🔧 Requirements
System Requirements
Python 3.7+
Google Chrome browser
ChromeDriver (matching your Chrome version)
Python Dependencies
selenium>=4.0.0 - Web automation and scraping
pytz>=2021.1 - Timezone handling
Development Dependencies (optional)
pytest>=6.0 - Testing framework
pytest-cov>=2.0 - Coverage reporting
black>=21.0 - Code formatting
mypy>=0.800 - Type checking
flake8>=3.8 - Linting
🚀 Quick Start
Basic Usage
bash


# Run single monitoring cycle
power-outage-monitor

# Or using Python module
python -m power_outage_monitor.main
First Run Example
bash


# 1. Install the package
pip install power-outage-monitor

# 2. Run with specific groups
power-outage-monitor --groups 1.1,2.1,3.2

# 3. Check output directory for generated files
ls output/
# Expected files:
# - group_1.1.ics
# - group_2.1.ics  
# - group_3.2.ics
# - all_groups_combined.ics
# - power_outages.db
⚙️ Configuration
Group Filtering
Via Command Line
bash


# Monitor specific groups
power-outage-monitor --groups 1.1,2.1,3.2

# Monitor all groups (default)
power-outage-monitor
Via JSON File
Create a groups.json file:

json


{
  "group": ["1.1", "2.1", "3.2", "4.1"]
}
Then run:

bash


power-outage-monitor --groups-file groups.json
Continuous Monitoring
bash


# Monitor every hour (3600 seconds)
power-outage-monitor --continuous --interval 3600

# Monitor every 15 minutes
power-outage-monitor --continuous --interval 900

# Monitor every 5 minutes with specific groups
power-outage-monitor --continuous --interval 300 --groups 1.1,2.1
Supported Group Codes
The system supports group codes in format X.Y where:

X: 1-6 (main group)
Y: 1-6 (subgroup)
Examples: 1.1, 1.2, 2.3, 3.1, 4.5, 6.6

Common Groups:



1.1, 1.2, 1.3, 1.4, 1.5, 1.6
2.1, 2.2, 2.3, 2.4, 2.5, 2.6
3.1, 3.2, 3.3, 3.4, 3.5, 3.6
4.1, 4.2, 4.3, 4.4, 4.5, 4.6
5.1, 5.2, 5.3, 5.4, 5.5, 5.6
6.1, 6.2, 6.3, 6.4, 6.5, 6.6
📁 Output Files
The application generates several output files in the specified output directory (default: ./output/):

ICS Calendar Files
group_X.Y.ics - Individual calendar files for each group
all_groups_combined.ics - Combined calendar with all groups
Compatible with: Google Calendar, Outlook, Apple Calendar, and other calendar applications
Database
power_outages.db - SQLite database with all historical data
Tables:
outage_periods - Raw outage data
events - Processed calendar events
event_tracking - Event state management
CSV Export
outages_export.csv - Exported data in CSV format (when using export functionality)
Example Output Structure


output/
├── group_1.1.ics
├── group_2.1.ics
├── group_3.2.ics
├── all_groups_combined.ics
├── power_outages.db
└── outages_export.csv
🐍 Python API
Basic Usage
python


from power_outage_monitor import PowerOutageMonitor, Config

# Create configuration
config = Config(
    groups=['1.1', '2.1'],
    continuous=True,
    interval=1800,  # 30 minutes
    debug=True
)

# Create and run monitor
monitor = PowerOutageMonitor(config)
success, message = monitor.run_full_process()

if success:
    print(f"✅ {message}")
else:
    print(f"❌ {message}")
Quick Start Function
python


from power_outage_monitor import quick_start

# Quick setup and run
monitor = quick_start(
    groups=['1.1', '2.1'],
    continuous=True,
    interval=3600,
    debug=True
)

# Run single cycle
success, message = monitor.run_full_process()
Database Operations
python


from power_outage_monitor import PowerOutageDatabase
from pathlib import Path

# Connect to database
db = PowerOutageDatabase(Path("power_outages.db"))

# Get all outage periods
periods = db.get_outage_periods()
print(f"Found {len(periods)} outage periods")

# Get filtered periods
periods = db.get_outage_periods(group_filter=['1.1', '2.1'])


# Export to CSV
db.export_to_csv("my_export.csv")

# Clean old data (older than 30 days)
db.clear_old_periods(days=30)

# Close connection
db.close()
ICS Generation
python


from power_outage_monitor import ICSEventGenerator
from pathlib import Path

# Create ICS generator
generator = ICSEventGenerator(Path("output"))

# Generate individual files for each group
success = generator.create_individual_ics_files(periods)

# Generate combined file with all groups
success = generator.create_combined_ics_file(periods)
Advanced Configuration
python


from power_outage_monitor import Config, PowerOutageMonitor
from pathlib import Path

# Advanced configuration
config = Config(
    url="https://poweron.loe.lviv.ua/",
    output_dir=Path("/custom/output/path"),
    db_path=Path("/custom/database.db"),
    groups=['1.1', '2.1', '3.2'],
    continuous=True,
    interval=1800,
    debug=True
)

# Create monitor with custom config
monitor = PowerOutageMonitor(config)

# Run continuous monitoring
monitor.run_continuous_monitoring()
💻 Command Line Interface
Basic Commands
bash


# Show help
power-outage-monitor --help

# Run with default settings
power-outage-monitor

# Enable debug logging
power-outage-monitor --debug
Group Filtering
bash


# Monitor specific groups
power-outage-monitor --groups 1.1,2.1,3.2

# Use groups from JSON file
power-outage-monitor --groups-file groups.json

# Monitor all groups (default behavior)
power-outage-monitor
Continuous Monitoring
bash


# Monitor every hour
power-outage-monitor --continuous --interval 3600

# Monitor every 15 minutes with debug
power-outage-monitor --continuous --interval 900 --debug

# Monitor specific groups every 30 minutes
power-outage-monitor --continuous --interval 1800 --groups 1.1,2.1
Custom Paths
bash


# Custom output directory
power-outage-monitor --output-dir /path/to/output

# Custom database path
power-outage-monitor --db-path /path/to/database.db

# Both custom paths
power-outage-monitor --output-dir ./my_output --db-path ./my_data.db
Complete Examples
bash


# Example 1: Monitor specific groups every 30 minutes
power-outage-monitor --groups 1.1,2.1,3.2 --continuous --interval 1800

# Example 2: Single run with debug and custom output
power-outage-monitor --debug --output-dir ./results

# Example 3: Production monitoring setup
power-outage-monitor --continuous --interval 3600 --groups-file production_groups.json
🛠️ Development
Setup Development Environment
bash


# Clone repository
git clone https://github.com/yourusername/power-outage-monitor.git
cd power-outage-monitor

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e ".[dev]"
Running Tests
bash


# Run all tests
pytest

# Run with coverage report
pytest --cov=power_outage_monitor --cov-report=html

# Run specific test file
pytest tests/test_config.py

# Run with verbose output
pytest -v

# Run tests and generate coverage report
pytest --cov=power_outage_monitor --cov-report=term-missing
Code Quality
bash


# Format code with Black
black src/ tests/

# Check code formatting
black --check src/ tests/

# Run type checking
mypy src/

# Run linting
flake8 src/ tests/
Building Package
bash


# Install build dependencies
pip install build

# Build wheel and source distribution
python -m build

# Check distribution
twine check dist/*
Using Build Scripts
bash


# Make scripts executable
chmod +x scripts/*.sh

# Run tests
./scripts/test.sh

# Build package
./scripts/build.sh

# Deploy to Test PyPI
./scripts/deploy.sh
📂 Project Structure


power-outage-monitor/
├── src/
│   └── power_outage_monitor/
│       ├── __init__.py          # Package initialization and public API
│       ├── main.py              # Main entry point
│       ├── monitor.py           # Main orchestrator with event tracking

│       ├── scraper.py           # Web scraping and parsing logic
│       ├── db.py                # Database operations with event tracking
│       ├── config.py            # Configuration management
│       ├── icsgen.py            # ICS event generation
│       └── utils.py             # Utility functions and helpers
├── tests/
│   ├── __init__.py
│   ├── test_config.py           # Configuration tests
│   ├── test_db.py               # Database tests
│   ├── test_icsgen.py           # ICS generation tests
│   ├── test_utils.py            # Utility function tests
│   ├── test_monitor.py          # Monitor integration tests
│   └── fixtures/                # Test data and fixtures
├── scripts/
│   ├── build.sh                 # Build script
│   ├── test.sh                  # Test script
│   └── deploy.sh                # Deployment script
├── requirements/
│   ├── base.txt                 # Base requirements
│   ├── dev.txt                  # Development requirements
│   └── test.txt                 # Test requirements
├── docs/
│   ├── README.md                # This file
│   ├── CHANGELOG.md             # Version history
│   └── API.md                   # API documentation
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions CI
├── pyproject.toml               # Project configuration
├── setup.py                     # Setup script (for compatibility)
├── MANIFEST.in                  # Package manifest
├── .gitignore                   # Git ignore rules
├── LICENSE                      # GPL v3.0 License
└── README.md                    # This file
🔧 Troubleshooting
ChromeDriver Issues
Problem: selenium.common.exceptions.WebDriverException: Message: 'chromedriver' executable needs to be in PATH

Solutions:

Download ChromeDriver: https://chromedriver.chromium.org/
Match Chrome version: Ensure ChromeDriver version matches your Chrome browser
Add to PATH:
bash


# Linux/Mac
export PATH=$PATH:/path/to/chromedriver

# Windows
set PATH=%PATH%;C:\path\to\chromedriver
Alternative: Place chromedriver.exe in the project directory
Ukrainian Text Issues on Windows
Problem: Garbled Ukrainian text in output

Solutions:

bash


# Set console code page to UTF-8
chcp 65001

# Or run Python with UTF-8 encoding
set PYTHONIOENCODING=utf-8
python -m power_outage_monitor.main
The application automatically configures Windows console for UTF-8 encoding, but manual setup may be needed in some cases.

Database Issues
Problem: sqlite3.OperationalError: database is locked

Solutions:

Ensure no other instances are running
Check file permissions on database file
Close any database browser tools (DB Browser for SQLite, etc.)
Restart the application
Problem: Database corruption

Solutions:

bash


# Backup and recreate database
mv power_outages.db power_outages.db.backup
power-outage-monitor  # Will create new database
Memory Issues
Problem: High memory usage with large datasets

Solutions:

Use group filtering to reduce data volume:
bash


power-outage-monitor --groups 1.1,2.1  # Instead of all groups
Increase monitoring interval:
bash


power-outage-monitor --continuous --interval 7200  # Every 2 hours
Clean old data regularly:
python


from power_outage_monitor import PowerOutageDatabase
db = PowerOutageDatabase("power_outages.db")
db.clear_old_periods(days=30)  # Keep only last 30 days
Network Issues
Problem: Connection timeouts or network errors

Solutions:

Check internet connection
Verify the website is accessible: https://poweron.loe.lviv.ua/
Try running with debug mode:
bash


power-outage-monitor --debug
Increase timeout in code if needed
Installation Issues
Problem: pip install fails

Solutions:

bash


# Upgrade pip first

python -m pip install --upgrade pip

# Install with verbose output
pip install -v power-outage-monitor

# Install from source if PyPI fails
pip install git+https://github.com/yourusername/power-outage-monitor.git
🤝 Contributing
We welcome contributions! Here's how you can help:

Getting Started
Fork the repository on GitHub
Clone your fork locally:
bash


git clone https://github.com/yourusername/power-outage-monitor.git
Create a new branch for your feature:
bash


git checkout -b feature-awesome-feature
Development Process
Setup development environment:
bash


pip install -e ".[dev]"
Make your changes
Add tests for new functionality
Run tests to ensure everything works:
bash


pytest
Format your code:
bash


black src/ tests/
Commit your changes:
bash


git commit -am "Add awesome feature"
Push to your fork:
bash


git push origin feature-awesome-feature
Create a Pull Request on GitHub
Contribution Guidelines
Code Style: Use Black for formatting
Tests: Add tests for new features
Documentation: Update README and docstrings
Commits: Use clear, descriptive commit messages
Issues: Reference issue numbers in commits when applicable
Types of Contributions
🐛 Bug fixes
✨ New features
📚 Documentation improvements
🧪 Test coverage improvements
🔧 Performance optimizations
🌐 Internationalization
📄 License
This project is licensed under the GNU General Public License v3.0 - see the LICENSE file for details.

What this means:
✅ Commercial use - You can use this software commercially
✅ Modification - You can modify the software
✅ Distribution - You can distribute the software
✅ Patent use - You can use any patents related to the software
✅ Private use - You can use the software privately
Requirements:
📋 License and copyright notice - Include the license and copyright notice
📋 State changes - Document any changes made to the software
📋 Disclose source - Make source code available when distributing
📋 Same license - Derivative works must use the same license
For more information, visit: https://www.gnu.org/licenses/gpl-3.0.html

📞 Support
Getting Help
🐛 Bug Reports: GitHub Issues
💬 Questions: GitHub Discussions
📖 Documentation: This README and inline code documentation
Before Reporting Issues
Check existing issues to avoid duplicates
Update to the latest version
Include relevant information:
Python version
Operating system
Chrome/ChromeDriver versions
Full error messages
Steps to reproduce
Feature Requests
We welcome feature requests! Please:

Check if the feature already exists
Describe the use case clearly
Explain why it would be beneficial
Consider contributing the feature yourself
🙏 Acknowledgments
Lviv Energy Company for providing the outage schedule data
Selenium Project for excellent web automation tools
Python Community for amazing packaging and development tools
Contributors who help improve this project
📈 Changelog
See CHANGELOG.md for a detailed list of changes and version history.

Made with ❤️ for the Ukrainian community

This tool helps Ukrainian citizens stay informed about power outages and plan their daily activities accordingly. 