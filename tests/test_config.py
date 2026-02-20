"""Tests for configuration management."""

import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from power_outage_monitor.config import Config, parse_arguments


class TestConfig:
    """Test cases for Config class."""

    def test_config_initialization(self):
        """Test Config initialization with default values."""
        config = Config()
        assert config.base_url == "https://poweron.loe.lviv.ua/"
        assert config.json_data_dir == Path("json_data")
        assert config.ics_output_dir == Path("calendar_events")
        assert config.selenium_timeout == 30
        assert config.headless is True
        assert config.check_interval == 300
        assert config.continuous_mode is False
        assert config.group_filter is None
        assert config.groups_file == "groups.json"
        assert config.log_level == "INFO"
        assert config.log_file == Path("power_monitor.log")
        assert config.ics_timezone == "Europe/Kiev"
        assert config.calendar_name == "Power Outages"
        assert config.cleanup_days == 30

    def test_config_with_custom_values(self):
        """Test Config initialization with custom values."""
        config = Config(
            base_url="https://custom.url/",
            json_data_dir=Path("/custom/json"),
            ics_output_dir=Path("/custom/ics"),
            selenium_timeout=60,
            continuous_mode=True,
            check_interval=1800,
        )
        assert config.base_url == "https://custom.url/"
        assert config.json_data_dir == Path("/custom/json")
        assert config.ics_output_dir == Path("/custom/ics")
        assert config.continuous_mode is True
        assert config.check_interval == 1800

    def test_parse_arguments_default(self):
        """Test argument parsing with default values."""
        with patch("sys.argv", ["main.py"]):
            config = parse_arguments()
            assert config.continuous_mode is False
            assert config.check_interval == 300
            assert config.group_filter is None
            assert config.selenium_timeout == 30

    def test_parse_arguments_with_groups(self):
        """Test argument parsing with group filtering."""
        with patch("sys.argv", ["main.py", "--groups", "1.1,2.1,3.2"]):
            config = parse_arguments()
            assert config.group_filter == ["1.1", "2.1", "3.2"]

    def test_parse_arguments_continuous(self):
        """Test argument parsing with continuous monitoring."""
        with patch("sys.argv", ["main.py", "--continuous", "--interval", "1800"]):
            config = parse_arguments()
            assert config.continuous_mode is True
            assert config.check_interval == 1800

    def test_groups_file_loading(self):
        """Test loading groups from JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"group": ["1.1", "2.1"]}, f)
            groups_file = f.name

        try:
            with patch("sys.argv", ["main.py", "--groups-file", groups_file]):
                config = parse_arguments()
                assert config.group_filter == ["1.1", "2.1"]
        finally:
            Path(groups_file).unlink()
