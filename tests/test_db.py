"""Tests for database operations."""
import pytest
import tempfile
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from power_outage_monitor.db import PowerOutageDatabase, OutagePeriod


class TestPowerOutageDatabase:
    """Test cases for PowerOutageDatabase class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        db = PowerOutageDatabase(db_path)
        yield db
        
        # Cleanup
        db.close()
        if db_path.exists():
            db_path.unlink()

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

    def test_database_initialization(self, temp_db):
        """Test database initialization and table creation."""
        assert temp_db.db_path.exists()
        
        # Check if tables exist
        cursor = temp_db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = ['outage_periods', 'events', 'event_tracking']
        for table in expected_tables:
            assert table in tables

    def test_store_outage_period(self, temp_db, sample_outage_period):
        """Test storing an outage period."""
        result = temp_db.store_outage_period(sample_outage_period)
        assert result is True
        
        # Verify data was stored
        cursor = temp_db.conn.cursor()
        cursor.execute("SELECT * FROM outage_periods WHERE group_code = ?", ("1.1",))
        row = cursor.fetchone()
        
        assert row is not None
        assert row[1] == "1.1"  
# group_code
        assert row[2] == "2024-01-15"  # date

    def test_get_outage_periods(self, temp_db, sample_outage_period):
        """Test retrieving outage periods."""
        temp_db.store_outage_period(sample_outage_period)
        
        periods = temp_db.get_outage_periods()
        assert len(periods) == 1
        assert periods[0].group_code == "1.1"

    def test_get_outage_periods_with_filter(self, temp_db, sample_outage_period):
        """Test retrieving outage periods with group filter."""
        temp_db.store_outage_period(sample_outage_period)
        
        # Test with matching filter
        periods = temp_db.get_outage_periods(group_filter=["1.1"])
        assert len(periods) == 1
        
        # Test with non-matching filter
        periods = temp_db.get_outage_periods(group_filter=["2.1"])
        assert len(periods) == 0

    def test_clear_old_periods(self, temp_db):
        """Test clearing old outage periods."""
        # Create old and new periods
        old_period = OutagePeriod(
            group_code="1.1",
            date="2020-01-01",
            start_time="09:00",
            end_time="12:00",
            is_all_day=False,
            raw_text="Old period"
        )
        
        new_period = OutagePeriod(
            group_code="1.1",
            date="2024-01-15",
            start_time="09:00",
            end_time="12:00",
            is_all_day=False,
            raw_text="New period"
        )
        
        temp_db.store_outage_period(old_period)
        temp_db.store_outage_period(new_period)
        
        # Clear old periods (older than 30 days)
        temp_db.clear_old_periods(days=30)
        
        periods = temp_db.get_outage_periods()
        assert len(periods) == 1
        assert periods[0].raw_text == "New period"