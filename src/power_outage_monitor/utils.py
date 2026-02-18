"""Utility functions for Power Outage Monitor with smart period comparison."""

import re
from datetime import datetime, time
from typing import List, Optional, Dict, Any
import logging


def normalize_time(time_str: str) -> str:
    """Normalize time string to HH:MM format with 24:00 -> 23:59 conversion."""
    # Remove whitespace
    time_str = time_str.strip()
    
    # Handle 24:00 special case
    if time_str == "24:00":
        return "23:59"
    
    # Handle different separators
    time_str = re.sub(r'[.:]', ':', time_str)
    
    # Ensure HH:MM format
    if ':' in time_str:
        parts = time_str.split(':')
        if len(parts) == 2:
            try:
                hour = int(parts[0])  # CORRECT: First part is hour
                minute = int(parts[1])  # CORRECT: Second part is minute
                return f"{hour:02d}:{minute:02d}"
            except ValueError:
                pass
    
    # If parsing fails, return original
    return time_str


def time_to_minutes(time_str: str) -> int:
    """Convert time string to minutes since midnight."""
    if not time_str:
        return 0
    try:
        hours, minutes = map(int, time_str.
split(':'))
        return hours * 60 + minutes
    except (ValueError, AttributeError):
        return 0


def minutes_to_time(minutes: int) -> str:
    """Convert minutes since midnight to time string."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def periods_intersect(period1, period2) -> bool:
    """Check if two time periods intersect, handling overnight periods."""
    try:
        # Handle both dict-like and object-like periods
        if hasattr(period1, 'period_from'):
            # OutagePeriod object
            start1 = time_to_minutes(period1.period_from or '')
            end1 = time_to_minutes(period1.period_to or '')
        else:
            # Dict-like object
            start1 = time_to_minutes(period1.get('period_from', ''))
            end1 = time_to_minutes(period1.get('period_to', ''))
        
        if hasattr(period2, 'period_from'):
            # OutagePeriod object
            start2 = time_to_minutes(period2.period_from or '')
            end2 = time_to_minutes(period2.period_to or '')
        else:
            # Dict-like object
            start2 = time_to_minutes(period2.get('period_from', ''))
            end2 = time_to_minutes(period2.get('period_to', ''))
        
        # Handle overnight periods
        if end1 < start1:
            end1 += 24 * 60
        if end2 < start2:
            end2 += 24 * 60
        
        return not (end1 <= start2 or end2 <= start1)
    except Exception as e:
        return False

def extract_group_code(group_name: str) -> str:
    """Extract group code from group name (e.g., 'Група 1.1' -> '1.1')"""
    if not group_name:
        return group_name
    
    # Split by space and get the second part if it exists
    parts = group_name.split(' ')
    if len(parts) > 1:
        return parts[1]
    
    return group_name


class GroupFilter:
    """Handles group filtering logic with Ukrainian group code extraction."""
    
    def __init__(self, group_filter: Optional[List[str]], logger: logging.Logger):
        self.group_filter = set(group_filter) if group_filter else None
        self.logger = logger
    
    def should_include_period(self, period) -> bool:
        """Check if a period should be included based on group filter."""
        if not self.group_filter:
            return True
        
        # Extract group code from name (e.g., "Група 1.1" -> "1.1")
        group_code = extract_group_code(period.name)
        
        return group_code in self.group_filter
    
    def filter_periods(self, periods: List) -> List:
        """Filter list of periods based on group filter."""
        if not self.group_filter:
            return periods
        
        filtered = [p for p in periods if self.should_include_period(p)]
        
        self.logger.info(f"Filtered {len(periods)} periods to {len(filtered)} based on groups: {sorted(self.group_filter)}")
        return filtered


class SmartPeriodComparator:
    """Smart period comparator with duplicate detection and overlap handling."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def process_smart_period_comparisons(self, database, new_periods: List) -> None:
        """Process periods with smart duplicate detection and overlap handling."""
        self.logger.info("Processing smart period comparisons with overlap detection...")
        try:
            current_date_ukraine = database.get_ukraine_current_date_str()
            # Group new periods by name
            groups_by_name = {}
            for period in new_periods:
                if period.name not in groups_by_name:
                    groups_by_name[period.name] = []
                groups_by_name[period.name].append(period)

            # Process each group
            for name, new_group_periods in groups_by_name.items():
                self.logger.debug(f"Processing group '{name}' with {len(new_group_periods)} new periods")

                for new_period in new_group_periods:
                    self._process_single_period(database, new_period)
        except Exception as e:
            self.logger.error(f"Error in process_smart_period_comparisons: {e}")
    
    def _process_single_period(self, database, new_period) -> None:
        """Process a single new period with smart logic."""
        
        # Step 1: Check if identical event already exists and was sent
        identical_event = database.check_identical_event_exists(new_period)
        if identical_event:
            self.logger.info(f"Identical event already sent for {new_period.name}, marking as discarded")
            database.update_calendar_event_state(new_period.recid, 'discarded')
            return
        
        # Step 2: Find overlapping events
        overlapping_events = database.find_overlapping_events(new_period)
        
        if overlapping_events:
            self.logger.info(f"Found {len(overlapping_events)} overlapping events for {new_period.name}")
            
            # Step 3: Compare with overlapping events
            should_generate_new = self._should_generate_new_event(new_period, overlapping_events)
            
            if should_generate_new:
                # Mark new event as generated
                database.update_calendar_event_state(new_period.recid, 'generated')
                
                # Mark overlapping events for cancellation
                database.mark_events_for_cancellation(overlapping_events)
                
                self.logger.info(f"New event {new_period.calendar_event_id} will be generated, {len(overlapping_events)} events marked for cancellation")
            else:
                # Keep existing events, discard new one
                database.update_calendar_event_state(new_period.recid, 'discarded')
                self.logger.info(f"Keeping existing events, discarding new event {new_period.calendar_event_id}")
        else:
            # No overlaps, generate new event
            database.update_calendar_event_state(new_period.recid, 'generated')
            self.logger.info(f"No overlaps found, generating new event {new_period.calendar_event_id}")
    
    def _should_generate_new_event(self, new_period, existing_periods: List) -> bool:
        """Determine if new event should be generated over existing ones."""
        
        # Rule 1: Always prefer newer last_update
        for existing in existing_periods:
            if new_period.last_update <= existing.last_update:
                self.logger.debug(f"New period has older/same last_update ({new_period.last_update} vs {existing.last_update})")
                return False
        
        # Rule 2: If new period has newer last_update, generate it
        self.logger.debug(f"New period has newer last_update, will generate")
        return True


