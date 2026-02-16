import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import re
import json
import sqlite3
import uuid
from datetime import datetime, timedelta
import os
import logging
import time
import sys
import pytz

# Fix Windows console for Ukrainian text
if sys.platform.startswith('win'):
    try:
        os.system('chcp 65001 >nul 2>&1')
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

def parse_group_input(console_input, json_file):
    # Priority: console input > json file > None
    group_codes = None
    if console_input:
        group_codes = [g.strip() for g in console_input.split(',') if g.strip()]
    elif json_file and os.path.exists(json_file):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and "group" in data and isinstance(data["group"], list):
                    group_codes = [str(g).strip() for g in data["group"] if str(g).strip()]
        except Exception as e:
            print(f"[ERROR] Could not read group codes from {json_file}: {e}")
    return group_codes

class PowerOutageDatabase:
    def __init__(self, db_file='power_outages.db'):
        self.db_file = db_file
        self.logger = logging.getLogger(__name__)
        self.init_database()
    
    def init_database(self):
        """Initialize database with data preservation and schema upgrades"""
        db_exists = os.path.exists(self.db_file)
        if db_exists:
            self.logger.info(f"[OK] Using existing database: {self.db_file}")
            self.verify_and_upgrade_schema()
        else:
            self.logger.info(f"[OK] Creating new database: {self.db_file}")
            self.create_fresh_database()
    
    def create_fresh_database(self):
        """Create database with optimized schema"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                CREATE TABLE periods (
                    recid TEXT PRIMARY KEY,
                    insert_ts TEXT NOT NULL,
                    date TEXT NOT NULL,
                    last_update TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    period_from TEXT,
                    period_to TEXT,
                    calendar_event_id TEXT,
                    calendar_event_uid TEXT,
                    calendar_event_state TEXT DEFAULT 'pending',
                    calendar_event_ts TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_periods_date ON periods(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_periods_name ON periods(name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_periods_state ON periods(calendar_event_state)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_periods_last_update ON periods(last_update)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_periods_date_name ON periods(date, name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_periods_uid ON periods(calendar_event_uid)')
            cursor.execute('''
                CREATE TABLE metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute("INSERT INTO metadata (key, value) VALUES ('schema_version', '3.0')")
            cursor.execute("INSERT INTO metadata (key, value) VALUES ('created_at', ?)", (datetime.now().isoformat(),))
            conn.commit()
            self.logger.info("[OK] Fresh database created with enhanced schema")
        except Exception as e:
            self.logger.error(f"Error creating fresh database: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def verify_and_upgrade_schema(self):
        """Verify and upgrade existing schema without data loss"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='periods'")
            if not cursor.fetchone():
                self.logger.info("Periods table not found, creating...")
                self.create_fresh_database()
                return
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metadata'")
            if not cursor.fetchone():
                self.logger.info("Adding metadata table...")
                cursor.execute('''
                    CREATE TABLE metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute("INSERT INTO metadata (key, value) VALUES ('schema_version', '3.0')")
                cursor.execute("INSERT INTO metadata (key, value) VALUES ('upgraded_at', ?)", (datetime.now().isoformat(),))
            cursor.execute("PRAGMA table_info(periods)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            required_columns = {
                'calendar_event_uid': 'TEXT',
                'created_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TEXT DEFAULT CURRENT_TIMESTAMP'
            }
            for col_name, col_def in required_columns.items():
                if col_name not in existing_columns:
                    self.logger.info(f"Adding column: {col_name}")
                    cursor.execute(f"ALTER TABLE periods ADD COLUMN {col_name} {col_def}")
            cursor.execute("SELECT recid FROM periods WHERE calendar_event_uid IS NULL OR calendar_event_uid = ''")
            records_without_uid = cursor.fetchall()
            for record in records_without_uid:
                new_uid = f"{uuid.uuid4()}@power-monitor"
                cursor.execute("UPDATE periods SET calendar_event_uid = ? WHERE recid = ?", (new_uid, record[0]))
            if records_without_uid:
                self.logger.info(f"Generated UIDs for {len(records_without_uid)} existing records")
            required_indexes = [
                'CREATE INDEX IF NOT EXISTS idx_periods_date ON periods(date)',
                'CREATE INDEX IF NOT EXISTS idx_periods_name ON periods(name)',
                'CREATE INDEX IF NOT EXISTS idx_periods_state ON periods(calendar_event_state)',
                'CREATE INDEX IF NOT EXISTS idx_periods_last_update ON periods(last_update)',
                'CREATE INDEX IF NOT EXISTS idx_periods_date_name ON periods(date, name)',
                'CREATE INDEX IF NOT EXISTS idx_periods_uid ON periods(calendar_event_uid)'
            ]
            for idx_sql in required_indexes:
                cursor.execute(idx_sql)
            conn.commit()
            self.logger.info("[OK] Database schema verified and upgraded")
        except Exception as e:
            self.logger.error(f"Schema upgrade error: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_comprehensive_stats(self):
        """Get comprehensive database statistics with safe error handling"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        stats = {
            'total_records': 0,
            'unique_dates': 0,
            'unique_groups': 0,
            'by_state': {},
            'date_range': {'from': None, 'to': None},
            'last_24h_records': 0,
            'by_status': {},
            'latest_update': None,
            'latest_insert': None
        }
        try:
            cursor.execute("SELECT COUNT(*) FROM periods")
            total_count = cursor.fetchone()
            if total_count and total_count[0] > 0:
                stats['total_records'] = total_count[0]
                cursor.execute("SELECT COUNT(DISTINCT date) FROM periods")
                unique_dates = cursor.fetchone()
                stats['unique_dates'] = unique_dates[0] if unique_dates else 0
                cursor.execute("SELECT COUNT(DISTINCT name) FROM periods")
                unique_groups = cursor.fetchone()
                stats['unique_groups'] = unique_groups[0] if unique_groups else 0
                cursor.execute("""
                    SELECT calendar_event_state, COUNT(*) 
                    FROM periods 
                    GROUP BY calendar_event_state
                """)
                stats['by_state'] = dict(cursor.fetchall())
                cursor.execute("SELECT MIN(date), MAX(date) FROM periods WHERE date IS NOT NULL AND date != ''")
                date_range = cursor.fetchone()
                if date_range and date_range[0]:
                    stats['date_range'] = {'from': date_range[0], 'to': date_range[1]}
                cursor.execute("""
                    SELECT COUNT(*) FROM periods 
                    WHERE datetime(insert_ts) > datetime('now', '-24 hours')
                """)
                recent = cursor.fetchone()
                stats['last_24h_records'] = recent[0] if recent else 0
                cursor.execute("""
                    SELECT status, COUNT(*) 
                    FROM periods 
                    GROUP BY status
                """)
                stats['by_status'] = dict(cursor.fetchall())
                cursor.execute("""
                    SELECT MAX(last_update), MAX(insert_ts) 
                    FROM periods
                """)
                latest_info = cursor.fetchone()
                if latest_info:
                    stats['latest_update'] = latest_info[0]
                    stats['latest_insert'] = latest_info[1]
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
        finally:
            conn.close()
        return stats
    
    def cleanup_old_data(self, days_to_keep=30):
        """Clean up old data while preserving recent records"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                DELETE FROM periods 
                WHERE datetime(insert_ts) < datetime('now', '-{} days')
            """.format(days_to_keep))
            deleted_count = cursor.rowcount
            conn.commit()
            self.logger.info(f"[OK] Cleaned up {deleted_count} old records (kept last {days_to_keep} days)")
            return deleted_count
        except Exception as e:
            self.logger.error(f"Error cleaning up data: {e}")
            return 0
        finally:
            conn.close()

class PowerOutageMonitor:
    def __init__(self, url='https://poweron.loe.lviv.ua/', db_file='power_outages.db', json_dir='json_data', events_dir='calendar_events', group_filter=None):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        file_handler = logging.FileHandler('power_monitor.log', encoding='utf-8')
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        try:
            logger.addHandler(console_handler)
        except:
            print("Console logging disabled due to encoding issues. Check power_monitor.log for details.")
        self.logger = logger
        self.url = url
        self.db = PowerOutageDatabase(db_file)
        self.json_dir = json_dir
        self.events_dir = events_dir
        self.ukraine_tz = pytz.timezone('Europe/Kiev')
        self.group_filter = set(group_filter) if group_filter else None
        for directory in [self.json_dir, self.events_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
        self.show_startup_info()

    def get_ukraine_current_date(self):
        current_datetime_ukraine = datetime.now(self.ukraine_tz)
        return current_datetime_ukraine.date()

    def get_ukraine_current_date_str(self):
        return self.get_ukraine_current_date().strftime('%d.%m.%Y')

    def parse_ukraine_datetime(self, date_str, time_str):
        try:
            naive_dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
            ukraine_dt = self.ukraine_tz.localize(naive_dt)
            return ukraine_dt
        except ValueError as e:
            self.logger.warning(f"Error parsing Ukraine datetime '{date_str} {time_str}': {e}")
            return datetime.now(self.ukraine_tz)

    def show_startup_info(self):
        stats = self.db.get_comprehensive_stats()
        self.logger.info("=" * 60)
        self.logger.info("POWER OUTAGE MONITOR - STARTUP INFORMATION")
        self.logger.info("=" * 60)
        if self.group_filter:
            self.logger.info(f"Groups filter applied: {sorted(self.group_filter)}")
        else:
            self.logger.info("Executed without groups filter")        
        self.logger.info(f"Database: {self.db.db_file}")
        self.logger.info(f"Ukraine current date: {self.get_ukraine_current_date_str()}")
        self.logger.info(f"Total records: {stats['total_records']}")
        self.logger.info(f"Unique dates: {stats['unique_dates']}")
        self.logger.info(f"Unique groups: {stats['unique_groups']}")
        self.logger.info(f"Date range: {stats['date_range']['from']} to {stats['date_range']['to']}")
        self.logger.info(f"Records in last 24h: {stats['last_24h_records']}")
        if stats['by_state']:
            self.logger.info("Records by calendar state:")
            for state, count in stats['by_state'].items():
                self.logger.info(f"  {state}: {count}")
        if stats['by_status']:
            self.logger.info("Records by power status:")
            for status, count in stats['by_status'].items():
                self.logger.info(f"  {status}: {count}")
        self.logger.info("=" * 60)
    
    def normalize_last_update(self, last_update_str):
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

    def parse_power_off_text(self, text):
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        result = {
            "date": None,
            "last_update": None,
            "groups": [],
            "date_found": False,
            "last_update_found": False
        }
        for line in lines:
            m = re.match(r"Графік погодинних відключень на (\d{2}\.\d{2}\.\d{4})", line)
            if m:
                result["date"] = m.group(1)
                result["date_found"] = True
            m = re.match(r"Інформація станом на (\d{2}:\d{2} \d{2}\.\d{2}\.\d{4})", line)
            if m:
                result["last_update"] = self.normalize_last_update(m.group(1))
                result["last_update_found"] = True
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

    def validate_schedule_data(self, parsed_data):
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

    def extract_dynamic_content(self):
        url = self.url
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        try:
            print("Starting browser...")
            driver = webdriver.Chrome(options=chrome_options)
            print(f"Loading: {url}")
            driver.get(url)
            print("Waiting for content to load...")
            time.sleep(5)
            selectors_to_try = [
                "div[class='power-off__text']"
            ]
            found_content = False
            parsed = None
            for selector in selectors_to_try:
                try:
                    print(f"Trying selector: {selector}")
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for i, element in enumerate(elements):
                        text = element.text.strip()
                        if text and len(text) > 50:
                            print(f"FOUND CONTENT with {selector} (element {i}):")
                            print(f'Text length: {len(text)} chars')
                            parsed = self.parse_power_off_text(text)
                            print(f"PARSED JSON: {parsed}")
                            found_content = True
                            break
                    if found_content:
                        break
                except Exception as e:
                    print(f"  Error with {selector}: {e}")
            if not found_content:
                print("No specific content found, getting all page text:")
                all_text = driver.find_element(By.TAG_NAME, "body").text
                parsed = self.parse_power_off_text(all_text)
                with open('selenium_all_content.txt', 'w', encoding='utf-8') as f:
                    f.write("All page content:\n")
                    f.write("=" * 60 + "\n")
                    f.write(all_text)
        except Exception as e:
            print(f"Error: {e}")
            parsed = None
        finally:
            try:
                driver.quit()
            except:
                pass
        return parsed

    def normalize_time(self, time_str):
        parts = time_str.split(':')
        hour = parts[0].zfill(2)
        minute = parts[1].zfill(2)
        return f"{hour}:{minute}"

    def parse_date_to_datetime(self, date_str):
        try:
            return datetime.strptime(date_str, "%d.%m.%Y")
        except ValueError:
            return datetime.now()

    def format_datetime_for_ics(self, dt):
        if dt.tzinfo is not None:
            utc_dt = dt.astimezone(pytz.UTC)
        else:
            utc_dt = dt
        return utc_dt.strftime("%Y%m%dT%H%M%SZ")

    def create_ics_content(self, event):
        if event['period_from'] and event['period_to']:
            start_time_ukraine = self.parse_ukraine_datetime(event['date'], event['period_from'])
            end_time_ukraine = self.parse_ukraine_datetime(event['date'], event['period_to'])
            if end_time_ukraine <= start_time_ukraine:
                end_time_ukraine += timedelta(days=1)
            dtstart = f"DTSTART:{self.format_datetime_for_ics(start_time_ukraine)}"
            dtend = f"DTEND:{self.format_datetime_for_ics(end_time_ukraine)}"
        else:
            event_date = self.parse_date_to_datetime(event['date'])
            dtstart = f"DTSTART;VALUE=DATE:{event_date.strftime('%Y%m%d')}"
            dtend = f"DTEND;VALUE=DATE:{(event_date + timedelta(days=1)).strftime('%Y%m%d')}"
        uid = event.get('calendar_event_uid', f"{uuid.uuid4()}@power-monitor")
        now_utc = datetime.now(pytz.UTC)
        dtstamp = f"DTSTAMP:{self.format_datetime_for_ics(now_utc)}"
        created = f"CREATED:{self.format_datetime_for_ics(now_utc)}"
        def escape_text(text):
            return text.replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')
        summary = escape_text(event['calendar_event_id'])
        description_parts = [
            f"Дата: {event['date']}",
            f"Група: {event['name']}",
            f"Статус: {event['status']}",
            f"Останнє оновлення: {event['last_update']}"
        ]
        if event['period_from'] and event['period_to']:
            description_parts.append(f"Період: {event['period_from']} - {event['period_to']} (час України)")
        description = escape_text(" | ".join(description_parts))
        if event['status'] == 'Електроенергії немає':
            categories = "POWER OUTAGE,UTILITY"
        else:
            categories = "POWER AVAILABLE,UTILITY"
        ics_content = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Power Monitor//Power Outage Monitor//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            dtstamp,
            created,
            dtstart,
            dtend,
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            f"CATEGORIES:{categories}",
            "STATUS:CONFIRMED",
            "TRANSP:OPAQUE",
            "END:VEVENT",
            "END:VCALENDAR"
        ]
        return "\r\n".join(ics_content)

    def stage2_store_json(self, data):
        self.logger.info("=== STAGE 2: Storing JSON ===")
        if not data:
            self.logger.error("No data to store")
            return None
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_power_outages.json"
        filepath = os.path.join(self.json_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"[OK] JSON stored: {filename}")
            return filepath
        except Exception as e:
            self.logger.error(f"[ERROR] JSON storage error: {e}")
            return None

    def stage3_database_operations(self, json_filepath):
        self.logger.info("=== STAGE 3: Database operations ===")
        if not json_filepath or not os.path.exists(json_filepath):
            self.logger.error("JSON file not found")
            return None
        try:
            with open(json_filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading JSON: {e}")
            return None
        conn = sqlite3.connect(self.db.db_file)
        cursor = conn.cursor()
        insert_ts = datetime.now().isoformat()
        inserted_count = 0
        try:
            for group in data['groups']:
                group_code = group['name'].split(' ')[1] if 'name' in group and ' ' in group['name'] else group.get('name')
                if self.group_filter and group_code not in self.group_filter:
                    continue
                recid = str(uuid.uuid4())
                calendar_event_uid = f"{uuid.uuid4()}@power-monitor"
                period_from = group.get('period', {}).get('from', '')
                period_to = group.get('period', {}).get('to', '')
                calendar_event_id = f"{data['date']}_{group['name']}-{group['status']}-{period_from}-{period_to}"
                cursor.execute('''
                    INSERT INTO periods (
                        recid, insert_ts, date, last_update, name, status, 
                        period_from, period_to, calendar_event_id, calendar_event_uid,
                        calendar_event_state, calendar_event_ts
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    recid, insert_ts, data['date'], data['last_update'],
                    group['name'], group['status'],
                    period_from, period_to, calendar_event_id, calendar_event_uid,
                    'pending', insert_ts
                ))
                inserted_count += 1
            conn.commit()
            self.logger.info(f"[OK] Inserted {inserted_count} new records")
            self.process_advanced_period_comparisons(cursor)
            conn.commit()
        except Exception as e:
            self.logger.error(f"Database operation error: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
        return self.generate_calendar_events_json()

    def process_advanced_period_comparisons(self, cursor):
        self.logger.info("Processing advanced period comparisons...")
        current_date_ukraine = self.get_ukraine_current_date_str()
        cursor.execute('''
            SELECT recid, last_update, name, status, period_from, period_to, calendar_event_id, calendar_event_uid, insert_ts
            FROM periods 
            WHERE date = ? 
            ORDER BY name, last_update DESC, insert_ts DESC
        ''', (current_date_ukraine,))
        all_records = cursor.fetchall()
        if not all_records:
            self.logger.info(f"No records found for current Ukraine date: {current_date_ukraine}")
            return
        groups_by_name = {}
        for record in all_records:
            recid, last_update, name, status, period_from, period_to, calendar_event_id, calendar_event_uid, insert_ts = record
            if name not in groups_by_name:
                groups_by_name[name] = []
            groups_by_name[name].append({
                'recid': recid,
                'last_update': last_update,
                'name': name,
                'status': status,
                'period_from': period_from,
                'period_to': period_to,
                'calendar_event_id': calendar_event_id,
                'calendar_event_uid': calendar_event_uid,
                'insert_ts': insert_ts
            })
        for name, group_records in groups_by_name.items():
            if not group_records:
                self.logger.warning(f"Empty group_records for {name}")
                continue
            group_records.sort(key=lambda x: (x['last_update'], x['insert_ts']), reverse=True)
            latest_record = group_records[0]
            if latest_record['status'] == 'Електроенергія є':
                for i, record in enumerate(group_records):
                    state = 'generated' if i == 0 else 'discarded'
                    self.update_calendar_event_state(cursor, record['recid'], state)
            else:
                self.process_period_intersections(cursor, group_records)

    def process_period_intersections(self, cursor, group_records):
        if not group_records:
            self.logger.warning("Empty group_records in process_period_intersections")
            return
        period_records = [r for r in group_records if r['period_from'] and r['period_to']]
        if not period_records:
            self.update_calendar_event_state(cursor, group_records[0]['recid'], 'generated')
            for record in group_records[1:]:
                self.update_calendar_event_state(cursor, record['recid'], 'discarded')
            return
        period_records.sort(key=lambda x: (x['last_update'], x['insert_ts']), reverse=True)
        if not period_records:
            self.logger.warning("No period_records after sorting")
            return
        latest_record = period_records[0]
        self.update_calendar_event_state(cursor, latest_record['recid'], 'generated')
        for older_record in period_records[1:]:
            if self.periods_intersect(latest_record, older_record):
                self.update_calendar_event_state(cursor, older_record['recid'], 'discarded')
            else:
                self.update_calendar_event_state(cursor, older_record['recid'], 'discarded')

    def periods_intersect(self, period1, period2):
        try:
            def time_to_minutes(time_str):
                if not time_str:
                    return 0
                hours, minutes = map(int, time_str.split(':'))
                return hours * 60 + minutes
            start1 = time_to_minutes(period1['period_from'])
            end1 = time_to_minutes(period1['period_to'])
            start2 = time_to_minutes(period2['period_from'])
            end2 = time_to_minutes(period2['period_to'])
            if end1 < start1:
                end1 += 24 * 60
            if end2 < start2:
                end2 += 24 * 60
            return not (end1 <= start2 or end2 <= start1)
        except Exception as e:
            self.logger.warning(f"Error checking period intersection: {e}")
            return False

    def update_calendar_event_state(self, cursor, recid, state):
        cursor.execute('''
            UPDATE periods 
            SET calendar_event_state = ?, calendar_event_ts = ?, updated_at = CURRENT_TIMESTAMP
            WHERE recid = ?
        ''', (state, datetime.now().isoformat(), recid))

    def generate_calendar_events_json(self):
        self.logger.info("Generating calendar events JSON...")
        conn = sqlite3.connect(self.db.db_file)
        cursor = conn.cursor()
        if self.group_filter:
            placeholders = ','.join('?' for _ in self.group_filter)
            cursor.execute(f'''
                SELECT calendar_event_id, calendar_event_uid, date, name, status, period_from, period_to, last_update
                FROM periods 
                WHERE calendar_event_state = 'generated' AND substr(name, 8) IN ({placeholders})
                ORDER BY calendar_event_ts DESC
            ''', tuple(self.group_filter))
        else:
            cursor.execute('''
                SELECT calendar_event_id, calendar_event_uid, date, name, status, period_from, period_to, last_update
                FROM periods 
                WHERE calendar_event_state = 'generated'
                ORDER BY calendar_event_ts DESC
            ''')
        create_records = cursor.fetchall()
        if self.group_filter:
            placeholders = ','.join('?' for _ in self.group_filter)
            cursor.execute(f'''
                SELECT DISTINCT calendar_event_id, calendar_event_uid
                FROM periods 
                WHERE calendar_event_state = 'discarded' AND substr(name, 8) IN ({placeholders})
                ORDER BY calendar_event_ts DESC
            ''', tuple(self.group_filter))
        else:
            cursor.execute('''
                SELECT DISTINCT calendar_event_id, calendar_event_uid
                FROM periods 
                WHERE calendar_event_state = 'discarded'
                ORDER BY calendar_event_ts DESC
            ''')
        delete_records = cursor.fetchall()
        conn.close()
        events_to_create = []
        for record in create_records:
            calendar_event_id, calendar_event_uid, date, name, status, period_from, period_to, last_update = record
            events_to_create.append({
                'calendar_event_id': calendar_event_id,
                'calendar_event_uid': calendar_event_uid,
                'date': date,
                'name': name,
                'status': status,
                'period_from': period_from,
                'period_to': period_to,
                'last_update': last_update
            })
        events_to_delete = []
        for record in delete_records:
            events_to_delete.append({
                'calendar_event_id': record[0],
                'calendar_event_uid': record[1]
            })
        result = {
            'events_to_create': events_to_create,
            'events_to_delete': events_to_delete,
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'create_count': len(events_to_create),
                'delete_count': len(events_to_delete)
            }
        }
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_calendar_events.json"
        filepath = os.path.join(self.events_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            self.logger.info(f"[OK] Calendar events JSON created: {filename}")
            self.logger.info(f"  Events to create: {len(events_to_create)}")
            self.logger.info(f"  Events to delete: {len(events_to_delete)}")
            return filepath
        except Exception as e:
            self.logger.error(f"Error creating calendar events JSON: {e}")
            return None

    def stage4_generate_calendar_files(self, events_json_filepath):
        self.logger.info("=== STAGE 4: Generating ICS calendar files ===")
        if not events_json_filepath or not os.path.exists(events_json_filepath):
            self.logger.error("Events JSON file not found")
            return
        try:
            with open(events_json_filepath, 'r', encoding='utf-8') as f:
                events_data = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading events JSON: {e}")
            return
        events_to_create = events_data.get('events_to_create', [])
        events_to_delete = events_data.get('events_to_delete', [])
        if not events_to_create and not events_to_delete:
            self.logger.info("No events to create or delete - skipping calendar file generation")
            return
        if events_to_delete:
            self.create_cancellation_ics_file(events_to_delete)
        if events_to_create:
            self.generate_ics_files(events_to_create)
        self.generate_deletion_summary([event['calendar_event_id'] for event in events_to_delete])

    def create_cancellation_ics_file(self, events_to_delete):
        if not events_to_delete:
            return None
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_cancel_events.ics"
        filepath = os.path.join(self.events_dir, filename)
        try:
            ics_lines = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//Power Monitor//Power Outage Monitor//EN",
                "CALSCALE:GREGORIAN",
                "METHOD:CANCEL"
            ]
            for event in events_to_delete:
                uid = event.get('calendar_event_uid', f"{event['calendar_event_id']}@power-monitor")
                now_utc = datetime.now(pytz.UTC)
                dtstamp = f"DTSTAMP:{self.format_datetime_for_ics(now_utc)}"
                event_lines = [
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    dtstamp,
                    f"SUMMARY:{event['calendar_event_id']}",
                    "STATUS:CANCELLED",
                    "END:VEVENT"
                ]
                ics_lines.extend(event_lines)
            ics_lines.append("END:VCALENDAR")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("\r\n".join(ics_lines))
            self.logger.info(f"[OK] Cancellation ICS file created: {filename} ({len(events_to_delete)} events)")
            return filepath
        except Exception as e:
            self.logger.error(f"Error creating cancellation ICS file: {e}")
            return None

    def generate_deletion_summary(self, events_to_delete):
        if not events_to_delete:
            return
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_manual_delete.txt"
        filepath = os.path.join(self.events_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("GOOGLE CALENDAR - MANUAL DELETION (BACKUP OPTION)\n")
                f.write("="*50 + "\n\n")
                f.write(f"Generated: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
                f.write(f"Total events to delete: {len(events_to_delete)}\n\n")
                f.write("Event IDs to search and delete manually:\n")
                f.write("-" * 50 + "\n")
                for i, event_id in enumerate(events_to_delete, 1):
                    f.write(f"{i:3d}. {event_id}\n")
                f.write(f"\n{'='*50}\n")
                f.write("Instructions:\n")
                f.write("1. Use cancellation ICS file first (recommended)\n")
                f.write("2. If ICS cancellation fails, use manual deletion:\n")
                f.write("   - Open Google Calendar\n")
                f.write("   - Search for each event ID\n")
                f.write("   - Delete found events manually\n")
            self.logger.info(f"[OK] Manual deletion summary created: {filename}")
        except Exception as e:
            self.logger.error(f"Error creating manual deletion summary: {e}")

    def generate_ics_files(self, events_to_create):
        if not events_to_create:
            self.logger.info("No events to create")
            return
        created_files = []
        for event in events_to_create:
            filepath = self.create_single_ics_file(event)
            if filepath:
                created_files.append(filepath)
        combined_filepath = self.create_combined_ics_file(events_to_create)
        if combined_filepath:
            created_files.append(combined_filepath)
        self.logger.info(f"[OK] Created {len(created_files)} ICS files")
        self.logger.info(f"  Individual files: {len(events_to_create)}")
        self.logger.info(f"  Combined file: 1")

    def create_single_ics_file(self, event):
        try:
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', event['calendar_event_id'])
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{safe_title}.ics"
            filepath = os.path.join(self.events_dir, filename)
            ics_content = self.create_ics_content(event)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(ics_content)
            return filepath
        except Exception as e:
            self.logger.error(f"Error creating ICS file for event {event.get('calendar_event_id', 'unknown')}: {e}")
            return None

    def create_combined_ics_file(self, events_to_create):
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_all_power_events.ics"
            filepath = os.path.join(self.events_dir, filename)
            ics_lines = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//Power Monitor//Power Outage Monitor//EN",
                "CALSCALE:GREGORIAN",
                "METHOD:PUBLISH"
            ]
            for event in events_to_create:
                if event['period_from'] and event['period_to']:
                    start_time_ukraine = self.parse_ukraine_datetime(event['date'], event['period_from'])
                    end_time_ukraine = self.parse_ukraine_datetime(event['date'], event['period_to'])
                    if end_time_ukraine <= start_time_ukraine:
                        end_time_ukraine += timedelta(days=1)
                    dtstart = f"DTSTART:{self.format_datetime_for_ics(start_time_ukraine)}"
                    dtend = f"DTEND:{self.format_datetime_for_ics(end_time_ukraine)}"
                else:
                    event_date = self.parse_date_to_datetime(event['date'])
                    dtstart = f"DTSTART;VALUE=DATE:{event_date.strftime('%Y%m%d')}"
                    dtend = f"DTEND;VALUE=DATE:{(event_date + timedelta(days=1)).strftime('%Y%m%d')}"
                uid = event.get('calendar_event_uid', f"{uuid.uuid4()}@power-monitor")
                now_utc = datetime.now(pytz.UTC)
                dtstamp = f"DTSTAMP:{self.format_datetime_for_ics(now_utc)}"
                created = f"CREATED:{self.format_datetime_for_ics(now_utc)}"
                def escape_text(text):
                    return text.replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')
                summary = escape_text(event['calendar_event_id'])
                description_parts = [
                    f"Дата: {event['date']}",
                    f"Група: {event['name']}",
                    f"Статус: {event['status']}",
                    f"Останнє оновлення: {event['last_update']}"
                ]
                if event['period_from'] and event['period_to']:
                    description_parts.append(f"Період: {event['period_from']} - {event['period_to']} (час України)")
                description = escape_text(" | ".join(description_parts))
                if event['status'] == 'Електроенергії немає':
                    categories = "POWER OUTAGE,UTILITY"
                else:
                    categories = "POWER AVAILABLE,UTILITY"
                event_lines = [
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    dtstamp,
                    created,
                    dtstart,
                    dtend,
                    f"SUMMARY:{summary}",
                    f"DESCRIPTION:{description}",
                    f"CATEGORIES:{categories}",
                    "STATUS:CONFIRMED",
                    "TRANSP:OPAQUE",
                    "END:VEVENT"
                ]
                ics_lines.extend(event_lines)
            ics_lines.append("END:VCALENDAR")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("\r\n".join(ics_lines))
            self.logger.info(f"[OK] Combined ICS file created: {filename} ({len(events_to_create)} events)")
            return filepath
        except Exception as e:
            self.logger.error(f"Error creating combined ICS file: {e}")
            return None

    def run_full_process(self):
        self.logger.info("Starting complete power outage monitoring process")
        try:
            json_data = self.extract_dynamic_content()
            is_valid, status_code, status_message = self.validate_schedule_data(json_data)
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
            json_filepath = self.stage2_store_json(json_data)
            if not json_filepath:
                self.logger.error("Stage 2 failed - JSON storage")
                return False, "error"
            events_json_filepath = self.stage3_database_operations(json_filepath)
            if not events_json_filepath:
                self.logger.error("Stage 3 failed - database operations")
                return False, "error"
            self.stage4_generate_calendar_files(events_json_filepath)
            self.logger.info("[OK] Complete process finished successfully")
            return True, "success"
        except Exception as e:
            self.logger.error(f"Process error: {e}")
            return False, "error"

    def run_continuous_monitoring(self, interval_minutes=5):
        self.logger.info(f"Starting continuous monitoring (every {interval_minutes} minutes)")
        self.logger.info("Press Ctrl+C to stop")
        while True:
            try:
                success, status = self.run_full_process()
                if success:
                    stats = self.db.get_comprehensive_stats()
                    if status == "success":
                        self.logger.info(f"Моніторинг: успішно, статус: розклад оброблено")
                        self.logger.info(f"Database: {stats['total_records']} total records, {stats['last_24h_records']} in last 24h")
                    elif status == "no_data":
                        self.logger.info(f"Моніторинг: успішно, статус: розклад відсутній")
                    elif status == "old_data":
                        self.logger.info(f"Моніторинг: успішно, статус: розклад застарілий")
                    else:
                        self.logger.info(f"Моніторинг: успішно, статус: {status}")
                else:
                    self.logger.error(f"Моніторинг: помилка, статус: технічна проблема")
                self.logger.info(f"Next check in {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                self.logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                self.logger.info(f"Retrying in {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)

    def cleanup_old_data(self, days_to_keep=30):
        return self.db.cleanup_old_data(days_to_keep)

    def get_database_stats(self):
        return self.db.get_comprehensive_stats()

    def query_periods_by_date(self, date):
        conn = sqlite3.connect(self.db.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT name, status, period_from, period_to, calendar_event_state, 
                   last_update, calendar_event_id
            FROM periods 
            WHERE date = ?
            ORDER BY name, last_update DESC
        ''', (date,))
        results = cursor.fetchall()
        conn.close()
        return results

    def export_data_to_csv(self, output_file='power_outages_export.csv'):
        import csv
        conn = sqlite3.connect(self.db.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT date, name, status, period_from, period_to, 
                   calendar_event_state, last_update, insert_ts
            FROM periods 
            ORDER BY date DESC, name
        ''')
        results = cursor.fetchall()
        conn.close()
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Date', 'Group', 'Status', 'From', 'To', 'Calendar State', 'Last Update', 'Insert Time'])
                writer.writerows(results)
            self.logger.info(f"[OK] Data exported to {output_file} ({len(results)} records)")
            return output_file
        except Exception as e:
            self.logger.error(f"Export error: {e}")
            return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Power Outage Monitor with group filtering")
    parser.add_argument('--groups', type=str, help="Comma-separated list of group codes (e.g. 1.1,2.1,3.2)")
    parser.add_argument('--groups-file', type=str, default='groups.json', help="JSON file with group codes")
    args = parser.parse_args()

    group_codes = parse_group_input(args.groups, args.groups_file)

    print("="*80)
    print("POWER OUTAGE MONITOR - ICS CALENDAR SUPPORT WITH UKRAINE TIMEZONE")
    print("="*80)
    print("\n1. STARTUP & DATABASE CHECK")
    print("-" * 40)
    print("The script will check if the database exists.")
    print("If it exists, it will be used and upgraded if needed (no data loss).")
    print("If it does not exist, a new database will be created.")
    print("Group filter will be determined from console or JSON file (if provided).")
    print("-" * 40)    
    print("\n2. INITIALIZING MONITOR")
    print("-" * 40)
    monitor = PowerOutageMonitor(
        url='https://poweron.loe.lviv.ua/',
        db_file='power_outages.db',
        json_dir='json_data',
        events_dir='calendar_events',
        group_filter=group_codes
    )
    print("\n3. RUNNING SINGLE MONITORING CYCLE")
    print("-" * 40)
    success, status = monitor.run_full_process()
    if success:
        print("\n4. PROCESS RESULTS")
        print("-" * 40)
        if status == "success":
            print("[OK] Process completed successfully!")
            stats = monitor.get_database_stats()
            print(f"\nDatabase Statistics:")
            print(f"  Total records: {stats['total_records']}")
            print(f"  Unique dates: {stats['unique_dates']}")
            print(f"  Unique groups: {stats['unique_groups']}")
            print(f"  Records in last 24h: {stats['last_24h_records']}")
            today = monitor.get_ukraine_current_date_str()
            today_data = monitor.query_periods_by_date(today)
            if today_data:
                print(f"\nToday's periods ({today}):")
                for record in today_data:
                    name, status_text, period_from, period_to, state, last_update, event_id = record
                    time_info = f"({period_from}-{period_to})" if period_from and period_to else "(all day)"
                    try:
                        print(f"  {name}: {status_text} {time_info} [{state}]")
                    except UnicodeEncodeError:
                        print(f"  [Ukrainian group]: [Ukrainian status] {time_info} [{state}]")
            print(f"\nFiles created in:")
            print(f"  JSON data: {monitor.json_dir}/")
            print(f"  ICS calendar files: {monitor.events_dir}/")
            print(f"  Log file: power_monitor.log")
            csv_file = monitor.export_data_to_csv()
            if csv_file:
                print(f"  CSV export: {csv_file}")
            print(f"\nICS Files Usage:")
            print(f"  - Individual .ics files: Import each file separately")
            print(f"  - Combined .ics file: Import all events at once")
            print(f"  - Cancellation .ics file: Import to remove old events")
            print(f"  - Manual deletion .txt: Backup option for manual removal")
            print(f"  - All times are in Ukraine timezone (Europe/Kiev)")
        elif status in ["no_data", "old_data", "invalid_date"]:
            print(f"[INFO] Process completed - {status}")
            print("No calendar files were generated due to data status")
    else:
        print("\n[ERROR] Process failed - check the logs above")
    print("\n5. CONTINUOUS MONITORING OPTIONS")
    print("-" * 40)
    print("To run continuous monitoring, use one of these commands:")
    print("  monitor.run_continuous_monitoring(5)   # Every 5 minutes")
    print("  monitor.run_continuous_monitoring(15)  # Every 15 minutes")
    print("  monitor.run_continuous_monitoring(60)  # Every hour")
    
print("\n6. RUNNING WITH GROUP FILTERS")
print("-" * 40)
print("You can filter monitoring by specific group codes using:")
print("  --groups 1.1,2.1,3.2")
print("or by providing a JSON file (default: groups.json) with:")
print('  {"group": ["1.1", "2.1"]}')
print("Examples:")
print("  python script.py --groups 1.1,2.1")
print("  python script.py --groups-file mygroups.json")
print("If neither is provided, all groups from the website will be processed.")
print("="*80)
print("MONITORING SETUP COMPLETE - ICS CALENDAR SUPPORT WITH UKRAINE TIMEZONE")
print("Check calendar_events/ folder for .ics files to import")
print("All calendar events use Ukraine timezone (Europe/Kiev) with DST support")
print("="*80)