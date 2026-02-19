"""Tests for utility functions."""
import pytest
import logging
from datetime import datetime
from unittest.mock import patch, MagicMock

from power_outage_monitor.utils import GroupFilter, SmartPeriodComparator
from power_outage_monitor.db import OutagePeriod


class TestGroupFilter:
    """Test cases for GroupFilter class."""

    def test_group_filter_initialization_with_list(self):
        """Test GroupFilter initialization with list."""
        filter_obj = GroupFilter(["1.1", "2.1"])
        assert filter_obj.groups == ["1.1", "2.1"]

    def test_group_filter_initialization_with_none(self):
        """Test GroupFilter initialization with None."""
        filter_obj = GroupFilter(None)
        assert filter_obj.groups is None

    def test_should_include_with_filter(self):
        """Test should_include method with active filter."""
        filter_obj = GroupFilter(["1.1", "2.1"])
        
        assert filter_obj.should_include("1.1") is True
        assert filter_obj.should_include("2.1") is True
        assert filter_obj.should_include("3.1") is False

    def test_should_include_without_filter(self):
        """Test should_include method without filter."""
        filter_obj = GroupFilter(None)
        
        assert filter_obj.should_include("1.1") is True
        assert filter_obj.should_include("2.1") is True
        assert filter_obj.should_include("3.1") is True

    def test_filter_periods(self):
        """Test filtering periods."""
        periods = [
            OutagePeriod("1.1", "2024-01-15", "09:00", "12:00", False, "Test 1"),
            OutagePeriod("2.1", "2024-01-15", "13:00", "16:00", False, "Test 2"),
            OutagePeriod("3.1", "2024-01-15", "17:00", "20:00", False, "Test 3"),
        ]
        
        filter_obj = GroupFilter(["1.1", "2.1"])
        filtered = filter_obj.filter_periods(periods)
        
        assert len(filtered) == 2
        assert filtered[0].group_code == "1.1"
        assert filtered[1].group_code == "2.1"


class TestSmartPeriodComparator:
    """Test cases for SmartPeriodComparator class."""

    def test_periods_equal(self):
        """Test comparing equal periods."""
        period1 = OutagePeriod("1.1", "2024-01-15", "09:00", "12:00", False, "Test")
        period2 = OutagePeriod("1.1", "2024-01-15", "09:00", "12:00", False, "Test")
        
        comparator = SmartPeriodComparator()
        assert comparator.are_periods_equal(period1, period2) is True

    def test_periods_different(self):
        """Test comparing different periods."""
        period1 = OutagePeriod("1.1", "2024-01-15", "09:00", "12:00", False, "Test")
        period2 = OutagePeriod("1.1", "2024-01-15", "13:00", "16:00", False, "Test")
        
        comparator = SmartPeriodComparator()
        assert comparator.are_periods_equal(period1, period2) is False

    def test_find_changes(self):
        """Test finding changes between period lists."""
        old_periods = [
            OutagePeriod("1.1", "2024-01-15", "09:00", "12:00", False, "Old"),
        ]
        
        new_periods = [
            OutagePeriod("1.1", "2024-01-15", "09:00", "12:00", False, "Old"),
            OutagePeriod("2.1", "2024-01-15", "13:00", "16:00", False, "New"),
        ]
        
        comparator = SmartPeriodComparator()
        added, removed, modified = comparator.find_changes(old_periods, new_periods)
        
        assert len(added) == 1
        assert len(removed) == 0
        assert len(modified) == 0
        assert added[0].group_code == "2.1"