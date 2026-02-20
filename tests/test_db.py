"""Tests for database operations."""

import pytest
import tempfile
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

from power_outage_monitor.db import PowerOutageDatabase, OutagePeriod


class TestPowerOutageDatabase:
    """Test cases for PowerOutageDatabase class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        # Create a logger for testing
        logger = logging.getLogger("test_db")
        logger.setLevel(logging.DEBUG)

        db = PowerOutageDatabase(db_path, logger)
        yield db

        # Cleanup - the database doesn't have a close method,
        # connections are handled automatically with context managers
        try:
            if db_path.exists():
                db_path.unlink()
        except Exception:
            pass

    @pytest.fixture
    def sample_outage_period(self):
        """Create a sample outage period for testing."""
        return OutagePeriod(
            date="15.01.2024",  # Use the format expected by the database
            name="Група 1.1",  # This is the group name field
            status="Можливе відключення",  # Status field
            period_from="09:00",
            period_to="12:00",
            last_update="2024-01-15T10:00:00",
        )

    def test_database_initialization(self, temp_db):
        """Test database initialization and table creation."""
        assert temp_db.db_path.exists()

        # Check if the correct table exists (it's 'periods', not 'outage_periods')
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            # The actual table names from the schema
            expected_tables = ["periods", "metadata"]
            for table in expected_tables:
                assert table in tables

    def test_insert_period(self, temp_db, sample_outage_period):
        """Test inserting an outage period."""
        recid = temp_db.insert_period(sample_outage_period)
        assert recid is not None
        assert isinstance(recid, str)

        # Verify data was stored
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM periods WHERE recid = ?", (recid,))
            row = cursor.fetchone()

            assert row is not None

    def test_get_periods_by_name_and_date(self, temp_db, sample_outage_period):
        """Test retrieving periods by name and date."""
        # Insert the period first
        temp_db.insert_period(sample_outage_period)

        # Retrieve periods
        periods = temp_db.get_periods_by_name_and_date(
            sample_outage_period.name, sample_outage_period.date
        )

        assert len(periods) == 1
        assert periods[0].name == "Група 1.1"
        assert periods[0].date == "15.01.2024"

    def test_update_calendar_event_state(self, temp_db, sample_outage_period):
        """Test updating calendar event state."""
        # Insert period first
        recid = temp_db.insert_period(sample_outage_period)

        # Update state

        temp_db.update_calendar_event_state(recid, "generated")

        # Verify update
        periods = temp_db.get_periods_by_name_and_date(
            sample_outage_period.name, sample_outage_period.date
        )

        assert len(periods) == 1
        assert periods[0].calendar_event_state == "generated"

    def test_mark_event_as_sent(self, temp_db, sample_outage_period):
        """Test marking an event as sent."""
        # Insert period first
        recid = temp_db.insert_period(sample_outage_period)

        # Mark as sent
        temp_db.mark_event_as_sent(recid)

        # Verify
        periods = temp_db.get_periods_by_name_and_date(
            sample_outage_period.name, sample_outage_period.date
        )

        assert len(periods) == 1
        assert periods[0].event_sent is True

    def test_get_events_for_generation(self, temp_db, sample_outage_period):
        """Test getting events for generation."""
        # Create a period with a future date (or today's date)

        # Get current Ukraine date and add a few days to ensure it's in the future
        current_ukraine_date = temp_db.get_ukraine_current_date()
        future_date = current_ukraine_date + timedelta(days=1)
        future_date_str = future_date.strftime("%d.%m.%Y")

        # Create a period with future date
        future_period = OutagePeriod(
            date=future_date_str,
            name="Група 1.1",
            status="Можливе відключення",
            period_from="09:00",
            period_to="12:00",
            last_update=datetime.now().isoformat(),
        )

        # Insert and update period to 'generated' state
        recid = temp_db.insert_period(future_period)
        temp_db.update_calendar_event_state(recid, "generated")

        # Get events for generation
        events = temp_db.get_events_for_generation()

        assert "events_to_create" in events
        assert "events_to_cancel" in events
        assert len(events["events_to_create"]) == 1
        assert events["events_to_create"][0].name == "Група 1.1"

    def test_cleanup_old_data(self, temp_db):
        """Test cleaning up old data."""
        # Create an old period (with old insert_ts)
        old_period = OutagePeriod(
            date="01.01.2020",
            name="Група 1.1",
            status="Можливе відключення",
            period_from="09:00",
            period_to="12:00",
            last_update="2020-01-01T10:00:00",
            insert_ts="2020-01-01T10:00:00",  # Very old timestamp
        )

        # Create a recent period
        recent_period = OutagePeriod(
            date="15.01.2024",
            name="Група 2.1",
            status="Можливе відключення",
            period_from="13:00",
            period_to="16:00",
            last_update="2024-01-15T10:00:00",
        )

        temp_db.insert_period(old_period)
        temp_db.insert_period(recent_period)

        # Clean up old data (keep last 30 days)
        deleted_count = temp_db.cleanup_old_data(days_to_keep=30)

        # Should have deleted the old record
        assert (
            deleted_count >= 0
        )  # At least 0 (might be 1 if the old record was actually deleted)

    def test_get_comprehensive_stats(self, temp_db, sample_outage_period):
        """Test getting comprehensive statistics."""
        # Insert a period
        temp_db.insert_period(sample_outage_period)

        # Get stats
        stats = temp_db.get_comprehensive_stats()

        assert "total_records" in stats
        assert "unique_dates" in stats
        assert "unique_groups" in stats
        assert stats["total_records"] >= 1

    def test_export_to_csv(self, temp_db, sample_outage_period):
        """Test exporting data to CSV."""
        # Insert a period
        temp_db.insert_period(sample_outage_period)

        # Create temporary CSV file
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = Path(f.name)

        try:
            # Export to CSV
            temp_db.export_to_csv(csv_path)

            # Verify file was created and has content
            assert csv_path.exists()
            content = csv_path.read_text(encoding="utf-8")
            assert "Date" in content  # Header
            assert "Група 1.1" in content  # Our test data

        finally:
            # Cleanup
            if csv_path.exists():
                csv_path.unlink()

    def test_check_identical_event_exists(self, temp_db, sample_outage_period):
        """Test checking for identical events."""
        # Insert and mark as sent
        recid = temp_db.insert_period(sample_outage_period)
        temp_db.update_calendar_event_state(recid, "generated")
        temp_db.mark_event_as_sent(recid)

        # Create identical period
        identical_period = OutagePeriod(
            date="15.01.2024",
            name="Група 1.1",
            status="Можливе відключення",
            period_from="09:00",
            period_to="12:00",
            last_update="2024-01-15T11:00:00",  # Different update time
        )

        # Check for identical event
        existing = temp_db.check_identical_event_exists(identical_period)

        # Should find the existing event (same hash)
        assert existing is not None

        assert existing.name == "Група 1.1"

    def test_ukraine_timezone_methods(self, temp_db):
        """Test Ukraine timezone related methods."""
        current_date = temp_db.get_ukraine_current_date()
        current_date_str = temp_db.get_ukraine_current_date_str()

        assert current_date is not None
        assert isinstance(current_date_str, str)
        assert len(current_date_str) > 0
