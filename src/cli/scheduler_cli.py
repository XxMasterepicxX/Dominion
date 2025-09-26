#!/usr/bin/env python3
"""
CLI interface for managing the Dominion scraper scheduler

Usage:
    python -m src.cli.scheduler_cli start
    python -m src.cli.scheduler_cli stop
    python -m src.cli.scheduler_cli status
    python -m src.cli.scheduler_cli trigger city_permits
"""

import asyncio
import sys
import argparse
import json
from typing import Optional
from datetime import datetime

from ..scheduler import get_scheduler, SchedulerStatus
from ..utils.logging import get_logger


logger = get_logger(__name__)


class SchedulerCLI:
    """Command-line interface for scheduler management"""

    def __init__(self):
        self.scheduler = None

    async def start_scheduler(self) -> None:
        """Start the scheduler"""
        try:
            self.scheduler = await get_scheduler()
            await self.scheduler.start()
            print("✅ Scheduler started successfully")
            print(f"📊 Scheduled {self.scheduler.metrics.total_jobs_scheduled} jobs")

            # Show scheduled jobs
            jobs = self.scheduler.list_scheduled_jobs()
            if jobs:
                print("\n📅 Scheduled Jobs:")
                for job in jobs:
                    next_run = job['next_run_time'] if job['next_run_time'] else "No next run"
                    print(f"  • {job['name']} - Next: {next_run}")

        except Exception as e:
            print(f"❌ Failed to start scheduler: {e}")
            logger.error(f"Scheduler start failed: {e}")
            sys.exit(1)

    async def stop_scheduler(self) -> None:
        """Stop the scheduler"""
        try:
            self.scheduler = await get_scheduler()
            await self.scheduler.stop()
            print("✅ Scheduler stopped successfully")

        except Exception as e:
            print(f"❌ Failed to stop scheduler: {e}")
            logger.error(f"Scheduler stop failed: {e}")
            sys.exit(1)

    async def pause_scheduler(self) -> None:
        """Pause the scheduler"""
        try:
            self.scheduler = await get_scheduler()
            await self.scheduler.pause()
            print("⏸️ Scheduler paused")

        except Exception as e:
            print(f"❌ Failed to pause scheduler: {e}")
            logger.error(f"Scheduler pause failed: {e}")
            sys.exit(1)

    async def resume_scheduler(self) -> None:
        """Resume the scheduler"""
        try:
            self.scheduler = await get_scheduler()
            await self.scheduler.resume()
            print("▶️ Scheduler resumed")

        except Exception as e:
            print(f"❌ Failed to resume scheduler: {e}")
            logger.error(f"Scheduler resume failed: {e}")
            sys.exit(1)

    async def get_scheduler_status(self, detailed: bool = False) -> None:
        """Get scheduler status and metrics"""
        try:
            self.scheduler = await get_scheduler()
            status = self.scheduler.get_job_status()

            print(f"🔄 Scheduler Status: {status['scheduler_status'].upper()}")

            metrics = status['metrics']
            print(f"📊 Execution Metrics:")
            print(f"  • Total jobs scheduled: {metrics['total_jobs_scheduled']}")
            print(f"  • Total jobs executed: {metrics['total_jobs_executed']}")
            print(f"  • Success rate: {metrics['success_rate']:.1f}%")
            print(f"  • Successful: {metrics['successful_jobs']}")
            print(f"  • Failed: {metrics['failed_jobs']}")
            print(f"  • Timeout: {metrics['timeout_jobs']}")
            print(f"  • Skipped: {metrics['skipped_jobs']}")
            print(f"  • Average execution time: {metrics['avg_execution_time_seconds']:.1f}s")

            if metrics['last_execution_time']:
                print(f"  • Last execution: {metrics['last_execution_time']}")

            if metrics['active_jobs']:
                print(f"🏃 Active Jobs: {', '.join(metrics['active_jobs'])}")

            print(f"📝 Registered Scrapers: {', '.join(status['registered_scrapers'])}")

            if detailed:
                jobs = self.scheduler.list_scheduled_jobs()
                if jobs:
                    print("\n📅 Scheduled Jobs Details:")
                    for job in jobs:
                        print(f"  • {job['name']}")
                        print(f"    ID: {job['id']}")
                        print(f"    Trigger: {job['trigger']}")
                        print(f"    Next Run: {job['next_run_time'] or 'No next run'}")
                        print()

        except Exception as e:
            print(f"❌ Failed to get scheduler status: {e}")
            logger.error(f"Scheduler status failed: {e}")
            sys.exit(1)

    async def trigger_scraper(self, scraper_name: str) -> None:
        """Manually trigger a specific scraper"""
        try:
            self.scheduler = await get_scheduler()
            print(f"🎯 Triggering scraper: {scraper_name}")
            await self.scheduler.trigger_scraper(scraper_name)
            print(f"✅ Scraper {scraper_name} triggered successfully")

        except ValueError as e:
            print(f"❌ Invalid scraper name: {e}")
            available = await self._get_available_scrapers()
            print(f"Available scrapers: {', '.join(available)}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Failed to trigger scraper: {e}")
            logger.error(f"Scraper trigger failed: {e}")
            sys.exit(1)

    async def list_scrapers(self) -> None:
        """List all available scrapers"""
        try:
            self.scheduler = await get_scheduler()
            scrapers = list(self.scheduler.registered_scrapers.keys())

            print("📋 Available Scrapers:")
            for scraper in scrapers:
                config = self.scheduler.registered_scrapers[scraper]
                schedule = config.get('schedule', 'No schedule')
                enabled = "✅" if config.get('enabled', False) else "❌"
                print(f"  {enabled} {scraper} ({config.get('type', 'unknown')}) - {schedule}")

        except Exception as e:
            print(f"❌ Failed to list scrapers: {e}")
            logger.error(f"Scraper list failed: {e}")
            sys.exit(1)

    async def _get_available_scrapers(self) -> list:
        """Get list of available scraper names"""
        try:
            self.scheduler = await get_scheduler()
            return list(self.scheduler.registered_scrapers.keys())
        except:
            return []

    async def run_daemon(self) -> None:
        """Run scheduler as a daemon (keep running)"""
        try:
            print("🚀 Starting Dominion Scraper Scheduler Daemon")
            await self.start_scheduler()

            print("🔄 Scheduler is running. Press Ctrl+C to stop.")
            try:
                while True:
                    await asyncio.sleep(60)  # Check every minute
                    # You could add periodic health checks here
            except KeyboardInterrupt:
                print("\n🛑 Received interrupt signal, stopping scheduler...")
                await self.stop_scheduler()
                print("✅ Scheduler daemon stopped")

        except Exception as e:
            print(f"❌ Daemon failed: {e}")
            logger.error(f"Scheduler daemon failed: {e}")
            sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser"""
    parser = argparse.ArgumentParser(
        description="Dominion Scraper Scheduler CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s start              Start the scheduler
  %(prog)s stop               Stop the scheduler
  %(prog)s pause              Pause the scheduler
  %(prog)s resume             Resume the scheduler
  %(prog)s status             Show scheduler status
  %(prog)s status --detailed  Show detailed status
  %(prog)s trigger city_permits  Manually trigger city permits scraper
  %(prog)s list               List all available scrapers
  %(prog)s daemon             Run as daemon (keep running)
        """
    )

    parser.add_argument(
        'command',
        choices=['start', 'stop', 'pause', 'resume', 'status', 'trigger', 'list', 'daemon'],
        help='Command to execute'
    )

    parser.add_argument(
        'scraper_name',
        nargs='?',
        help='Scraper name (required for trigger command)'
    )

    parser.add_argument(
        '--detailed',
        action='store_true',
        help='Show detailed information (for status command)'
    )

    return parser


async def main():
    """Main CLI entry point"""
    parser = create_parser()
    args = parser.parse_args()

    cli = SchedulerCLI()

    try:
        if args.command == 'start':
            await cli.start_scheduler()

        elif args.command == 'stop':
            await cli.stop_scheduler()

        elif args.command == 'pause':
            await cli.pause_scheduler()

        elif args.command == 'resume':
            await cli.resume_scheduler()

        elif args.command == 'status':
            await cli.get_scheduler_status(detailed=args.detailed)

        elif args.command == 'trigger':
            if not args.scraper_name:
                print("❌ Error: scraper_name is required for trigger command")
                parser.print_help()
                sys.exit(1)
            await cli.trigger_scraper(args.scraper_name)

        elif args.command == 'list':
            await cli.list_scrapers()

        elif args.command == 'daemon':
            await cli.run_daemon()

    except KeyboardInterrupt:
        print("\n🛑 Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logger.error(f"CLI error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())