class PeriodComparator:
    """Legacy period comparator for backward compatibility."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def process_advanced_period_comparisons(self, database, new_periods: List) -> None:
        """Process advanced period comparisons with intersection logic."""
        self.logger.info("Processing advanced period comparisons...")
        
        current_date_ukraine = database.get_ukraine_current_date_str()
        
        # Group new periods by name
        groups_by_name = {}
        for period in new_periods:
            if period.name not in groups_by_name:
                groups_by_name[period.name] = []
            groups_by_name[period.name].append(period)
        
        # Process each group
        for name, new_group_periods in groups_by_name.items():
            if not new_group_periods:
                self.logger.warning(f"Empty new_group_periods for {name}")
                continue
            
            self.logger.debug(f"Processing group '{name}' with {len(new_group_periods)} new periods")
            
            # Get existing records for this group AND current date only
            all_existing_periods = database.get_periods_by_name_and_date(name, current_date_ukraine)
            
            if not all_existing_periods:
                self.logger.warning(f"No existing periods found for {name} - this shouldn't happen after insertion")
                continue
            
            # Sort all existing periods by last_update DESC, then insert_ts DESC
            all_existing_periods.sort(key=lambda x: (x.last_update, x.insert_ts), reverse=True)
            
            self.logger.debug(f"Found {len(all_existing_periods)} total periods for '{name}' on {current_date_ukraine}")
            
            # Process based on the latest period's status
            latest_period = all_existing_periods[0]
            
            if latest_period.status == 'Електроенергія є':
                # For "power available" status, mark latest as generated, others as discarded
                self.logger.debug(f"Processing 'Електроенергія є' status for '{name}'")
                for i, period in enumerate(all_existing_periods):
                    state = 'generated' if i == 0 else 'discarded'
                    if period.calendar_event_state != state:
                        database.update_calendar_event_state(period.recid, state)
                        self.logger.debug(f"Updated period {period.recid} to state '{state}'")
            else:
                # For "power outage" status, process period intersections
                self.logger.debug(f"Processing 'Електроенергії немає' status for '{name}'")
                self._process_period_intersections(database, all_existing_periods)
    
    def _process_period_intersections(self, database, all_periods: List) -> None:
        """Process period intersections for power outage periods."""
        if not all_periods:
            self.logger.warning("Empty all_periods in process_period_intersections")
            return
        
        group_name = all_periods[0].name if all_periods else "unknown"
        self.logger.debug(f"Processing period intersections for '{group_name}' with {len(all_periods)} periods")
        
        # Filter periods that have time ranges
        period_records = [p for p in all_periods if p.period_from and p.period_to]
        
        if not period_records:
            # No time periods, just mark latest as generated, others as discarded
            self.logger.debug(f"No time periods found for '{group_name}', marking latest as generated")
            latest = all_periods[0]
            database.update_calendar_event_state(latest.recid, 'generated')
            
            for period in all_periods[1:]:
                database.update_calendar_event_state(period.recid, 'discarded')
            return
        
        # Periods are already sorted by last_update DESC, insert_ts DESC
        latest_record = period_records[0]
        
        self.logger.debug(f"Latest period for '{group_name}': {latest_record.period_from}-{latest_record.period_to}, last_update={latest_record.last_update}")
        
        # Mark latest as generated
        if latest_record.calendar_event_state != 'generated':
            database.update_calendar_event_state(latest_record.recid, 'generated')
            self.logger.debug(f"Marked latest period {latest_record.recid} as 'generated'")
        
        # Check intersections with older records
        for older_record in period_records[1:]:
            if self._periods_intersect_objects(latest_record, older_record):
                state = 'discarded'
                self.logger.debug(f"Period {older_record.recid} intersects with latest, marking as 'discarded'")
            else:
                state = 'discarded'  # In original logic, all older records are discarded
                self.logger.debug(f"Period {older_record.recid} doesn't intersect but marking as 'discarded' (original logic)")
            
            if older_record.calendar_event_state != state:
                database.update_calendar_event_state(older_record.recid, state)
                self.logger.debug(f"Updated period {older_record.recid} to state '{state}'")
    
    def _periods_intersect_objects(self, period1, period2) -> bool:
        """Check if two period objects intersect."""
        try:
            start1 = time_to_minutes(period1.period_from)
            end1 = time_to_minutes(period1.period_to)
            start2 = time_to_minutes(period2.period_from)
            end2 = time_to_minutes(period2.period_to)
            
            # Handle overnight periods
            if end1 < start1:
                end1 += 24 * 60
            if end2 < start2:
                end2 += 24 * 60
            
            intersects = not (end1 <= start2 or end2 <= start1)
            
            self.logger.debug(f"Intersection check: {period1.period_from}-{period1.period_to} vs {period2.period_from}-{period2.period_to} = {intersects}")
            
            return intersects
        except Exception as e:
            self.logger.warning(f"Error checking period intersection: {e}")
            return False