"""ICS calendar file generation for
 Power Outage Monitor."""

import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
from typing import List, Dict, Any, Optional, Tuple
import logging
import pytz


class ICSEventGenerator:
    """Generates ICS calendar files for power outage events."""
    
    def __init__(self, output_dir: Path, timezone: str, calendar_name: str, logger: logging.Logger):
        self.output_dir = output_dir
        self.timezone = timezone
        self.calendar_name = calendar_name
        self.logger = logger
        self.ukraine_tz = pytz.timezone(timezone)
        self.output_dir.mkdir(exist_ok=True)
    
    def parse_ukraine_datetime(self, date_str: str, time_str: str) -> datetime:
        """Parse Ukraine datetime from date and time strings"""
        try:
            naive_dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
            ukraine_dt = self.ukraine_tz.localize(naive_dt)
            return ukraine_dt
        except ValueError as e:
            self.logger.warning(f"Error parsing Ukraine datetime '{date_str} {time_str}': {e}")
            return datetime.now(self.ukraine_tz)
    
    def parse_date_to_datetime(self, date_str: str) -> datetime:
        """Parse date string to datetime"""
        try:
            return datetime.strptime(date_str, "%d.%m.%Y")
        except ValueError:
            return datetime.now()
    
    def format_datetime_for_ics(self, dt: datetime) -> str:
        """Format datetime for ICS file"""
        if dt.tzinfo is not None:
            utc_dt = dt.astimezone(pytz.UTC)
        else:
            utc_dt = dt
        return utc_dt.strftime("%Y%m%dT%H%M%SZ")
    
    def escape_text(self, text: str) -> str:
        """Escape text for ICS format"""
        return text.replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')
    
    def create_ics_content(self, event: Dict[str, Any]) -> str:
        """Create ICS content for a single event"""
        # Determine event timing
        if event.get('period_from') and event.get('period_to'):
            start_time_ukraine = self.parse_ukraine_datetime(event['date'], event['period_from'])
            end_time_ukraine = self.parse_ukraine_datetime(event['date'], event['period_to'])
            
            # Handle overnight periods
            if end_time_ukraine <= start_time_ukraine:
                end_time_ukraine += timedelta(days=1)
            
            dtstart = f"DTSTART:{self.format_datetime_for_ics(start_time_ukraine)}"
            dtend = f"DTEND:{self.format_datetime_for_ics(end_time_ukraine)}"
        else:
            # All-day event
            event_date = self.parse_date_to_datetime(event['date'])
            dtstart = f"DTSTART;VALUE=DATE:{event_date.strftime('%Y%m%d')}"
            dtend = f"DTEND;VALUE=DATE:{(event_date + timedelta(days=1)).strftime('%Y%m%d')}"
        
        # Event metadata
        uid = event.get('calendar_event_uid', f"{uuid.uuid4()}@power-monitor")
        now_utc = datetime.now(pytz.UTC)
        dtstamp = f"DTSTAMP:{self.format_datetime_for_ics(now_utc)}"
        created = f"CREATED:{self.format_datetime_for_ics(now_utc)}"
        
        # Event content
        summary = self.escape_text(event['calendar_event_id'])
        
        description_parts = [
            f"Дата: {event['date']}",
            f"Група: {event['name']}",
            f"Статус: {event['status']}",
            f"Останнє оновлення: {event['last_update']}"
        ]
        
        if event.get('period_from') and event.get('period_to'):
            description_parts.append(f"Період: {event['period_from']} - {event['period_to']} (час України)")
        
        description = self.escape_text(" | ".join(description_parts))
        
        # Categories based on status
        if event['status'] == 'Електроенергії немає':
            categories = "POWER OUTAGE,UTILITY"
        else:
            categories = "POWER AVAILABLE,UTILITY"
        
        # Build ICS content
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
    
    def create_single_ics_file(self, event: Dict[str, Any]) -> Optional[Path]:
        """Create individual ICS file for a single event"""
        try:
            # Create safe filename
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', event['calendar_event_id'])
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{safe_title}.ics"
            filepath = self.output_dir / filename
            
            ics_content = self.create_ics_content(event)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(ics_content)
            
            return filepath
            
        except Exception as e:
            self.logger.error(f"Error creating ICS file for event {event.get('calendar_event_id', 'unknown')}: {e}")
            return None
    
    def create_combined_ics_file(self, events_to_create: List[Dict[str, Any]]) -> Optional[Path]:
        """Create combined ICS file for all events"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_all_power_events.ics"
            filepath = self.output_dir / filename
            
            ics_lines = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//Power Monitor//Power Outage Monitor//EN",
                "CALSCALE:GREGORIAN",
                "METHOD:PUBLISH"
            ]
            
            for event in events_to_create:
                # Determine event timing
                if event.get('period_from') and event.get('period_to'):
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
                
                summary = self.escape_text(event['calendar_event_id'])
                
                description_parts = [
                    f"Дата: {event['date']}",
                    f"Група: {event['name']}",
                    f"Статус: {event['status']}",
                    f"Останнє оновлення: {event['last_update']}"
                ]
                
                if event.get('period_from') and event.get('period_to'):
                    description_parts.append(f"Період: {event['period_from']} - {event['period_to']} (час України)")
                
                description = self.escape_text(" | ".join(description_parts))
                
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
    
    def create_cancellation_ics_file(self, events_to_delete: List[Dict[str, Any]]) -> Optional[Path]:
        """Create cancellation ICS file for deleted events"""
        if not events_to_delete:
            return None
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_cancel_events.ics"
        filepath = self.output_dir / filename
        
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
    
    def generate_deletion_summary(self, events_to_delete: List[str]) -> None:
        """Generate manual deletion summary file"""
        if not events_to_delete:
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_manual_delete.txt"
        filepath = self.output_dir / filename
        
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
    
    def generate_ics_files(self, events_to_create: List[Dict[str, Any]]) -> None:
        """Generate all ICS files for events"""
        if not events_to_create:
            self.logger.info("No events to create")
            return
        
        created_files = []
        
        # Create individual files
        for event in events_to_create:
            filepath = self.create_single_ics_file(event)
            if filepath:
                created_files.append(filepath)
        
        # Create combined file
        combined_filepath = self.create_combined_ics_file(events_to_create)
        if combined_filepath:
            created_files.append(combined_filepath)
        
        self.logger.info(f"[OK] Created {len(created_files)} ICS files")
        self.logger.info(f"  Individual files: {len(events_to_create)}")
        self.logger.info(f"  Combined file: 1")