"""Web scraping and parsing logic for Power Outage Monitor."""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
import pytz

from .db import OutagePeriod


class PowerOutageScraper:
    """Handles web scraping and parsing of power outage data."""
    
    def __init__(self, base_url: str, timeout: int, headless: bool, logger: logging.Logger):
        self.base_url = base_url
        self.timeout = timeout
        self.headless = headless
        self.logger = logger
        self.ukraine_tz = pytz.timezone('Europe/Kiev')
        self.driver: Optional[webdriver.Chrome] = None
    
    def _setup_driver(self) -> webdriver.Chrome:
        """Setup and return Chrome WebDriver."""
        options = Options()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        try:
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(self.timeout)
            return driver
        except Exception as e:
            self.logger.error(f"Failed to setup Chrome driver: {e}")
            raise
    
    def get_ukraine_current_date(self) -> datetime.date:
        """Get current date in Ukraine timezone"""
        current_datetime_ukraine = datetime.now(self.ukraine_tz)
        return current_datetime_ukraine.date()
    
    def get_ukraine_current_date_str(self) -> str:
        """Get current date in Ukraine timezone as string"""
        return self.get_ukraine_current_date().strftime('%d.%m.%Y')
    
    def normalize_last_update(self, last_update_str: str) -> str:
        """Normalize last update string to standard format"""
        try:
            dt = datetime.strptime(last_update_str, "%H:%M %d.%m.%Y")
            return dt.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            pass
        
        try:
            dt = datetime.fromisoformat(last_update_str)
            return dt.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            pass
        
        return last_update_str
    
    def parse_power_off_text(self, text: str) -> Dict[str, Any]:
        """Parse Ukrainian power outage text into structured data"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        result = {
            "date": None,
            "last_update": None,
            "groups": [],
            "date_found": False,
            "last_update_found": False
        }
        
        # Parse date line
        for line in lines:
            # Match: "Графік погодинних відключень на 17.02.2026"
            m = re.match(r"Графік погодинних відключень на (\d{2}\.\d{2}\.\d{4})", line)
            if m:
                result["date"] = m.group(1)
                result["date_found"] = True
                break
        
        # Parse last update line
        for line in lines:
            # Match: "Інформація станом на 14:30 17.02.2026"
            m = re.match(r"Інформація станом на (\d{2}:\d{2} \d{2}\.\d{2}\.\d{4})", line)
            if m:
                result["last_update"] = self.normalize_last_update(m.group(1))
                result["last_update_found"] = True
                break
        
        # Parse group lines with exact Ukrainian pattern
        group_pattern = re.compile(
            r"^(Група \d+\.\d+)\. (Електроенергії немає|Електроенергія є)(?: з (\d{2}:\d{2}) до (\d{2}:\d{2}))?\."
        )
        
        for line in lines:
            m = group_pattern.match(line)
            if m:
                group = {
                    "name": m.group(1),
                    "status": m.group(2)
                }
                
                if m.group(3) and m.group(4):
                    period_from = m.group(3)
                    period_to = m.group(4)
                    
                    # Handle 24:00 -> 23:59 conversion
                    if period_to == "24:00":
                        period_to = "23:59"
                    if period_from == "24:00":
                        period_from = "23:59"
                    
                    group["period"] = {
                        "from": period_from,
                        "to": period_to
                    }
                
                result["groups"].append(group)
        
        return result
    
    def validate_schedule_data(self, parsed_data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Validate schedule data with detailed status codes"""
        if not parsed_data:
            return False, "no_data", "ГАВ розклад відсутній"
        
        if not parsed_data.get('date_found', False) or not parsed_data.get('date'):
            return False, "no_data", "ГАВ розклад відсутній"
        
        if not parsed_data.get('groups') or len(parsed_data['groups']) == 0:
            return False, "no_data", "ГАВ розклад відсутній"
        
        try:
            current_date_ukraine = self.get_ukraine_current_date()
            schedule_date = datetime.strptime(parsed_data['date'], "%d.%m.%Y").date()
            if schedule_date < current_date_ukraine:
                return False, "old_data", f"ГАВ розклад застарілий - дата {parsed_data['date']}, поточна дата {current_date_ukraine.strftime('%d.%m.%Y')}"
            elif schedule_date == current_date_ukraine:
                return True, "current_data", f"ГАВ розклад актуальний - дата {parsed_data['date']}"
            else:
                return True, "future_data", f"ГАВ розклад на майбутню дату - дата {parsed_data['date']}"
                
        except ValueError:
            return False, "invalid_date", f"ГАВ розклад має некоректну дату: {parsed_data.get('date', 'невідома')}"
    
    def extract_dynamic_content(self) -> Optional[Dict[str, Any]]:
        """Extract dynamic content from the website"""
        try:
            self.driver = self._setup_driver()
            self.logger.info(f"Starting browser...")
            self.logger.info(f"Loading: {self.base_url}")
            self.driver.get(self.base_url)
            
            self.logger.info(f"Waiting for content to load...")
            time.sleep(5)
            
            # Try specific selectors first
            selectors_to_try = [
                "div[class='power-off__text']"
            ]
            
            found_content = False
            parsed = None
            
            for selector in selectors_to_try:
                try:
                    self.logger.info(f"Trying selector: {selector}")
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for i, element in enumerate(elements):
                        text = element.text.strip()
                        if text and len(text) > 50:
                            parsed = self.parse_power_off_text(text)
                            found_content = True
                            break
                    
                    if found_content:
                        break
                        
                except Exception as e:
                    print(f"  Error with {selector}: {e}")
            
            # If no specific content found, get all page text
            if not found_content:
                print("No specific content found, getting all page text:")
                all_text = self.driver.find_element(By.TAG_NAME, "body").text
                parsed = self.parse_power_off_text(all_text)
                
                # Save debug content
                with open('selenium_all_content.txt', 'w', encoding='utf-8') as f:
                    f.write("All page content:\n")
                    f.write("=" * 60 + "\n")
                    f.write(all_text)
            
            return parsed
            
        except Exception as e:
            print(f"Error: {e}")
            self.logger.error(f"Error during content extraction: {e}")
            return None
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
    
    def save_raw_data(self, data: Dict[str, Any], json_dir: Path) -> Optional[Path]:
        """Save scraped data to timestamped JSON file."""
        if not data:
            self.logger.error("No data to store")
            return None
        
        json_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_power_outages.json"
        filepath = json_dir / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"[OK] JSON stored: {filename}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"[ERROR] JSON storage error: {e}")
            return None
    
    def convert_to_outage_periods(self, data: Dict[str, Any]) -> List[OutagePeriod]:
        """Convert parsed data to OutagePeriod objects"""
        try:
            self.logger.debug("Converting parsed data to OutagePeriod objects...")
            
            periods = []

            if not data or not data.get('groups'):
                return periods

            insert_ts = datetime.now().isoformat()

            for group in data['groups']:
                period_from = group.get('period', {}).get('from', '')
                period_to = group.get('period', {}).get('to', '')

                period = OutagePeriod(
                    insert_ts=insert_ts,
                    date=data['date'],
                    last_update=data['last_update'],
                    name=group['name'],
                    status=group['status'],
                    period_from=period_from,
                    period_to=period_to,
                    calendar_event_state='pending',
                    calendar_event_ts=insert_ts
                )

                periods.append(period)

            return periods
        except Exception as e:
            self.logger.error(f"Error converting data to OutagePeriods: {e}")
            raise   