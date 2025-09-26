#!/usr/bin/env python3
"""
Dominion Scraper Scheduler Service

Simple daemon script to run the scheduler service.
Can be used with systemd or other process managers.

Usage:
    python run_scheduler.py
    python run_scheduler.py --config-file .env.production
"""

import os
import sys
import asyncio
import signal
from pathlib import Path
import argparse

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.scheduler import get_scheduler
from src.utils.logging import get_logger
from src.config import settings


logger = get_logger(__name__)


class SchedulerDaemon:
    """Scheduler daemon service"""

    def __init__(self):
        self.scheduler = None
        self.running = False

    async def start(self):
        """Start the scheduler daemon"""
        try:
            logger.info("🚀 Starting Dominion Scraper Scheduler Daemon")
            logger.info(f"Environment: {settings.ENVIRONMENT}")
            logger.info(f"Max concurrent scrapers: {settings.MAX_CONCURRENT_SCRAPERS}")

            # Initialize and start scheduler
            self.scheduler = await get_scheduler()
            await self.scheduler.initialize()
            await self.scheduler.start()

            self.running = True
            logger.info("✅ Scheduler daemon started successfully")

            # Setup signal handlers
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)

            # Keep daemon running
            await self._run_daemon_loop()

        except Exception as e:
            logger.error(f"Failed to start scheduler daemon: {e}")
            sys.exit(1)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    async def _run_daemon_loop(self):
        """Main daemon loop"""
        try:
            while self.running:
                await asyncio.sleep(30)  # Check every 30 seconds

                # Perform health checks
                if self.scheduler:
                    metrics = self.scheduler.get_job_status()
                    active_jobs = len(metrics.get('metrics', {}).get('active_jobs', []))

                    if active_jobs > 0:
                        logger.debug(f"Health check: {active_jobs} active jobs")

        except asyncio.CancelledError:
            logger.info("Daemon loop cancelled")
        except Exception as e:
            logger.error(f"Daemon loop error: {e}")
            self.running = False

    async def stop(self):
        """Stop the scheduler daemon"""
        logger.info("🛑 Stopping scheduler daemon...")
        self.running = False

        if self.scheduler:
            await self.scheduler.stop()

        logger.info("✅ Scheduler daemon stopped")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Dominion Scraper Scheduler Daemon")
    parser.add_argument(
        '--config-file',
        help='Environment file to load (default: .env)',
        default='.env'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Log level (default: INFO)',
        default='INFO'
    )

    args = parser.parse_args()

    # Load configuration from specified file
    if args.config_file and Path(args.config_file).exists():
        os.environ['ENV_FILE'] = args.config_file
        logger.info(f"Loading configuration from: {args.config_file}")

    # Set log level
    os.environ['LOG_LEVEL'] = args.log_level

    # Start daemon
    daemon = SchedulerDaemon()
    try:
        await daemon.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await daemon.stop()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Scheduler daemon interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)