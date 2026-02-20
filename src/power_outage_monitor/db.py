"""Database operations for Power Outage Monitor with enhanced event tracking."""

import sqlite3
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
from dataclasses import dataclass
import pytz


@dataclass
class OutagePeriod:
    """Represents a power outage period with enhanced tracking."""
    recid: Optional[str] = None
    insert_ts: Optional[str] = None
    date: str = ""
    last_update: str = ""
    name: str = ""
    status: str = ""
    period_from: Optional[str] = None
    period_to: Optional[str] = None
    calendar_event_id: Optional[str] = None
    calendar_event_uid: Optional[str] = None
    calendar_event_state: str = "pending"  # pending, generated, discarded, sent, cancelled
    calendar_event_ts: Optional[str] = None
    event_sent: bool = False  # Track if ICS event was actually sent/generated
    event_hash: Optional[str] = None  # Hash for duplicate detection
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self):
        if self.recid is None:
            self.recid = str(uuid.uuid4())
        if self.insert_ts is None:
            self.insert_ts = datetime.now().isoformat()
        if self.calendar_event_uid is None:
            self.calendar_event_uid = f"{uuid.uuid4()}@power-monitor"
        if self.calendar_event_id is None and self.date and self.name and self.status:
            period_from = self.period_from or ""
            period_to = self.period_to or ""
            self.calendar_event_id = f"{self.date}_{self.name}-{self.status}-{period_from}-{period_to}"
        if self.event_hash is None:
            self.event_hash = self._generate_event_hash()

    def _generate_event_hash(self) -> str:
        """Generate hash for duplicate detection."""
        hash_string = f"{self.date}|{self.name}|{self.status}|{self.period_from or ''}|{self.period_to or ''}"
        return hashlib.md5(hash_string.encode()).hexdigest()


