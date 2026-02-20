import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from power_outage_monitor.monitor import PowerOutageMonitor


@pytest.fixture
def config(tmp_path):
    cfg = MagicMock()
    cfg.db_path = tmp_path / "db.sqlite"
    cfg.base_url = "http://test"
    cfg.selenium_timeout = 10
    cfg.headless = True
    cfg.ics_output_dir = tmp_path / "ics"
    cfg.ics_timezone = "Europe/Kyiv"
    cfg.calendar_name = "Test Calendar"
    cfg.group_filter = ["1.1", "2.1"]
    cfg.json_data_dir = tmp_path / "json"
    cfg.cleanup_days = 7
    return cfg


@pytest.fixture
def logger():
    return MagicMock()


@pytest.fixture
def monitor(config, logger):
    with patch("power_outage_monitor.monitor.PowerOutageDatabase") as MockDB, patch(
        "power_outage_monitor.monitor.PowerOutageScraper"
    ) as MockScraper, patch(
        "power_outage_monitor.monitor.ICSEventGenerator"
    ) as MockICS, patch(
        "power_outage_monitor.monitor.GroupFilter"
    ) as MockGroupFilter, patch(
        "power_outage_monitor.monitor.SmartPeriodComparator"
    ) as MockComparator:
        db = MockDB.return_value
        scraper = MockScraper.return_value
        ics = MockICS.return_value
        group_filter = MockGroupFilter.return_value
        comparator = MockComparator.return_value
        # Set up default return values for stats
        db.get_comprehensive_stats.return_value = {
            "total_records": 10,
            "unique_dates": 2,
            "unique_groups": 3,
            "date_range": {"from": "2024-01-01", "to": "2024-01-02"},
            "last_24h_records": 5,
            "events_sent": 7,
            "events_pending": 3,
            "by_state": {"generated": 5, "discarded": 2},
            "by_status": {"on": 6, "off": 4},
        }
        db.get_ukraine_current_date_str.return_value = "2024-01-01"
        return PowerOutageMonitor(config, logger)


def test_init_creates_dirs_and_logs(config, logger):
    with patch.object(Path, "mkdir") as mock_mkdir, patch(
        "power_outage_monitor.monitor.PowerOutageDatabase"
    ), patch("power_outage_monitor.monitor.PowerOutageScraper"), patch(
        "power_outage_monitor.monitor.ICSEventGenerator"
    ), patch(
        "power_outage_monitor.monitor.GroupFilter"
    ), patch(
        "power_outage_monitor.monitor.SmartPeriodComparator"
    ):
        PowerOutageMonitor(config, logger)
        # Should be called for both json_data_dir and ics_output_dir
        assert mock_mkdir.call_count == 2
        mock_mkdir.assert_any_call(exist_ok=True)


def test_show_startup_info(monitor, logger):
    monitor.show_startup_info()
    # Should log info about startup and stats
    assert any(
        "POWER OUTAGE MONITOR - STARTUP INFORMATION" in str(call)
        for call in logger.info.call_args_list
    )


def test_run_full_process_success(monitor):
    # Patch dependencies for a successful run
    monitor.scraper.extract_dynamic_content.return_value = {"date": "2024-01-01"}
    monitor.scraper.validate_schedule_data.return_value = (True, "current_data", "OK")
    monitor.scraper.save_raw_data.return_value = Path("test.json")
    monitor.stage3_enhanced_database_operations = MagicMock(
        return_value=Path("events.json")
    )
    monitor.stage4_enhanced_calendar_generation = MagicMock()
    success, status = monitor.run_full_process()
    assert success is True
    assert status == "success"


def test_run_full_process_invalid_data(monitor):
    monitor.scraper.extract_dynamic_content.return_value = {"date": "2024-01-01"}
    monitor.scraper.validate_schedule_data.return_value = (False, "no_data", "No data")
    success, status = monitor.run_full_process()
    assert success is True
    assert status == "no_data"


