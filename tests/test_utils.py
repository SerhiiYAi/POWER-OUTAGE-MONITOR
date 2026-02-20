"""Tests for utility functions."""
import pytest
import logging
from unittest.mock import MagicMock

from power_outage_monitor.utils import (
    normalize_time, time_to_minutes, minutes_to_time, periods_intersect,
    extract_group_code, GroupFilter, SmartPeriodComparator, PeriodComparator
)
from datetime import datetime, timedelta

# --- Utility Function Tests ---


@pytest.mark.parametrize("input_str,expected", [
    ("09:30", "09:30"),
    ("9:5", "09:05"),
    ("24:00", "23:59"),
    ("  09:30  ", "09:30"),
    ("09.30", "09:30"),
    ("09:30", "09:30"),
    ("invalid", "invalid"),
    ("", ""),
])
def test_normalize_time(input_str, expected):
    assert normalize_time(input_str) == expected


@pytest.mark.parametrize("input_str,expected", [
    ("00:00", 0),
    ("01:00", 60),
    ("12:30", 750),
    ("23:59", 1439),
    ("", 0),
    (None, 0),
    ("invalid", 0),
])
def test_time_to_minutes(input_str, expected):
    assert time_to_minutes(input_str) == expected


@pytest.mark.parametrize("minutes,expected", [
    (0, "00:00"),
    (60, "01:00"),
    (750, "12:30"),
    (1439, "23:59"),
])
def test_minutes_to_time(minutes, expected):
    assert minutes_to_time(minutes) == expected


def make_period(period_from, period_to):
    p = MagicMock()
    p.period_from = period_from
    p.period_to = period_to
    return p


@pytest.mark.parametrize("p1,p2,expected", [
    (make_period("09:00", "12:00"), make_period("11:00", "14:00"), True),
    (make_period("09:00", "12:00"), make_period("13:00", "16:00"), False),
    (make_period("23:00", "23:59"), make_period("23:30", "23:59"), True),
    (make_period("00:00", "01:00"), make_period("01:00", "02:00"), False),
    (make_period("09:00", "12:00"), make_period("09:00", "12:00"), True),
])
def test_periods_intersect(p1, p2, expected):
    assert periods_intersect(p1, p2) == expected


def test_periods_intersect_dict():
    p1 = {"period_from": "09:00", "period_to": "12:00"}
    p2 = {"period_from": "11:00", "period_to": "14:00"}
    assert periods_intersect(p1, p2) is True


def test_periods_intersect_error():
    # Should handle exceptions gracefully
    p1 = MagicMock()
    p1.period_from = None
    p1.period_to = None
    p2 = MagicMock()
    p2.period_from = None
    p2.period_to = None
    assert periods_intersect(p1, p2) is False


@pytest.mark.parametrize("group_name,expected", [
    ("Група 1.1", "1.1"),
    ("Група 2.5", "2.5"),
    (None, None),
    ("", ""),
    ("Група", "Група"),
    ("SomeGroup 3.2", "3.2"),
])
def test_extract_group_code(group_name, expected):
    assert extract_group_code(group_name) == expected

# --- GroupFilter Tests ---


def test_group_filter_should_include_period():
    logger = logging.getLogger("test")
    gf = GroupFilter(["1.1", "2.5"], logger)
    period = MagicMock()
    period.name = "Група 1.1"
    assert gf.should_include_period(period) is True
    period.name = "Група 3.3"
    assert gf.should_include_period(period) is False


def test_group_filter_no_filter():
    logger = logging.getLogger("test")
    gf = GroupFilter(None, logger)
    period = MagicMock()
    period.name = "Група 1.1"
    assert gf.should_include_period(period) is True


def test_group_filter_filter_periods():
    logger = logging.getLogger("test")
    gf = GroupFilter(["1.1"], logger)
    periods = []
    for code in ["1.1", "2.2"]:
        period = MagicMock()
        period.name = f"Група {code}"
        periods.append(period)
    filtered = gf.filter_periods(periods)
    assert len(filtered) == 1
    assert filtered[0].name == "Група 1.1"


def test_group_filter_logs(caplog):
    logger = logging.getLogger("test")
    gf = GroupFilter(["1.1"], logger)
    periods = []
    for code in ["1.1", "2.2"]:
        period = MagicMock()
        period.name = f"Група {code}"
        periods.append(period)
    with caplog.at_level(logging.INFO):
        gf.filter_periods(periods)
    assert "Filtered 2 periods to 1 based on groups" in caplog.text


