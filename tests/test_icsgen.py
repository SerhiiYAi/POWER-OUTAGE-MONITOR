"""Tests for ICS generation."""
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from power_outage_monitor.icsgen import ICSEventGenerator
from power_outage_monitor.db import OutagePeriod


class TestICSEventGenerator:
    """Test cases for ICS event generation."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_outage_period(self):
        """Create a sample outage period for testing."""
        return OutagePeriod(
            group_code="1.1",
            date="2024-01-15",
            start_time="09:00",
            end_time="12:00",
            is_all_day=False,
            raw_text="Група 1.1: 15.01.2024 з 09:00 до 12:00"
        )

    @pytest.fixture
    def ics_generator(self, temp_output_dir):
        """Create an ICS generator instance."""
        return ICSEventGenerator(temp_output_dir)

    def test_ics_generator_initialization(self, ics_generator, temp_output_dir):
        """Test ICS generator initialization."""
        assert ics_generator.output_dir == temp_output_dir
        assert temp_output_dir.exists()

    def test_generate_ics_content_timed_event(self, ics_generator, sample_outage_period):
        """Test generating ICS content for timed event."""
        content = ics_generator._generate_ics_content(
            sample_outage_period,
            "test-uid",
            datetime.now()
        )
        
        assert "BEGIN:VCALENDAR" in content
        assert "END:VCALENDAR" in content
        assert "BEGIN:VEVENT" in content
        assert "END:VEVENT" in content
        assert "UID:test-uid" in content
        assert "SUMMARY:" in content
        assert "DTSTART:" in content
        assert "DTEND:" in content

    def test_generate_ics_content_all_day_event(self, ics_generator):
        """Test generating ICS content for all-day event."""
        all_day_period = OutagePeriod(
            group_code="1.1",
            date="2024-01-15",
            start_time=None,
            end_time=None,
            is_all_day=True,
            raw_text="Група 1.1: 15.01.2024 весь день"
        )
        
        content = ics_generator._generate_ics_content(
            all_day_period,
            "test-uid",
            datetime.now()
        )
        
        assert "DTSTART;VALUE=DATE:" in content
        assert "DTEND;VALUE=DATE:" in content

    def test_create_individual_ics_files(self, ics_generator, sample_outage_period, temp_output_dir):
        """Test creating individual ICS files."""
        periods = [sample_outage_period]
        
        result = ics_generator.create_individual_ics_files(periods)
        assert result is True
        
        # Check if file was created
        expected_file = temp_output_dir / "group_1.1.ics"
        assert expected_file.exists()
        
        # Check file content
        content = expected_file.read_text(encoding='utf-8')
        assert "BEGIN:VCALENDAR" in content
        assert "Група 1.1"
 in content

    def test_create_combined_ics_file(self, ics_generator, sample_outage_period, temp_output_dir):
        """Test creating combined ICS file."""
        periods = [sample_outage_period]
        
        result = ics_generator.create_combined_ics_file(periods)
        assert result is True
        
        # Check if file was created
        expected_file = temp_output_dir / "all_groups_combined.ics"
        assert expected_file.exists()
        
        # Check file content
        content = expected_file.read_text(encoding='utf-8')
        assert "BEGIN:VCALENDAR" in content
        assert "Група 1.1" in content