class PowerOutageDatabase:
    """Handles all database operations for power outage data with enhanced event tracking."""

    def __init__(self, db_path: Path, logger: logging.Logger):
        self.db_path = db_path
        self.logger = logger
        self.ukraine_tz = pytz.timezone('Europe/Kiev')
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database with data preservation and schema upgrades"""
        db_exists = self.db_path.exists()
        if db_exists:
            self.logger.info(f"[OK] Using existing database: {self.db_path}")
            self._verify_and_upgrade_schema()
        else:
            self.logger.info(f"[OK] Creating new database: {self.db_path}")
            self._create_fresh_database()

    def _create_fresh_database(self) -> None:
        """Create database with enhanced schema for event tracking."""
        with sqlite3.connect(self.db_path) as conn:
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
                        event_sent BOOLEAN DEFAULT 0,
                        event_hash TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Enhanced indexes
                indexes = [
                    'CREATE INDEX IF NOT EXISTS idx_periods_date ON periods(date)',
                    'CREATE INDEX IF NOT EXISTS idx_periods_name ON periods(name)',
                    'CREATE INDEX IF NOT EXISTS idx_periods_state ON periods(calendar_event_state)',
                    'CREATE INDEX IF NOT EXISTS idx_periods_last_update ON periods(last_update)',
                    'CREATE INDEX IF NOT EXISTS idx_periods_date_name ON periods(date, name)',
                    'CREATE INDEX IF NOT EXISTS idx_periods_uid ON periods(calendar_event_uid)',
                    'CREATE INDEX IF NOT EXISTS idx_periods_hash ON periods(event_hash)',
                    'CREATE INDEX IF NOT EXISTS idx_periods_sent ON periods(event_sent)',
                    'CREATE INDEX IF NOT EXISTS idx_periods_unique_event ON periods(event_hash, calendar_event_state)'
                ]

                for idx_sql in indexes:
                    cursor.execute(idx_sql)

                cursor.execute('''
                    CREATE TABLE metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                cursor.execute("INSERT INTO metadata (key, value) VALUES ('schema_version', '4.0')")
                cursor.execute("INSERT INTO metadata (key, value) VALUES ('created_at', ?)", (datetime.now().isoformat(),))

                conn.commit()
                self.logger.info("[OK] Fresh database created with enhanced event tracking schema")

            except Exception as e:
                self.logger.error(f"Error creating fresh database: {e}")
                conn.rollback()
                raise

    def _verify_and_upgrade_schema(self) -> None:
        """Verify and upgrade existing schema for event tracking."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                # Check if periods table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='periods'")
                if not cursor.fetchone():
                    self.logger.info("Periods table not found, creating...")
                    self._create_fresh_database()
                    return

                # Check if metadata table exists
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
                    cursor.execute("INSERT INTO metadata (key, value) VALUES ('schema_version', '4.0')")
                    cursor.execute("INSERT INTO metadata (key, value) VALUES ('upgraded_at', ?)", (datetime.now().isoformat(),))

                # Check existing columns
                cursor.execute("PRAGMA table_info(periods)")
                existing_columns = {row[1] for row in cursor.fetchall()}

                # Add new columns for event tracking
                new_columns = {
                    'event_sent': 'BOOLEAN DEFAULT 0',
                    'event_hash': 'TEXT',
                    'calendar_event_uid': 'TEXT',
                    'created_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
                    'updated_at': 'TEXT DEFAULT CURRENT_TIMESTAMP'
                }

                for col_name, col_def in new_columns.items():
                    if col_name not in existing_columns:
                        self.logger.info(f"Adding column: {col_name}")
                        cursor.execute(f"ALTER TABLE periods ADD COLUMN {col_name} {col_def}")

                # Generate missing UIDs and hashes
                cursor.execute("SELECT recid, date, name, status, period_from, period_to FROM periods WHERE calendar_event_uid IS NULL OR calendar_event_uid = ''")
                records_without_uid = cursor.fetchall()

                for record in records_without_uid:
                    recid, date, name, status, period_from, period_to = record
                    new_uid = f"{uuid.uuid4()}@power-monitor"

                    # Generate hash
                    hash_string = f"{date}|{name}|{status}|{period_from or ''}|{period_to or ''}"
                    event_hash = hashlib.md5(hash_string.encode()).hexdigest()

                    cursor.execute("UPDATE periods SET calendar_event_uid = ?, event_hash = ? WHERE recid = ?", (new_uid, event_hash, recid))

                if records_without_uid:
                    self.logger.info(f"Generated UIDs and hashes for {len(records_without_uid)} existing records")

                # Create new indexes
                new_indexes = [
                    'CREATE INDEX IF NOT EXISTS idx_periods_hash ON periods(event_hash)',
                    'CREATE INDEX IF NOT EXISTS idx_periods_sent ON periods(event_sent)',
                    'CREATE INDEX IF NOT EXISTS idx_periods_uid ON periods(calendar_event_uid)'
                ]

                for idx_sql in new_indexes:
                    cursor.execute(idx_sql)

                conn.commit()
                self.logger.info("[OK] Database schema upgraded for event tracking")

            except Exception as e:
                self.logger.error(f"Schema upgrade error: {e}")
                conn.rollback()
                raise

    def get_ukraine_current_date(self) -> datetime.date:
        """Get current date in Ukraine timezone"""
        current_datetime_ukraine = datetime.now(self.ukraine_tz)
        return current_datetime_ukraine.date()

    def get_ukraine_current_date_str(self) -> str:
        """Get current date in Ukraine timezone as string"""
        return self.get_ukraine_current_date().strftime('%d.%m.%Y')

    def insert_period(self, period: OutagePeriod) -> str:
        """Insert a new outage period and return its recid."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO periods (
                    recid, insert_ts, date, last_update, name, status,
                    period_from, period_to, calendar_event_id, calendar_event_uid,
                    calendar_event_state, calendar_event_ts, event_sent, event_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                period.recid, period.insert_ts, period.date, period.last_update,
                period.name, period.status, period.period_from, period.period_to,
                period.calendar_event_id, period.calendar_event_uid,
                period.calendar_event_state, period.calendar_event_ts,
                period.event_sent, period.event_hash,
                period.created_at, period.updated_at
            ))

            conn.commit()
            self.logger.debug(f"Inserted period {period.recid} for {period.name}")
            return period.recid

    def update_calendar_event_state(self, recid: str, state: str) -> None:
        """Update the calendar event state of a period."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE periods
                SET calendar_event_state = ?, calendar_event_ts = ?, updated_at = CURRENT_TIMESTAMP
                WHERE recid = ?
            ''', (state, datetime.now().isoformat(), recid))
            conn.commit()
            self.logger.debug(f"Updated period {recid} state to {state}")

    def get_periods_by_name_and_date(self, name: str, date: str) -> List[OutagePeriod]:
        """Get all periods for a specific name and date, ordered by last_update DESC, insert_ts DESC."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM periods
                WHERE name = ? AND date >= ?
                ORDER BY last_update DESC, insert_ts DESC
            ''', (name, date))

            periods = []
            for row in cursor.fetchall():
                period = self._row_to_period(row)
                periods.append(period)

            return periods

    def check_identical_event_exists(self, period: OutagePeriod) -> Optional[OutagePeriod]:
        """Check if an identical event already exists and was sent."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM periods
                WHERE event_hash = ? AND calendar_event_state = 'generated' AND event_sent = 1
                ORDER BY insert_ts DESC
                LIMIT 1
            ''', (period.event_hash,))

            row = cursor.fetchone()
            if row:
                existing_period = self._row_to_period(row)
                self.logger.debug(f"Found identical event already sent: {existing_period.calendar_event_id}")
                return existing_period

            return None

    def find_overlapping_events(self, new_period: OutagePeriod) -> List[OutagePeriod]:
        """Find events that overlap with the new period."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get all generated events for the same group and date
            cursor = conn.execute('''
                SELECT * FROM periods
                WHERE name = ? AND date = ? AND calendar_event_state = 'generated'
                AND recid != ?
                ORDER BY insert_ts DESC
            ''', (new_period.name, new_period.date, new_period.recid or ''))

            overlapping = []

            for row in cursor.fetchall():
                existing_period = self._row_to_period(row)

                # Check for overlap
                if self._periods_overlap(new_period, existing_period):
                    overlapping.append(existing_period)
                    self.logger.debug(f"Found overlapping event: {existing_period.calendar_event_id}")

            return overlapping

    def _periods_overlap(self, period1: OutagePeriod, period2: OutagePeriod) -> bool:
        """Check if two periods overlap (any intersection)."""
        # If either period has no time range, consider them overlapping if same status
        if not (period1.period_from and period1.period_to and period2.period_from and period2.period_to):
            return period1.status == period2.status

        try:
            start1 = self._time_to_minutes(period1.period_from)
            end1 = self._time_to_minutes(period1.period_to)
            start2 = self._time_to_minutes(period2.period_from)
            end2 = self._time_to_minutes(period2.period_to)

            # Handle overnight periods
            if end1 <= start1:
                end1 += 24 * 60
            if end2 <= start2:
                end2 += 24 * 60

            return not (end1 <= start2 or end2 <= start1)
        except Exception as e:
            self.logger.warning(f"Error checking overlap: {e}")
            return False

    def _time_to_minutes(self, time_str: str) -> int:
        """Convert time string to minutes since midnight."""
        if not time_str:
            return 0
        try:
            hours, minutes = map(int, time_str.split(':'))
            return hours * 60 + minutes
        except (ValueError, AttributeError):
            return 0

    def mark_events_for_cancellation(self, periods: List[OutagePeriod]) -> None:
        """Mark events for cancellation (to be cancelled in next ICS generation)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            for period in periods:
                cursor.execute('''
                    UPDATE periods
                    SET calendar_event_state = 'cancelled',
                        calendar_event_ts = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE recid = ?
                ''', (datetime.now().isoformat(), period.recid))

                self.logger.info(f"Marked event {period.calendar_event_id} for cancellation due to overlap")

            conn.commit()

    def mark_event_as_sent(self, recid: str) -> None:
        """Mark an event as sent (ICS file generated)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE periods
                SET event_sent = 1, updated_at = CURRENT_TIMESTAMP
                WHERE recid = ?
            ''', (recid,))
            conn.commit()
            self.logger.debug(f"Marked event {recid} as sent")

    def get_events_for_generation(self, group_filter: Optional[List[str]] = None) -> Dict[str, List[OutagePeriod]]:
        """Get events that need to be generated or cancelled."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                try:
                    current_date_ukraine = self.get_ukraine_current_date_str()
                    self.logger.debug(f"Current Ukraine date for event generation: {current_date_ukraine}")
                except Exception as e:
                    self.logger.error(f"Error getting Ukraine current date: {e}")
                    raise

                # Get events to generate (generated but not sent)
                try:
                    if group_filter:
                        placeholders = ','.join('?' for _ in group_filter)
                        cursor = conn.execute(f'''
                            SELECT * FROM periods
                            WHERE date >= ? AND calendar_event_state = 'generated'
                            AND event_sent = 0 AND substr(name, 7) IN ({placeholders})
                            ORDER BY name, date, period_from, period_to, last_update DESC, insert_ts DESC
                        ''', (current_date_ukraine,) + tuple(group_filter))
                    else:
                        cursor = conn.execute('''
                            SELECT * FROM periods
                            WHERE date >= ? AND calendar_event_state = 'generated' AND event_sent = 0
                            ORDER BY name, date, period_from, period_to, last_update DESC, insert_ts DESC
                        ''', (current_date_ukraine,))
                except Exception as e:
                    self.logger.error(f"Error fetching events to create: {e}")
                    raise

                events_to_create = []
                seen_hashes = set()
                try:
                    for row in cursor.fetchall():
                        # Deduplicate by hash
                        if row['event_hash'] not in seen_hashes:
                            seen_hashes.add(row['event_hash'])
                            period = self._row_to_period(row)
                            events_to_create.append(period)
                except Exception as e:
                    self.logger.error(f"Error processing events to create: {e}")
                    raise

                # Get events to cancel (cancelled but not yet processed)
                try:
                    if group_filter:
                        cursor = conn.execute(f'''
                            SELECT * FROM periods
                            WHERE calendar_event_state = 'cancelled' AND event_sent = 1
                            AND substr(name, 7) IN ({placeholders})
                            ORDER BY calendar_event_ts DESC
                        ''', tuple(group_filter))
                    else:
                        cursor = conn.execute('''
                            SELECT * FROM periods
                            WHERE calendar_event_state = 'cancelled' AND event_sent = 1
                            ORDER BY calendar_event_ts DESC
                        ''')
                except Exception as e:
                    self.logger.error(f"Error fetching events to cancel: {e}")
                    raise

                events_to_cancel = []
                try:
                    for row in cursor.fetchall():
                        period = self._row_to_period(row)
                        events_to_cancel.append(period)
                except Exception as e:
                    self.logger.error(f"Error processing events to cancel: {e}")
                    raise

                self.logger.info(f"Events for generation: {len(events_to_create)} to create, {len(events_to_cancel)} to cancel")

                return {
                    'events_to_create': events_to_create,
                    'events_to_cancel': events_to_cancel
                }
        except Exception as e:
            self.logger.error(f"Unexpected error in get_events_for_generation: {e}")
            raise

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics with safe error handling"""
        with sqlite3.connect(self.db_path) as conn:
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
                'latest_insert': None,
                'events_sent': 0,
                'events_pending': 0
            }

            try:
                # Total records
                cursor.execute("SELECT COUNT(*) FROM periods")
                total_count = cursor.fetchone()
                if total_count and total_count[0] > 0:
                    stats['total_records'] = total_count[0]

                    # Unique dates
                    cursor.execute("SELECT COUNT(DISTINCT date) FROM periods")
                    unique_dates = cursor.fetchone()
                    stats['unique_dates'] = unique_dates[0] if unique_dates else 0

                    # Unique groups
                    cursor.execute("SELECT COUNT(DISTINCT name) FROM periods")
                    unique_groups = cursor.fetchone()
                    stats['unique_groups'] = unique_groups[0] if unique_groups else 0

                    # By calendar state
                    cursor.execute("""
                        SELECT calendar_event_state, COUNT(*)
                        FROM periods
                        GROUP BY calendar_event_state
                    """)
                    stats['by_state'] = dict(cursor.fetchall())

                    # Date range
                    cursor.execute("SELECT MIN(date), MAX(date) FROM periods WHERE date IS NOT NULL AND date != ''")
                    date_range = cursor.fetchone()
                    if date_range and date_range[0]:
                        stats['date_range'] = {'from': date_range[0], 'to': date_range[1]}

                    # Last 24h records
                    cursor.execute("""
                        SELECT COUNT(*) FROM periods
                        WHERE datetime(insert_ts) > datetime('now', '-24 hours')
                    """)
                    recent = cursor.fetchone()
                    stats['last_24h_records'] = recent[0] if recent else 0

                    # By status
                    cursor.execute("""
                        SELECT status, COUNT(*)
                        FROM periods
                        GROUP BY status
                    """)
                    stats['by_status'] = dict(cursor.fetchall())

                    # Latest info
                    cursor.execute("""
                        SELECT MAX(last_update), MAX(insert_ts)
                        FROM periods
                    """)
                    latest_info = cursor.fetchone()
                    if latest_info:
                        stats['latest_update'] = latest_info[0]
                        stats['latest_insert'] = latest_info[1]

                    # Event tracking stats

                    cursor.execute("SELECT COUNT(*) FROM periods WHERE event_sent = 1")
                    sent_count = cursor.fetchone()
                    stats['events_sent'] = sent_count[0] if sent_count else 0

                    cursor.execute("SELECT COUNT(*) FROM periods WHERE calendar_event_state = 'generated' AND event_sent = 0")
                    pending_count = cursor.fetchone()
                    stats['events_pending'] = pending_count[0] if pending_count else 0

            except Exception as e:
                self.logger.error(f"Error getting stats: {e}")

            return stats

    def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """Clean up old data while preserving recent records"""
        with sqlite3.connect(self.db_path) as conn:
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

    def query_periods_by_date(self, date: str) -> List[Tuple]:
        """Query periods by specific date"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name, status, period_from, period_to, calendar_event_state,
                       last_update, calendar_event_id
                FROM periods
                WHERE date = ?
                ORDER BY name, last_update DESC
            ''', (date,))
            return cursor.fetchall()

    def export_to_csv(self, output_path: Path) -> None:
        """Export all periods to CSV file."""
        import csv

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT date, name, status, period_from, period_to,
                       calendar_event_state, last_update, insert_ts, event_sent
                FROM periods
                ORDER BY date DESC, name
            ''')
            results = cursor.fetchall()

            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Date', 'Group', 'Status', 'From', 'To', 'Calendar State', 'Last Update', 'Insert Time', 'Event Sent'])
                writer.writerows(results)

        self.logger.info(f"[OK] Data exported to {output_path} ({len(results)} records)")

    def _row_to_period(self, row) -> OutagePeriod:
        """Convert database row to OutagePeriod object."""
        return OutagePeriod(
            recid=row['recid'],
            insert_ts=row['insert_ts'],
            date=row['date'],
            last_update=row['last_update'],
            name=row['name'],
            status=row['status'],
            period_from=row['period_from'],
            period_to=row['period_to'],
            calendar_event_id=row['calendar_event_id'],
            calendar_event_uid=row['calendar_event_uid'],
            calendar_event_state=row['calendar_event_state'],
            calendar_event_ts=row['calendar_event_ts'],
            event_sent=bool(row['event_sent']) if 'event_sent' in row.keys() else False,
            event_hash=row['event_hash'] if 'event_hash' in row.keys() else None,
            created_at=row['created_at'] if 'created_at' in row.keys() else None,
            updated_at=row['updated_at'] if 'updated_at' in row.keys() else None
        )
