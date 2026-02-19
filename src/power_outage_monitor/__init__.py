"""Power Outage Monitor - Automated monitoring and calendar integration system."""

from pathlib import Path
# Version information
try:
    from ._version import version as __version__
except ImportError:
    __version__ = "0.1.0.dev0"

# Package metadata
__title__ = "power-outage-monitor"
__description__ = "Automated monitoring and calendar integration system for power outage schedules"
__author__ = "Your Name"
__author_email__ = "sergai84g@gmail.com"
__license__ = "MIT"
__url__ = "https://github.com/SerhiiYAi/power-outage-monitor"

# Public API
from .config import Config
from .db import PowerOutageDatabase, OutagePeriod
from .monitor import PowerOutageMonitor
from .scraper import PowerOutageScraper
from .icsgen import ICSEventGenerator
from .utils import GroupFilter, SmartPeriodComparator

# Package constants
DEFAULT_URL = "https://poweron.loe.lviv.ua/"
DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_DB_NAME = "power_outages.db"
DEFAULT_INTERVAL = 3600  # 1 hour in seconds

# Supported group codes (can be extended)
SUPPORTED_GROUPS = [
    "1.1", "1.2", "1.3", "1.4", "1.5", "1.6",
    "2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
    "3.1", "3.2", "3.3", "3.4", "3.5", "3.6",
    "4.1", "4.2", "4.3", "4.4", "4.5", "4.6",
    "5.1", "5.2", "5.3", "5.4", "5.5", "5.6",
    "6.1", "6.2", "6.3", "6.4", "6.5", "6.6",
]


# Export all public components
__all__ = [
    # Version and metadata
    "__version__",
    "__title__",
    "__description__",
    "__author__",
    "__author_email__",
    "__license__",
    "__url__",
    
    # Main classes
    "Config",
    "PowerOutageDatabase",
    "OutagePeriod", 
    "PowerOutageMonitor",
    "PowerOutageScraper",
    "ICSEventGenerator",
    "GroupFilter",
    "SmartPeriodComparator",
    
    # Constants
    "DEFAULT_URL",
    "DEFAULT_OUTPUT_DIR", 
    "DEFAULT_DB_NAME",
    "DEFAULT_INTERVAL",
    "SUPPORTED_GROUPS",
]


def create_default_config(**kwargs):
    """
    Create a default configuration object.
    
    Args:
        **kwargs: Override default configuration values
        
    Returns:
        Config: Configured Config object
    """
    defaults = {
        'url': DEFAULT_URL,
        'output_dir': DEFAULT_OUTPUT_DIR,
        'db_path': DEFAULT_OUTPUT_DIR / DEFAULT_DB_NAME,
        'continuous': False,
        'interval': DEFAULT_INTERVAL,
        'groups': None,
        'debug': False,
    }
    defaults.update(kwargs)
    return Config(**defaults)


def setup_logging(level=logging.INFO, format_string=None):
    """
    Setup logging for the package.
    
    Args:
        level: Logging level (default: INFO)
        format_string: Custom format string for log messages
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    
    # Set package logger level
    logger.setLevel(level)
