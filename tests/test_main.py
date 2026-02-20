import pytest
from unittest.mock import patch, MagicMock
# Patch all imports from main.py


@pytest.fixture
def main_module():
    with patch("power_outage_monitor.main.parse_arguments") as mock_parse_args, \
         patch("power_outage_monitor.main.setup_logging") as mock_setup_logging, \
         patch("power_outage_monitor.main.PowerOutageMonitor") as mock_monitor_class:
        yield mock_parse_args, mock_setup_logging, mock_monitor_class


def test_main_success(monkeypatch, main_module):
    mock_parse_args, mock_setup_logging, mock_monitor_class = main_module

    # Setup config and logger
    config = MagicMock()
    config.continuous_mode = False
    config.check_interval = 300
    config.cleanup_days = 7
    config.json_data_dir = "/tmp/json"
    config.ics_output_dir = "/tmp/ics"
    config.log_file = "/tmp/log.txt"
    mock_parse_args.return_value = config

    logger = MagicMock()
    mock_setup_logging.return_value = logger

    monitor = MagicMock()
    monitor.run_full_process.return_value = (True, "success")
    monitor.get_database_stats.return_value = {
        "total_records": 1,
        "unique_dates": 1,
        "unique_groups": 1,
        "last_24h_records": 1
    }
    monitor.database.get_ukraine_current_date_str.return_value = "01.01.2024"
    monitor.query_periods_by_date.return_value = [
        ("Група 1.1", "Електроенергії немає", "09:00", "12:00", "generated", "01.01.2024 09:00", "event1")
    ]
    monitor.export_data_to_csv.return_value = "/tmp/export.csv"
    mock_monitor_class.return_value = monitor

    # Patch print to suppress output
    with patch("builtins.print"):
        from power_outage_monitor.main import main
        main()

    # Check that logger.info was called with expected messages
    assert logger.info.call_count > 0
    monitor.cleanup_old_data.assert_called_once()


def test_main_continuous(monkeypatch, main_module):
    mock_parse_args, mock_setup_logging, mock_monitor_class = main_module

    config = MagicMock()
    config.continuous_mode = True
    config.check_interval = 300
    config.cleanup_days = 7
    config.json_data_dir = "/tmp/json"
    config.ics_output_dir = "/tmp/ics"
    config.log_file = "/tmp/log.txt"
    mock_parse_args.return_value = config

    logger = MagicMock()
    mock_setup_logging.return_value = logger

    monitor = MagicMock()
    monitor.run_continuous_monitoring = MagicMock(side_effect=KeyboardInterrupt)
    mock_monitor_class.return_value = monitor

    # Patch print to suppress output
    with patch("builtins.print"):
        from power_outage_monitor.main import main
        with pytest.raises(SystemExit):
            main()

    monitor.run_continuous_monitoring.assert_called_once()


def test_main_keyboard_interrupt(monkeypatch, main_module):
    mock_parse_args, mock_setup_logging, mock_monitor_class = main_module

    config = MagicMock()
    config.continuous_mode = False
    config.check_interval = 300
    config.cleanup_days = 7
    config.json_data_dir = "/tmp/json"
    config.ics_output_dir = "/tmp/ics"
    config.log_file = "/tmp/log.txt"
    mock_parse_args.return_value = config

    logger = MagicMock()
    mock_setup_logging.return_value = logger

    monitor = MagicMock()
    monitor.run_full_process.side_effect = KeyboardInterrupt
    mock_monitor_class.return_value = monitor

    with patch("builtins.print"):
        from power_outage_monitor.main import main
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0


def test_main_exception(monkeypatch, main_module):
    mock_parse_args, mock_setup_logging, mock_monitor_class = main_module

    config = MagicMock()
    config.continuous_mode = False
    config.check_interval = 300
    config.cleanup_days = 7
    config.json_data_dir = "/tmp/json"
    config.ics_output_dir = "/tmp/ics"
    config.log_file = "/tmp/log.txt"
    mock_parse_args.return_value = config

    logger = MagicMock()
    mock_setup_logging.return_value = logger

    monitor = MagicMock()
    monitor.run_full_process.side_effect = Exception("fail")
    mock_monitor_class.return_value = monitor

    with patch("builtins.print"):
        from power_outage_monitor.main import main
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1


def test_main_no_data(monkeypatch, main_module):
    mock_parse_args, mock_setup_logging, mock_monitor_class = main_module

    config = MagicMock()
    config.continuous_mode = False
    config.check_interval = 300
    config.cleanup_days = 7
    config.json_data_dir = "/tmp/json"
    config.ics_output_dir = "/tmp/ics"
    config.log_file = "/tmp/log.txt"
    mock_parse_args.return_value = config

    logger = MagicMock()
    mock_setup_logging.return_value = logger

    monitor = MagicMock()
    monitor.run_full_process.return_value = (True, "no_data")
    monitor.get_database_stats.return_value = {
        "total_records": 1,
        "unique_dates": 1,
        "unique_groups": 1,
        "last_24h_records": 1
    }
    monitor.database.get_ukraine_current_date_str.return_value = "01.01.2024"
    monitor.query_periods_by_date.return_value = []
    monitor.export_data_to_csv.return_value = "/tmp/export.csv"
    mock_monitor_class.return_value = monitor

    with patch("builtins.print"):
        from power_outage_monitor.main import main
        main()

    monitor.cleanup_old_data.assert_called_once()