def test_run_full_process_json_storage_fail(monitor):
    monitor.scraper.extract_dynamic_content.return_value = {"date": "2024-01-01"}
    monitor.scraper.validate_schedule_data.return_value = (True, "current_data", "OK")
    monitor.scraper.save_raw_data.return_value = None
    success, status = monitor.run_full_process()
    assert success is False
    assert status == "error"


def test_run_full_process_db_ops_fail(monitor):
    monitor.scraper.extract_dynamic_content.return_value = {"date": "2024-01-01"}
    monitor.scraper.validate_schedule_data.return_value = (True, "current_data", "OK")
    monitor.scraper.save_raw_data.return_value = Path("test.json")
    monitor.stage3_enhanced_database_operations = MagicMock(return_value=None)
    success, status = monitor.run_full_process()
    assert success is False
    assert status == "error"


def test_run_full_process_exception(monitor):
    monitor.scraper.extract_dynamic_content.side_effect = Exception("fail")
    success, status = monitor.run_full_process()
    assert success is False
    assert status == "error"


def test_stage3_enhanced_database_operations_file_not_found(monitor):
    result = monitor.stage3_enhanced_database_operations(None)
    assert result is None


def test_stage3_enhanced_database_operations_json_load_error(monitor, tmp_path):
    file = tmp_path / "bad.json"
    file.write_text("{bad json")
    result = monitor.stage3_enhanced_database_operations(file)
    assert result is None


def test_stage3_enhanced_database_operations_convert_error(monitor, tmp_path):
    file = tmp_path / "good.json"
    file.write_text("[]")
    monitor.scraper.convert_to_outage_periods.side_effect = Exception("fail")
    result = monitor.stage3_enhanced_database_operations(file)
    assert result is None


def test_stage3_enhanced_database_operations_group_filter_error(monitor, tmp_path):
    file = tmp_path / "good.json"
    file.write_text("[]")
    monitor.scraper.convert_to_outage_periods.return_value = []
    monitor.group_filter.filter_periods.side_effect = Exception("fail")
    result = monitor.stage3_enhanced_database_operations(file)
    assert result is None


def test_stage3_enhanced_database_operations_insert_error(monitor, tmp_path):
    file = tmp_path / "good.json"
    file.write_text("[]")
    period = MagicMock()
    monitor.scraper.convert_to_outage_periods.return_value = [period]
    monitor.group_filter.filter_periods.return_value = [period]
    monitor.database.insert_period.side_effect = Exception("fail")
    # Should still proceed and log error
    result = monitor.stage3_enhanced_database_operations(file)
    assert result is None or isinstance(result, Path)  # Could fail later


def test_generate_enhanced_calendar_events_json_success(monitor, tmp_path):
    class Event:
        def __init__(
            self,
            calendar_event_id,
            calendar_event_uid,
            date,
            name,
            status,
            period_from,
            period_to,
            last_update,
            recid,
        ):
            self.calendar_event_id = calendar_event_id
            self.calendar_event_uid = calendar_event_uid
            self.date = date
            self.name = name
            self.status = status
            self.period_from = period_from
            self.period_to = period_to
            self.last_update = last_update
            self.recid = recid

    class CancelEvent:
        def __init__(self, calendar_event_id, calendar_event_uid, recid):
            self.calendar_event_id = calendar_event_id
            self.calendar_event_uid = calendar_event_uid
            self.recid = recid

    monitor.database.get_events_for_generation.return_value = {
        "events_to_create": [
            Event(
                "id1",
                "uid1",
                "2024-01-01",
                "Група 1.1",
                "on",
                "09:00",
                "12:00",
                "2024-01-01T09:00",
                1,
            )
        ],
        "events_to_cancel": [CancelEvent("id2", "uid2", 2)],
    }
    monitor.config.ics_output_dir = tmp_path
    result = monitor.generate_enhanced_calendar_events_json()
    assert result is not None
    assert result.exists()
    data = result.read_text(encoding="utf-8")
    assert "events_to_create" in data
    assert "events_to_cancel" in data


