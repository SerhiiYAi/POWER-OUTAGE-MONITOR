"""Tests for configuration management."""
import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from power_outage_monitor.config import Config, parse_arguments


class TestConfig:
    """Test cases for Config class."""

    def test_config_initialization(self):
        """Test Config initialization with default values."""
        config = Config()
        assert config.url == "https://poweron.loe.lviv.ua/"
        assert config.output_dir == Path("output")
        assert config.db_path == Path("power_outages.db")
        assert config.continuous is False
        assert config.interval == 3600

    def test_config_with_custom_values(self):
        """Test Config initialization with custom values."""
        config = Config(
            url="https://custom.url/",
            output_dir=Path("/custom/path"),
            continuous=True,
            interval=1800
        )
        assert config.url == "https://custom.url/"
        assert config.output_dir == Path("/custom/path")
        assert config.continuous is True
        assert config.interval == 1800

    def test_parse_arguments_default(self):
        """Test argument parsing with default values."""
        with patch('sys.argv', ['main.py']):
            config = parse_arguments()
            assert config.continuous is False
            assert config.interval == 3600
            assert config.groups is None

    def test_parse_arguments_with_groups(self):
        """Test argument parsing with group filtering."""
        with patch('sys.argv', ['main.py', '--groups', '1.1,2.1,3.2']):
            config = parse_arguments()
            assert config.groups == ['1.1', '2.1', '3.2']

    def test_parse_arguments_continuous(self):
        """Test argument parsing with continuous monitoring."""
        with patch('sys.argv', ['main.py', '--continuous', '--interval', '1800']):
            config = parse_arguments()
            assert config.continuous is True
            assert config.interval == 1800

    def test_groups_file_loading(self):
        """Test loading groups from JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"group": ["1.1", "2.1"]}, f)
            groups_file = f.name

        try:
            with patch('sys.argv', ['main.py', '--groups-file', groups_file]):
                config = parse_arguments()
                assert config.groups == ["1.1", "2.1"]
        finally:
            Path(groups_file).unlink()