"""Tests for ICS generation."""
import pytest
import tempfile
import logging
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
            date="15.01.2024",
            name="Група 1.1",
            status="Можливе відключення",
            period_from="09:00",
            period_to="12:00",
            last_update="2024-01-15T10:00:00",
            calendar_event_id="15.01.2024_Група 1.1-Можливе відключення-09:00-12:00",
            calendar_event_uid="test-uid-123@power-monitor"
        )

    @pytest.fixture
    def sample_event_dict(self):
        """Create a sample event dictionary for testing."""
        return {
            'date': '15.01.2024',
            'name': 'Група 1.1',
            'status': 'Можливе відключення',
            'period_from': '09:00',
            'period_to': '12:00',
            'last_update': '2024-01-15T10:00:00',
            'calendar_event_id': '15.01.2024_Група 1.1-Можливе відключення-09:00-12:00',
            'calendar_event_uid': 'test-uid-123@power-monitor'
        }

    @pytest.fixture
    def ics_generator(self, temp_output_dir):
        """Create an ICS generator instance."""
        logger = logging.getLogger('test_ics')
        logger.setLevel(logging.DEBUG)
        
        return ICSEventGenerator(
            output_dir=temp_output_dir,
            timezone='Europe/Kiev',
            calendar_name='Power Outage Monitor',
            logger=logger


            
        )

    def test_ics_generator_initialization(self, ics_generator, temp_output_dir):
        """Test ICS generator initialization."""
        assert ics_generator.output_dir == temp_output_dir
        assert ics_generator.timezone == 'Europe/Kiev'
        assert ics_generator.calendar_name == 'Power Outage Monitor'
        assert temp_output_dir.exists()

    def test_create_ics_content_timed_event(self, ics_generator, sample_event_dict):
        """Test creating ICS content for timed event."""
        content = ics_generator.create_ics_content(sample_event_dict)
        
        assert "BEGIN:VCALENDAR" in content
        assert "END:VCALENDAR" in content
        assert "BEGIN:VEVENT" in content
        assert "END:VEVENT" in content
        assert "UID:test-uid-123@power-monitor" in content
        assert "SUMMARY:" in content
        assert "DTSTART:" in content
        assert "DTEND:" in content
        assert "Група 1.1" in content

    def test_create_ics_content_all_day_event(self, ics_generator):
        """Test creating ICS content for all-day event."""
        all_day_event = {
            'date': '15.01.2024',
            'name': 'Група 1.1',
            'status': 'Можливе відключення',
            'period_from': None
,
            'period_to': None,
            'last_update': '2024-01-15T10:00:00',
            'calendar_event_id': '15.01.2024_Група 1.1-Можливе відключення',
            'calendar_event_uid': 'test-uid-allday@power-monitor'
        }
        
        content = ics_generator.create_ics_content(all_day_event)
        
        assert "DTSTART;VALUE=DATE:" in content
        assert "DTEND;VALUE=DATE:" in content
        assert "BEGIN:VCALENDAR" in content
        assert "END:VCALENDAR" in content

    def test_create_single_ics_file(self, ics_generator, sample_event_dict, temp_output_dir):
        """Test creating individual ICS file."""
        filepath = ics_generator.create_single_ics_file(sample_event_dict)
        
        assert filepath is not None
        assert filepath.exists()
        assert filepath.suffix == '.ics'
        
        # Check file content
        content = filepath.read_text(encoding='utf-8')
        assert "BEGIN:VCALENDAR" in content
        assert "Група 1.1" in content
        assert "test-uid-123@power-monitor" in content

    def test_create_combined_ics_file(self, ics_generator, sample_event_dict, temp_output_dir):
        """Test creating combined ICS file."""
        events = [sample_event_dict]
        
        filepath = ics_generator.create_combined_ics_file(events)
        
        assert filepath is not None
        assert filepath.exists()
        assert filepath.suffix == '.ics'
        
        # Check file content
        content = filepath.read_text(encoding='utf-8')
        assert "BEGIN:VCALENDAR" in content
        assert "END:VCALENDAR" in content
        assert "Група 1.1" in content
        assert content.count("BEGIN:VEVENT") == 1
        assert content.count("END:VEVENT") == 1

    def test_create_combined_ics_file_multiple_events(self, ics_generator, temp_output_dir):
        """Test creating combined ICS file with multiple events."""
        events = [
            {
                'date': '15.01.2024',
                'name': 'Група 1.1',
                'status': 'Можливе відключення',
                'period_from': '09:00',
                'period_to': '12:00',
                'last_update': '2024-01-15T10:00:00',
                'calendar_event_id': '15.01.2024_Група 1.1-Можливе відключення-09:00-12:00',
                'calendar_event_uid': 'test-uid-1@power-monitor'
            },
            {
                'date': '16.01.2024',
                'name': 'Група 2.1',
                'status': 'Електроенергії немає',
                'period_from': '14:00',
                'period_to': '18:00',
                'last_update': '2024-01-16T10:00:00',
                'calendar_event_id': '16.01.2024_Група 2.1-Електроенергії немає-14:00-18:00',
                'calendar_event_uid': 'test-uid-2@power-monitor'
            }
        ]
        
        filepath = ics_generator.create_combined_ics_file(events)
        
        assert filepath is not None
        assert filepath.exists()
        
        content = filepath.read_text(encoding='utf-8')
        assert content.count("BEGIN:VEVENT") == 2
        assert content.count("END:VEVENT") == 2
        assert "Група 1.1" in content
        assert "Група 2.1" in content

    def test_create_cancellation_ics_file(self, ics_generator, temp_output_dir):
        """Test creating cancellation ICS file."""
        events_to_cancel = [
            {
                'calendar_event_id': '15.01.2024_Група 1.1-Можливе відключення-09:00-12:00',
                'calendar_event_uid': 'test-uid-1@power-monitor'
            },
            {
                'calendar_event_id': '16.01.2024_Група 2.1-Електроенергії немає-14:00-18:00',
                'calendar_event_uid': 'test-uid-2@power-monitor'
            }
        ]
        
        filepath = ics_generator.create_cancellation_ics_file(events_to_cancel)
        
        assert filepath is not None
        assert filepath.exists()
        assert "cancel_events" in filepath.name
        
        content = filepath.read_text(encoding='utf-8')
        assert "METHOD:CANCEL" in content
        assert "STATUS:CANCELLED" in content
        assert content.count("BEGIN:VEVENT") == 2

    def test_create_cancellation_ics_file_empty_list(self, ics_generator):
        """Test creating cancellation ICS file with empty list."""
        filepath = ics_generator.create_cancellation_ics_file([])
        assert filepath is None

    def test_generate_deletion_summary(self, ics_generator, temp_output_dir):
        """Test generating deletion summary file."""
        events_to_delete = [
            '15.01.2024_Група 1.1-Можливе відключення-09:00-12:00',
            '16.01.2024_Група 2.1-Електроенергії немає-14:00-18:00'
        ]
        
        ics_generator.generate_deletion_summary(events_to_delete)
        
        # Find the generated file
        txt_files = list(temp_output_dir.glob("*manual_delete.txt"))
        assert len(txt_files) == 1
        
        content = txt_files[1].read_text(encoding='utf-8')
        assert "GOOGLE CALENDAR - MANUAL DELETION" in content
        assert "Total events to delete: 2" in content
        assert "Група 1.1" in content
        assert "Група 2.1" in content

    def test_generate_ics_files(self, ics_generator, sample_event_dict, temp_output_dir):
        """Test generating all ICS files."""
        events = [sample_event_dict]
        
        ics_generator.generate_ics_files(events)
        
        # Check that files were created
        ics_files = list(temp_output_dir.glob("*.ics"))
        assert len(ics_files) >= 2  # At least individual + combined
        
        # Check for combined file
        combined_files = [f for f in ics_files if "all_power_events" in f.name]
        assert len(combined_files) == 1

    def test_generate_ics_files_empty_list(self, ics_generator, temp_output_dir):
        """Test generating ICS files with empty event list."""
        ics_generator.generate_ics_files([])
        
        # Should not create any files
        ics_files = list(temp_output_dir.glob("*.ics"))
        assert len(ics_files) == 0

    def test_parse_ukraine_datetime(self, ics_generator):
        """Test parsing Ukraine datetime."""
        dt = ics_generator.parse_ukraine_datetime("15.01.2024", "09:30")
        
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15
        assert dt.hour == 9
        assert dt.minute == 30
        assert dt.tzinfo is not None

    def test_parse_date_to_datetime(self, ics_generator):
        """Test parsing date to datetime."""
        dt = ics_generator.parse_date_to_datetime("15.01.2024")
        
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

    def test_escape_text(self, ics_generator):
        """Test text escaping for ICS format."""
        text = "Test, text; with\nspecial chars"
        escaped = ics_generator.escape_text(text)
        
        assert "\\," in escaped
        assert "\\;" in escaped
        assert "\\n" in escaped

    def test_format_datetime_for_ics(self, ics_generator):
        """Test datetime formatting for ICS."""
        dt = datetime(2024, 1, 15, 9, 30, 0)
        formatted = ics_generator.format_datetime_for_ics(dt)
        
        assert formatted.endswith("Z")
        assert "20240115" in formatted
        assert "093000" in formatted

    def test_overnight_period_handling(self, ics_generator):
        """Test handling of overnight periods."""
        overnight_event = {
            'date': '15.01.2024',
            'name': 'Група 1.1',
            'status': 'Можливе відключення',
            'period_from': '23:00',
            'period_to': '06:00',  # Next day
            'last_update': '2024-01-15T10:00:00',
            'calendar_event_id': '15.01.2024_Група 1.1-Можливе відключення-23:00-06:00',
            'calendar_event_uid': 'test-uid-overnight@power-monitor'
        }
        
        content = ics_generator.create_ics_content(overnight_event)
        
        assert "BEGIN:VCALENDAR" in content
        assert "DTSTART:" in content
        assert "DTEND:" in content
        # The end time should be on the next day
        lines = content.split('\r\n')
        dtstart_line = next(line for line in lines if line.startswith('DTSTART:'))
        dtend_line = next(line for line in lines if line.startswith('DTEND:'))
        
        # Extract dates from the datetime strings
        start_date = dtstart_line.split(':')[1][:8]  # YYYYMMDD
        end_date = dtend_line.split(':')[1][:8]      # YYYYMMDD
        
        # End date should be one day after start date for overnight period
        assert int(end_date) > int(start_date)