def test_group_filter_with_nonstandard_group_name():
    logger = logging.getLogger("test")
    gf = GroupFilter(["1.1"], logger)
    period = MagicMock()
    period.name = "SomeGroup 1.1"
    assert gf.should_include_period(period) is True


def test_group_filter_with_group_name_without_code():
    logger = logging.getLogger("test")
    gf = GroupFilter(["1.1"], logger)
    period = MagicMock()
    period.name = "Група"
    assert gf.should_include_period(period) is False


def test_group_filter_with_group_code_not_in_filter():
    logger = logging.getLogger("test")
    gf = GroupFilter(["1.1"], logger)
    period = MagicMock()
    period.name = "Група 2.2"
    assert gf.should_include_period(period) is False


def test_group_filter_with_empty_name():
    logger = logging.getLogger("test")
    gf = GroupFilter(["1.1"], logger)
    period = MagicMock()
    period.name = ""
    assert gf.should_include_period(period) is False


def test_group_filter_with_none_name():
    logger = logging.getLogger("test")
    gf = GroupFilter(["1.1"], logger)
    period = MagicMock()
    period.name = None
    assert gf.should_include_period(period) is False


def test_group_filter_empty_list():
    logger = logging.getLogger("test")
    gf = GroupFilter(["1.1"], logger)
    filtered = gf.filter_periods([])
    assert filtered == []


def test_group_filter_no_filter_all_pass():
    logger = logging.getLogger("test")
    gf = GroupFilter(None, logger)
    periods = []
    for code in ["1.1", "2.2"]:
        period = MagicMock()
        period.name = f"Група {code}"
        periods.append(period)
    filtered = gf.filter_periods(periods)
    assert len(filtered) == 2

# --- SmartPeriodComparator Tests ---


def test_smart_period_comparator_should_generate():
    logger = logging.getLogger("test")
    comparator = SmartPeriodComparator(logger)
    db = MagicMock()
    new_period = MagicMock()
    new_period.name = "Група 1.1"
    new_period.recid = 1
    new_period.last_update = datetime.now()
    new_period.calendar_event_id = "event1"
    db.get_ukraine_current_date_str.return_value = "15.01.2024"
    db.check_identical_event_exists.return_value = None
    db.find_overlapping_events.return_value = []
    comparator.process_smart_period_comparisons(db, [new_period])
    db.update_calendar_event_state.assert_called_with(1, 'generated')


def test_smart_period_comparator_should_discard_identical():
    logger = logging.getLogger("test")
    comparator = SmartPeriodComparator(logger)
    db = MagicMock()
    new_period = MagicMock()
    new_period.name = "Група 1.1"
    new_period.recid = 2
    new_period.last_update = datetime.now()
    db.get_ukraine_current_date_str.return_value = "15.01.2024"
    db.check_identical_event_exists.return_value = True
    comparator.process_smart_period_comparisons(db, [new_period])
    db.update_calendar_event_state.assert_called_with(2, 'discarded')


def test_smart_period_comparator_overlap_generate_and_cancel():
    logger = logging.getLogger("test")
    comparator = SmartPeriodComparator(logger)
    db = MagicMock()
    new_period = MagicMock()
    new_period.name = "Група 1.1"
    new_period.recid = 3
    new_period.last_update = datetime.now()
    new_period.calendar_event_id = "event3"
    db.get_ukraine_current_date_str.return_value = "15.01.2024"
    db.check_identical_event_exists.return_value = None
    old_period = MagicMock()
    old_period.last_update = datetime.now() - timedelta(days=1)
    db.find_overlapping_events.return_value = [old_period]
    comparator.process_smart_period_comparisons(db, [new_period])
    db.update_calendar_event_state.assert_called_with(3, 'generated')
    db.mark_events_for_cancellation.assert_called_with([old_period])


def test_smart_period_comparator_overlap_discard():
    logger = logging.getLogger("test")
    comparator = SmartPeriodComparator(logger)
    db = MagicMock()
    new_period = MagicMock()
    new_period.name = "Група 1.1"
    new_period.recid = 4
    new_period.last_update = datetime.now() - timedelta(days=1)
    db.get_ukraine_current_date_str.return_value = "15.01.2024"
    db.check_identical_event_exists.return_value = None
    old_period = MagicMock()
    old_period.last_update = datetime.now()
    db.find_overlapping_events.return_value = [old_period]
    comparator.process_smart_period_comparisons(db, [new_period])
    db.update_calendar_event_state.assert_called_with(4, 'discarded')


