import pytest
from unittest.mock import MagicMock, patch
import json

from power_outage_monitor.scraper import PowerOutageScraper


@pytest.fixture
def logger():
    return MagicMock()


@pytest.fixture
def scraper(logger):
    return PowerOutageScraper(
        base_url="http://test", timeout=5, headless=True, logger=logger
    )


def test_init_sets_attributes(scraper):
    assert scraper.base_url == "http://test"
    assert scraper.timeout == 5
    assert scraper.headless is True
    assert scraper.logger is not None


def test_get_ukraine_current_date_and_str(scraper):
    date_str = scraper.get_ukraine_current_date_str()
    assert isinstance(date_str, str)
    assert len(date_str) == 10


@pytest.mark.parametrize(
    "input_str,expected",
    [
        ("14:30 17.02.2026", "17.02.2026 14:30"),
        ("2026-02-17T14:30:00", "17.02.2026 14:30"),
        ("bad format", "bad format"),
    ],
)
def test_normalize_last_update(scraper, input_str, expected):
    assert scraper.normalize_last_update(input_str) == expected


def test_parse_power_off_text(scraper):
    text = (
        "Графік погодинних відключень на 17.02.2026\n"
        "Інформація станом на 14:30 17.02.2026\n"
        "Група 1.1. Електроенергії немає з 09:00 до 12:00.\n"
        "Група 2.1. Електроенергія є.\n"
    )
    result = scraper.parse_power_off_text(text)
    assert result["date"] == "17.02.2026"
    assert result["last_update"] == "17.02.2026 14:30"
    assert result["date_found"] is True
    assert result["last_update_found"] is True
    assert len(result["groups"]) == 2
    assert result["groups"][0]["name"] == "Група 1.1"
    assert result["groups"][0]["status"] == "Електроенергії немає"
    assert result["groups"][0]["period"]["from"] == "09:00"
    assert result["groups"][0]["period"]["to"] == "12:00"
    assert result["groups"][1]["status"] == "Електроенергія є"


def test_parse_power_off_text_handles_24_00(scraper):
    text = (
        "Графік погодинних відключень на 17.02.2026\n"
        "Інформація станом на 14:30 17.02.2026\n"
        "Група 1.1. Електроенергії немає з 23:00 до 24:00.\n"
    )
    result = scraper.parse_power_off_text(text)
    assert result["groups"][0]["period"]["to"] == "23:59"


def test_validate_schedule_data(scraper):
    # Valid, current date
    today = scraper.get_ukraine_current_date().strftime("%d.%m.%Y")
    data = {
        "date": today,
        "date_found": True,
        "groups": [{"name": "Група 1.1", "status": "Електроенергія є"}],
    }
    valid, code, msg = scraper.validate_schedule_data(data)
    assert valid is True
    assert code == "current_data"

    # Valid, future date
    future = (
        scraper.get_ukraine_current_date().replace(
            year=scraper.get_ukraine_current_date().year + 1
        )
    ).strftime("%d.%m.%Y")
    data = {
        "date": future,
        "date_found": True,
        "groups": [{"name": "Група 1.1", "status": "Електроенергія є"}],
    }
    valid, code, msg = scraper.validate_schedule_data(data)
    assert valid is True
    assert code == "future_data"

    # Old date
    old = (
        scraper.get_ukraine_current_date().replace(
            year=scraper.get_ukraine_current_date().year - 1
        )
    ).strftime("%d.%m.%Y")
    data = {
        "date": old,
        "date_found": True,
        "groups": [{"name": "Група 1.1", "status": "Електроенергія є"}],
    }
    valid, code, msg = scraper.validate_schedule_data(data)
    assert valid is False
    assert code == "old_data"

    # No data
    valid, code, msg = scraper.validate_schedule_data({})
    assert valid is False
    assert code == "no_data"

    # Invalid date
    data = {
        "date": "bad",
        "date_found": True,
        "groups": [{"name": "Група 1.1", "status": "Електроенергія є"}],
    }
    valid, code, msg = scraper.validate_schedule_data(data)
    assert valid is False
    assert code == "invalid_date"


def test_save_raw_data_and_error(scraper, tmp_path):
    data = {"test": "value"}
    result = scraper.save_raw_data(data, tmp_path)
    assert result.exists()
    with open(result, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["test"] == "value"

    # Test error path
    result = scraper.save_raw_data(None, tmp_path)
    assert result is None


def test_convert_to_outage_periods(scraper):
    # Patch OutagePeriod for this test
    with patch("power_outage_monitor.scraper.OutagePeriod") as MockPeriod:
        data = {
            "date": "17.02.2026",
            "last_update": "17.02.2026 14:30",
            "groups": [
                {
                    "name": "Група 1.1",
                    "status": "Електроенергії немає",
                    "period": {"from": "09:00", "to": "12:00"},
                }
            ],
        }
        periods = scraper.convert_to_outage_periods(data)
        assert len(periods) == 1
        MockPeriod.assert_called_once()
        args, kwargs = MockPeriod.call_args
        assert kwargs["name"] == "Група 1.1"
        assert kwargs["status"] == "Електроенергії немає"
        assert kwargs["period_from"] == "09:00"
        assert kwargs["period_to"] == "12:00"


def test_convert_to_outage_periods_empty(scraper):
    with patch("power_outage_monitor.scraper.OutagePeriod"):
        periods = scraper.convert_to_outage_periods({})
        assert periods == []
        periods = scraper.convert_to_outage_periods({"groups": []})
        assert periods == []


def test_convert_to_outage_periods_error(scraper):
    with patch(
        "power_outage_monitor.scraper.OutagePeriod", side_effect=Exception("fail")
    ):
        data = {
            "date": "17.02.2026",
            "last_update": "17.02.2026 14:30",
            "groups": [
                {
                    "name": "Група 1.1",
                    "status": "Електроенергії немає",
                    "period": {"from": "09:00", "to": "12:00"},
                }
            ],
        }
        with pytest.raises(Exception):
            scraper.convert_to_outage_periods(data)


def test_extract_dynamic_content_success(scraper):
    # Patch _setup_driver and driver methods
    driver = MagicMock()
    scraper._setup_driver = MagicMock(return_value=driver)
    element = MagicMock()
    element.text = (
        "Графік погодинних відключень на 17.02.2026\n"
        "Інформація станом на 14:30 17.02.2026\n"
        "Група 1.1. Електроенергії немає з 09:00 до 12:00.\n"
    )
    driver.find_elements.return_value = [element]
    driver.find_element.return_value.text = element.text
    result = scraper.extract_dynamic_content()
    assert result["date"] == "17.02.2026"
    driver.quit.assert_called_once()


def test_extract_dynamic_content_error(scraper):
    scraper._setup_driver = MagicMock(side_effect=Exception("fail"))
    result = scraper.extract_dynamic_content()
    assert result is None