def test_generate_enhanced_calendar_events_json_db_error(monitor):
    monitor.database.get_events_for_generation.side_effect = Exception("fail")
    result = monitor.generate_enhanced_calendar_events_json()
    assert result is None


def test_generate_enhanced_calendar_events_json_file_error(monitor, tmp_path):
    monitor.database.get_events_for_generation.return_value = {
        "events_to_create": [],
        "events_to_cancel": [],
    }
    monitor.config.ics_output_dir = tmp_path
    # Patch open to raise error
    with patch("builtins.open", side_effect=Exception("fail")):
        result = monitor.generate_enhanced_calendar_events_json()
        assert result is None


def test_stage4_enhanced_calendar_generation_file_not_found(monitor):
    monitor.logger.reset_mock()
    monitor.stage4_enhanced_calendar_generation(None)
    assert monitor.logger.error.called


def test_stage4_enhanced_calendar_generation_json_load_error(monitor, tmp_path):
    file = tmp_path / "bad.json"
    file.write_text("{bad json")
    monitor.logger.reset_mock()
    monitor.stage4_enhanced_calendar_generation(file)
    assert monitor.logger.error.called


def test_stage4_enhanced_calendar_generation_no_events(monitor, tmp_path):
    file = tmp_path / "events.json"
    file.write_text('{"events_to_create": [], "events_to_cancel": []}')
    monitor.logger.reset_mock()
    monitor.stage4_enhanced_calendar_generation(file)
    assert monitor.logger.info.called


def test_stage4_enhanced_calendar_generation_create_and_cancel(monitor, tmp_path):
    file = tmp_path / "events.json"
    file.write_text(
        '{"events_to_create": [{"recid": 1, "calendar_event_id": "id1"}], "events_to_cancel": [{"recid": 2, "calendar_event_id": "id2"}]}'
    )
    monitor.ics_generator.create_cancellation_ics_file = MagicMock()
    monitor.ics_generator.generate_deletion_summary = MagicMock()
    monitor.ics_generator.generate_ics_files = MagicMock()
    monitor.database.update_calendar_event_state = MagicMock()
    monitor.database.mark_event_as_sent = MagicMock()
    monitor.logger.reset_mock()
    monitor.stage4_enhanced_calendar_generation(file)
    assert monitor.ics_generator.create_cancellation_ics_file.called
    assert monitor.ics_generator.generate_deletion_summary.called
    assert monitor.ics_generator.generate_ics_files.called
    assert monitor.database.update_calendar_event_state.called
    assert monitor.database.mark_event_as_sent.called


def test_cleanup_old_data(monitor):
    monitor.database.cleanup_old_data.return_value = 5
    assert monitor.cleanup_old_data(3) == 5


def test_get_database_stats(monitor):
    stats = monitor.get_database_stats()
    assert isinstance(stats, dict)
    assert "total_records" in stats


def test_query_periods_by_date(monitor):
    monitor.database.query_periods_by_date.return_value = [MagicMock()]
    result = monitor.query_periods_by_date("2024-01-01")
    assert isinstance(result, list)


def test_export_data_to_csv_success(monitor, tmp_path):
    monitor.database.export_to_csv = MagicMock()
    result = monitor.export_data_to_csv(str(tmp_path / "export.csv"))
    assert result.endswith("export.csv")


def test_export_data_to_csv_error(monitor):
    monitor.database.export_to_csv.side_effect = Exception("fail")
    result = monitor.export_data_to_csv("fail.csv")
    assert result is None


def test_get_event_summary(monitor):
    summary = monitor.get_event_summary()
    assert "total_events" in summary
    assert "events_sent" in summary
    assert "events_pending" in summary
    assert "events_by_state" in summary
    assert "last_24h_activity" in summary
