"""Main orchestrator for Power Outage Monitor with enhanced event tracking."""

import time
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import logging
from datetime import datetime

from .config import Config
from .db import PowerOutageDatabase
from .scraper import PowerOutageScraper
from .icsgen import ICSEventGenerator
from .utils import GroupFilter, SmartPeriodComparator


class PowerOutageMonitor:
    """Main orchestrator that coordinates all components with enhanced event tracking."""

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger

        # Initialize components
        self.database = PowerOutageDatabase(config.db_path, logger)
        self.scraper = PowerOutageScraper(
            config.base_url,
            config.selenium_timeout,
            config.headless,
            logger
        )
        self.ics_generator = ICSEventGenerator(
            config.ics_output_dir,
            config.ics_timezone,
            config.calendar_name,
            logger
        )
        self.group_filter = GroupFilter(config.group_filter, logger)
        self.smart_comparator = SmartPeriodComparator(logger)

        # Create directories
        for directory in [config.json_data_dir, config.ics_output_dir]:
            directory.mkdir(exist_ok=True)

        self.show_startup_info()
        self.logger.info("Power Outage Monitor initialized with enhanced event tracking")
        self.logger.info("=" * 60)

    def show_startup_info(self) -> None:
        """Show comprehensive startup information"""
        stats = self.database.get_comprehensive_stats()

        self.logger.info("=" * 60)
        self.logger.info("POWER OUTAGE MONITOR - STARTUP INFORMATION")
        self.logger.info("=" * 60)

        if self.config.group_filter:
            self.logger.info(f"Groups filter applied: {sorted(self.config.group_filter)}")
        else:
            self.logger.info("Executed without groups filter")

        self.logger.info(f"Database: {self.config.db_path}")
        self.logger.info(f"Ukraine current date: {self.database.get_ukraine_current_date_str()}")
        self.logger.info(f"Total records: {stats['total_records']}")
        self.logger.info(f"Unique dates: {stats['unique_dates']}")
        self.logger.info(f"Unique groups: {stats['unique_groups']}")
        self.logger.info(f"Date range: {stats['date_range']['from']} to {stats['date_range']['to']}")
        self.logger.info(f"Records in last 24h: {stats['last_24h_records']}")
        self.logger.info(f"Events sent: {stats['events_sent']}")
        self.logger.info(f"Events pending: {stats['events_pending']}")

        if stats['by_state']:
            self.logger.info("Records by calendar state:")
            for state, count in stats['by_state'].items():
                self.logger.info(f"  {state}: {count}")

        if stats['by_status']:
            self.logger.info("Records by power status:")
            for status, count in stats['by_status'].items():
                self.logger.info(f"  {status}: {count}")

        self.logger.info("=" * 60)

    def run_full_process(self) -> Tuple[bool, str]:
        """Run complete power outage monitoring process with enhanced logic"""
        self.logger.info("Starting complete power outage monitoring process")

        try:
            # Stage 1: Extract dynamic content
            self.logger.info("=" * 60)
            self.logger.info("=== STAGE 1: Extract dynamic content ===")
            self.logger.info("=" * 60)
            json_data = self.scraper.extract_dynamic_content()

            # Validate schedule data
            is_valid, status_code, status_message = self.scraper.validate_schedule_data(json_data)

            if not is_valid:
                self.logger.info(status_message)
                if status_code in ['no_data', 'no_groups']:
                    print("Розклад відсутній на сьогодні - файли не створюються")
                elif status_code == 'old_data':
                    print("Розклад застарілий - файли не створюються")
                elif status_code == 'invalid_date':
                    print("Розклад має некоректну дату - файли не створюються")
                return True, status_code

            self.logger.info(status_message)
            if status_code == 'current_data':
                print(f"Розклад актуальний на {json_data['date']} - обробка продовжується")
            elif status_code == 'future_data':
                print(f"Розклад на майбутню дату {json_data['date']} - обробка продовжується")

            # Stage 2: Store JSON
            self.logger.info("=" * 60)
            self.logger.info("=== STAGE 2: Store JSON ===")
            self.logger.info("=" * 60)
            json_filepath = self.scraper.save_raw_data(json_data, self.config.json_data_dir)
            if not json_filepath:
                self.logger.error("Stage 2 failed - JSON storage")
                return False, "error"

            # Stage 3: Enhanced database operations
            self.logger.info("=" * 60)
            self.logger.info("=== STAGE 3: Enhanced database operations ===")
            self.logger.info("=" * 60)
            events_json_filepath = self.stage3_enhanced_database_operations(json_filepath)
            if not events_json_filepath:
                self.logger.error("Stage 3 failed - database operations")
                return False, "error"

            # Stage 4: Enhanced calendar file generation
            self.stage4_enhanced_calendar_generation(events_json_filepath)

            self.logger.info("[OK] Complete process finished successfully")
            return True, "success"

        except Exception as e:
            self.logger.error(f"Process error: {e}")
            return False, "error"

    def stage3_enhanced_database_operations(self, json_filepath: Path) -> Optional[Path]:
        """Enhanced Stage 3: Database operations with smart overlap detection"""

        if not json_filepath or not json_filepath.exists():
            self.logger.error("JSON file not found")
            return None

        try:
            with open(json_filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.logger.debug(f"Loaded JSON data: {len(data)}")
        except Exception as e:
            self.logger.error(f"Error loading JSON: {e}")
            return None

        # Convert to OutagePeriod objects
        try:
            self.logger.debug("Converting to OutagePeriod objects...")
            periods = self.scraper.convert_to_outage_periods(data)
            self.logger.debug(f"Converted {len(periods)} periods")
        except Exception as e:
            self.logger.error(f"Error in convert_to_outage_periods: {e}")
            return None

        # Apply group filter
        try:
            self.logger.debug("Applying group filter...")
            filtered_periods = self.group_filter.filter_periods(periods)
            self.logger.debug(f"Filtered to {len(filtered_periods)} periods")
        except Exception as e:
            self.logger.error(f"Error in group filtering: {e}")
            return None

        # Insert new periods into database
        try:
            self.logger.debug("Inserting periods into database...")

            inserted_count = 0
            inserted_periods = []

            for period in filtered_periods:
                try:
                    recid = self.database.insert_period(period)
                    period.recid = recid
                    inserted_periods.append(period)
                    inserted_count += 1
                    self.logger.debug(f"Inserted period {recid} for {period.name}")
                except Exception as e:
                    self.logger.error(f"Error inserting period: {e}")

            self.logger.info(f"[OK] Inserted {inserted_count} new records")
        except Exception as e:
            self.logger.error(f"Error in database insertion: {e}")
            return None

        # Use smart period comparator for enhanced logic
        try:
            self.logger.debug("Starting smart period comparison...")
            self.smart_comparator.process_smart_period_comparisons(self.database, inserted_periods)
            self.logger.debug("Smart period comparison completed")
        except Exception as e:
            self.logger.error(f"Error in smart period comparison: {e}")
            return None

        # Generate enhanced calendar events JSON
        try:
            self.logger.debug("Generating enhanced calendar events JSON...")
            result = self.generate_enhanced_calendar_events_json()
            self.logger.debug(f"Calendar events JSON generation result: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error generating calendar events JSON: {e}")
            return None

    def generate_enhanced_calendar_events_json(self) -> Optional[Path]:
        """Generate enhanced calendar events JSON with proper event tracking."""
        self.logger.info("Generating enhanced calendar events JSON...")
        try:

            self.logger.debug("Call for get_events_for_generation")
            self.logger.debug(f"Current group filter: {self.config.group_filter}")
            # Get events that need processing
            events_data = self.database.get_events_for_generation(self.config.group_filter)
        except Exception as e:
            self.logger.error(f"Error in get_events_for_generation: {e}")
            return None

        events_to_create = events_data['events_to_create']
        events_to_cancel = events_data['events_to_cancel']
        # Prepare result
        result = {
            'events_to_create': [
                {
                    'calendar_event_id': event.calendar_event_id,
                    'calendar_event_uid': event.calendar_event_uid,
                    'date': event.date,
                    'name': event.name,
                    'status': event.status,
                    'period_from': event.period_from,
                    'period_to': event.period_to,
                    'last_update': event.last_update,
                    'recid': event.recid  # Include recid for tracking
                }
                for event in events_to_create
            ],
            'events_to_cancel': [
                {
                    'calendar_event_id': event.calendar_event_id,
                    'calendar_event_uid': event.calendar_event_uid,
                    'recid': event.recid
                }
                for event in events_to_cancel
            ],
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'create_count': len(events_to_create),
                'cancel_count': len(events_to_cancel)
            }
        }
        # Save to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_calendar_events.json"
        filepath = self.config.ics_output_dir / filename

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            self.logger.info(f"[OK] Enhanced calendar events JSON created: {filename}")
            self.logger.info(f"  Events to create: {len(events_to_create)}")
            self.logger.info(f"  Events to cancel: {len(events_to_cancel)}")

            return filepath

        except Exception as e:
            self.logger.error(f"Error creating calendar events JSON: {e}")
            return None

    def stage4_enhanced_calendar_generation(self, events_json_filepath: Path) -> None:
        """Enhanced Stage 4: Generate ICS files and mark events as sent"""

        self.logger.info("=" * 60)
        self.logger.info("=== STAGE 4: Enhanced ICS calendar file generation ===")
        self.logger.info("=" * 60)

        if not events_json_filepath or not events_json_filepath.exists():
            self.logger.error("Events JSON file not found")
            return

        try:
            with open(events_json_filepath, 'r', encoding='utf-8') as f:
                events_data = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading events JSON: {e}")
            return

        events_to_create = events_data.get('events_to_create', [])
        events_to_cancel = events_data.get('events_to_cancel', [])

        if not events_to_create and not events_to_cancel:
            self.logger.info("No events to create or cancel - skipping calendar file generation")
            return

        # Generate cancellation files for events to cancel
        if events_to_cancel:
            self.ics_generator.create_cancellation_ics_file(events_to_cancel)
            self.ics_generator.generate_deletion_summary([event['calendar_event_id'] for event in events_to_cancel])

            # Mark cancelled events as processed
            for event in events_to_cancel:
                self.database.update_calendar_event_state(event['recid'], 'discarded')
                self.logger.debug(f"Marked cancelled event {event['recid']} as discarded")

        # Generate ICS files for new events
        if events_to_create:
            self.ics_generator.generate_ics_files(events_to_create)

            # Mark created events as sent
            for event in events_to_create:
                self.database.mark_event_as_sent(event['recid'])
                self.logger.debug(f"Marked event {event['recid']} as sent")

        self.logger.info(f"[OK] Enhanced calendar generation completed: {len(events_to_create)} created, {len(events_to_cancel)} cancelled")

    def run_continuous_monitoring(self, interval_minutes: int = 5) -> None:
        """Run continuous monitoring with specified interval"""
        self.logger.info(f"Starting continuous monitoring (every {interval_minutes} minutes)")
        self.logger.info("Press Ctrl+C to stop")

        while True:
            try:
                success, status = self.run_full_process()

                if success:
                    stats = self.database.get_comprehensive_stats()
                    if status == "success":
                        self.logger.info("Моніторинг: успішно, статус: розклад оброблено")
                        self.logger.info(f"Database: {stats['total_records']} total records, {stats['last_24h_records']} in last 24h")
                        self.logger.info(f"Events: {stats['events_sent']} sent, {stats['events_pending']} pending")
                    elif status == "no_data":
                        self.logger.info("Моніторинг: успішно, статус: розклад відсутній")
                    elif status == "old_data":
                        self.logger.info("Моніторинг: успішно, статус: розклад застарілий")
                    else:
                        self.logger.info(f"Моніторинг: успішно, статус: {status}")
                else:
                    self.logger.error("Моніторинг: помилка, статус: технічна проблема")

                self.logger.info(f"Next check in {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)

            except KeyboardInterrupt:
                self.logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                self.logger.info(f"Retrying in {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)

    def cleanup_old_data(self, days_to_keep: Optional[int] = None) -> int:
        """Clean up old data"""
        days = days_to_keep or self.config.cleanup_days
        return self.database.cleanup_old_data(days)

    def get_database_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics"""
        return self.database.get_comprehensive_stats()

    def query_periods_by_date(self, date: str) -> List:
        """Query periods by specific date"""
        return self.database.query_periods_by_date(date)

    def export_data_to_csv(self, output_file: str = 'power_outages_export.csv') -> Optional[str]:
        """Export data to CSV file"""
        try:
            output_path = Path(output_file)
            self.database.export_to_csv(output_path)
            return str(output_path)
        except Exception as e:
            self.logger.error(f"Export error: {e}")
            return None

    def get_event_summary(self) -> Dict[str, Any]:
        """Get summary of event processing status"""
        stats = self.database.get_comprehensive_stats()

        return {
            'total_events': stats['total_records'],
            'events_sent': stats['events_sent'],
            'events_pending': stats['events_pending'],
            'events_by_state': stats['by_state'],
            'last_24h_activity': stats['last_24h_records']
        }
