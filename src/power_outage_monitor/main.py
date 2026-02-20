"""Main entry point for Power Outage Monitor."""

import sys
from .config import parse_arguments, setup_logging
from .monitor import PowerOutageMonitor


def main():
    """Main entry point with comprehensive output and Ukrainian support."""
    try:
        # Parse configuration
        config = parse_arguments()

        # Setup logging
        logger = setup_logging(config)

        print("=" * 80)
        print("POWER OUTAGE MONITOR - ICS CALENDAR SUPPORT WITH UKRAINE TIMEZONE")
        print("=" * 80)
        print("\n1. STARTUP & DATABASE CHECK")
        print("-" * 80)
        logger.info("The script will check if the database exists.")
        logger.info("If it exists, it will be used and upgraded if needed (no data loss).")
        logger.info("If it does not exist, a new database will be created.")
        logger.info("Group filter will be determined from console or JSON file (if provided).")
        print("-" * 80)

        print("\n2. INITIALIZING MONITOR")
        print("-" * 80)

        # Create monitor
        monitor = PowerOutageMonitor(config, logger)

        print("-" * 80)
        print("\n3. RUNNING SINGLE MONITORING CYCLE")
        print("-" * 80)

        # Run based on configuration
        if config.continuous_mode:
            monitor.run_continuous_monitoring(config.check_interval // 60)
        else:
            success, status = monitor.run_full_process()

            if success:
                print("\n4. PROCESS RESULTS")
                print("-" * 80)

                if status == "success":
                    logger.info("[OK] Process completed successfully!")

                    # Show statistics
                    stats = monitor.get_database_stats()
                    logger.info("\nDatabase Statistics:")
                    logger.info(f"  Total records: {stats['total_records']}")
                    logger.info(f"  Unique dates: {stats['unique_dates']}")
                    logger.info(f"  Unique groups: {stats['unique_groups']}")
                    logger.info(f"  Records in last 24h: {stats['last_24h_records']}")

                    # Show today's data
                    today = monitor.database.get_ukraine_current_date_str()
                    today_data = monitor.query_periods_by_date(today)

                    if today_data:
                        logger.info(f"\nToday's periods ({today}):")
                        seen = set()
                        for record in today_data:
                            name, status_text, period_from, period_to, state, last_update, event_id = record

                            # Create unique key to avoid duplicates
                            unique_key = (name, status_text, period_from, period_to, state)
                            if unique_key in seen:
                                continue
                            seen.add(unique_key)

                            time_info = f"({period_from}-{period_to})" if period_from and period_to else "(all day)"
                            try:
                                logger.info(f"  {name}: {status_text} {time_info} [{state}]")
                            except UnicodeEncodeError:
                                logger.info(f"  [Ukrainian group]: [Ukrainian status] {time_info} [{state}]")

                    # Show file locations
                    logger.info("\nFiles created in:")
                    logger.info(f"  JSON data: {config.json_data_dir}/")
                    logger.info(f"  ICS calendar files: {config.ics_output_dir}/")
                    logger.info(f"  Log file: {config.log_file}")

                    # Export CSV
                    csv_file = monitor.export_data_to_csv()
                    if csv_file:
                        logger.info(f"  CSV export: {csv_file}")

                    # Usage instructions
                    logger.info("\nICS Files Usage:")
                    logger.info("  - Individual .ics files: Import each file separately")
                    logger.info("  - Combined .ics file: Import all events at once")
                    logger.info("  - Cancellation .ics file: Import to remove old events")
                    logger.info("  - Manual deletion .txt: Backup option for manual removal")
                    logger.info("  - All times are in Ukraine timezone (Europe/Kiev)")

                elif status in ["no_data", "old_data", "invalid_date"]:
                    logger.info(f"[INFO] Process completed - {status}")
                    logger.info("No calendar files were generated due to data status")
            else:
                logger.info("\n[ERROR] Process failed - check the logs above")

            # Show usage information
            print("-" * 80)
            print("\n5. CONTINUOUS MONITORING OPTIONS")
            print("-" * 80)
            logger.info("To run continuous monitoring, use one of these commands:")
            logger.info("  python main.py --continuous --interval 300   # Every 5 minutes")
            logger.info("  python main.py --continuous --interval 900   # Every 15 minutes")
            logger.info("  python main.py --continuous --interval 3600  # Every hour")

            print("-" * 80)
            print("\n6. RUNNING WITH GROUP FILTERS")
            print("-" * 80)
            logger.info("You can filter monitoring by specific group codes using:")
            logger.info("  --groups 1.1,2.1,3.2")
            logger.info("or by providing a JSON file (default: groups.json) with:")
            logger.info('  {"group": ["1.1", "2.1"]}')
            logger.info("Examples:")
            logger.info("  python main.py --groups 1.1,2.1")
            logger.info("  python main.py --groups-file mygroups.json")
            logger.info("If neither is provided, all groups from the website will be processed.")

            logger.info("=" * 80)
            logger.info("MONITORING SETUP COMPLETE - ICS CALENDAR SUPPORT WITH UKRAINE TIMEZONE")
            logger.info("Check calendar_events/ folder for .ics files to import")
            logger.info("All calendar events use Ukraine timezone (Europe/Kiev) with DST support")
            logger.info("=" * 80)

        print("-" * 80)
        print("\n7. CLEANUP OLD RECORDS")
        print("-" * 80)
        monitor.cleanup_old_data()
        logger.info(f"Old records cleanup completed (older than {config.cleanup_days} days)")
        print("-" * 80)
        print("Exit.")

    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.info(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