def test_smart_period_comparator_error_handling():
    logger = logging.getLogger("test")
    comparator = SmartPeriodComparator(logger)
    db = MagicMock()
    db.get_ukraine_current_date_str.side_effect = Exception("fail")
    comparator.process_smart_period_comparisons(db, [])

# --- PeriodComparator Tests ---


def test_period_comparator_power_available():
    logger = logging.getLogger("test")
    comparator = PeriodComparator(logger)
    db = MagicMock()
    period = MagicMock()
    period.name = "Група 1.1"
    period.status = 'Електроенергія є'
    period.calendar_event_state = None
    period.recid = 1
    period.last_update = datetime.now()
    period.insert_ts = datetime.now()

    db.get_ukraine_current_date_str.return_value = "15.01.2024"
    db.get_periods_by_name_and_date.return_value = [period]
    comparator.process_advanced_period_comparisons(db, [period])
    db.update_calendar_event_state.assert_called_with(1, 'generated')


def test_period_comparator_power_outage_intersection():
    logger = logging.getLogger("test")
    comparator = PeriodComparator(logger)
    db = MagicMock()
    period1 = MagicMock()
    period1.name = "Група 1.1"
    period1.status = 'Електроенергії немає'
    period1.calendar_event_state = None
    period1.recid = 1
    period1.last_update = datetime.now()
    period1.insert_ts = datetime.now()
    period1.period_from = "09:00"
    period1.period_to = "12:00"
    period2 = MagicMock()
    period2.name = "Група 1.1"
    period2.status = 'Електроенергії немає'
    period2.calendar_event_state = None
    period2.recid = 2
    period2.last_update = datetime.now() - timedelta(hours=1)
    period2.insert_ts = datetime.now() - timedelta(hours=1)
    period2.period_from = "11:00"
    period2.period_to = "14:00"
    db.get_ukraine_current_date_str.return_value = "15.01.2024"
    db.get_periods_by_name_and_date.return_value = [period1, period2]
    comparator.process_advanced_period_comparisons(db, [period1, period2])
    db.update_calendar_event_state.assert_any_call(1, 'generated')
    db.update_calendar_event_state.assert_any_call(2, 'discarded')


def test_period_comparator_no_existing_periods():
    logger = logging.getLogger("test")
    comparator = PeriodComparator(logger)
    db = MagicMock()
    period = MagicMock()
    period.name = "Група 1.1"
    period.status = 'Електроенергія є'
    db.get_ukraine_current_date_str.return_value = "15.01.2024"
    db.get_periods_by_name_and_date.return_value = []
    comparator.process_advanced_period_comparisons(db, [period])


def test_period_comparator_empty_new_group_periods():
    logger = logging.getLogger("test")
    comparator = PeriodComparator(logger)
    db = MagicMock()
    db.get_ukraine_current_date_str.return_value = "15.01.2024"
    comparator.process_advanced_period_comparisons(db, [])


def test_period_comparator_error_handling():
    logger = logging.getLogger("test")
    comparator = PeriodComparator(logger)
    db = MagicMock()
    db.get_ukraine_current_date_str.side_effect = Exception("fail")
    with pytest.raises(Exception, match="fail"):
        comparator.process_advanced_period_comparisons(db, [])


def test_period_comparator_periods_intersect_objects():
    logger = logging.getLogger("test")
    comparator = PeriodComparator(logger)
    period1 = MagicMock()
    period1.period_from = "09:00"
    period1.period_to = "12:00"
    period2 = MagicMock()
    period2.period_from = "11:00"
    period2.period_to = "14:00"
    assert comparator._periods_intersect_objects(period1, period2) is True
    period2.period_from = "13:00"
    period2.period_to = "16:00"
    assert comparator._periods_intersect_objects(period1, period2) is False


def test_period_comparator_periods_intersect_objects_error():
    logger = logging.getLogger("test")
    comparator = PeriodComparator(logger)
    period1 = MagicMock()
    period1.period_from = None
    period1.period_to = None
    period2 = MagicMock()
    period2.period_from = None
    period2.period_to = None
    assert comparator._periods_intersect_objects(period1, period2) is False
