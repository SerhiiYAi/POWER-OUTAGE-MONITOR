"""Configuration management for Power Outage Monitor."""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
import logging


# Fix Windows console for Ukrainian text
if sys.platform.startswith('win'):
    try:
        os.system('chcp 65001 >nul 2>&1')
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass


@dataclass
class Config:
    """Configuration settings for the power outage monitor."""
    
    # Paths
    db_path: Path = Path("power_outages.db")
    json_data_dir: Path = Path("json_data")
    ics_output_dir: Path = Path("calendar_events")
    
    # Web scraping
    base_url: str = "https://poweron.loe.lviv.ua/"
    selenium_timeout: int = 30
    headless: bool = True
    
    # Monitoring
    check_interval: int = 300  # seconds
    continuous_mode: bool = False
    
    # Filtering
    group_filter: Optional[List[str]] = None
    groups_file: str = "groups.json"
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[Path] = Path("power_monitor.log")
    
    # ICS settings
    ics_timezone: str = "Europe/Kiev"
    calendar_name: str = "Power Outages"
    
    # Data cleanup
    cleanup_days: int = 30


def parse_group_input(console_input: Optional[str], json_file: str) -> Optional[List[str]]:
    """Parse group input with priority: console input > json file > None"""
    group_codes = None
    
    if console_input:
        group_codes = [g.strip() for g in console_input.split(',') if g.strip()]
    elif json_file and os.path.exists(json_file):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and "group" in data and isinstance(data["group"], list):
                    group_codes = [str(g).strip() for g in data["group"] if str(g).strip()]
        except Exception as e:
            print(f"[ERROR] Could not read group codes from {json_file}: {e}")
    
    return group_codes


def parse_arguments() -> Config:
    """Parse command line arguments and return configuration."""
    parser = argparse.ArgumentParser(description="Power Outage Monitor with group filtering")
    
    parser.add_argument("--db-path", type=Path, default="power_outages.db",
                       help="Path to SQLite database")
    parser.add_argument("--json-dir", type=Path, default="json_data",
                       help="Directory for JSON data storage")
    parser.add_argument("--ics-dir", type=Path, default="calendar_events",
                       help="Directory for ICS file output")
    parser.add_argument("--interval", type=int, default=300,
                       help="Check interval in seconds")
    parser.add_argument("--continuous", action="store_true",
                       help="Run in continuous monitoring mode")
    parser.add_argument("--groups", type=str,
                       help="Comma-separated list of group codes (e.g. 1.1,2.1,3.2)")
    parser.add_argument("--groups-file", type=str, default="groups.json",
                       help="JSON file with group codes")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       default="INFO", help="Logging level")
    parser.add_argument("--log-file", type=Path, default="power_monitor.log",
                       help="Log file path")
    parser.add_argument("--headless", action="store_true", default=True,
                       help="Run browser in headless mode")
    parser.add_argument("--cleanup-days", type=int, default=30,
                       help="Days to keep in database cleanup")
    
    args = parser.parse_args()
    
    # Parse group filter
    group_filter = parse_group_input(args.groups, args.groups_file)
    
    return Config(
        db_path=args.db_path,
        json_data_dir=args.json_dir,
        ics_output_dir=args.ics_dir,
        check_interval=args.interval,
        continuous_mode=args.continuous,
        group_filter=group_filter,
        groups_file=args.groups_file,
        log_level=args.log_level,
        log_file=args.log_file,
        headless=args.headless,
        cleanup_days=args.cleanup_days
    )


def setup_logging(config: Config) -> logging.Logger:
    """Setup logging configuration with enhanced file information only in DEBUG mode."""
    import sys
    import logging

    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, config.log_level))
    logger.handlers.clear()

    # Define formatters
    debug_formatter = logging.Formatter(
        '%(asctime)s - %(filename)s:%(lineno)d - %(funcName)s() - %(levelname)s - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    # Choose formatter based on log level
    formatter = debug_formatter if config.log_level.upper() == "DEBUG" else simple_formatter

    # File handler
    if config.log_file:
        file_handler = logging.FileHandler(config.log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Console handler with error handling for encoding issues
    try:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    except Exception:
        print("Console logging disabled due to encoding issues. Check power_monitor.log for details.")

    return logger