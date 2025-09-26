"""
Scraper Scheduler for Dominion Real Estate Intelligence

This module provides a comprehensive scheduling system for running all data scrapers
based on their configured schedules. It uses APScheduler for cron-based scheduling
with proper error handling, concurrency management, and execution tracking.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import json
import traceback

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
import aioredis
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from ..config import settings, data_sources
from ..database.models import ScrapingRun, ScrapingError
from ..scrapers.base.resilient_scraper import ScrapingResult, ScraperStatus, ScraperType
from ..utils.logging import get_logger


class SchedulerStatus(Enum):
    """Scheduler execution status"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class JobStatus(Enum):
    """Individual job execution status"""
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class JobExecution:
    """Track individual job execution"""
    job_id: str
    scraper_name: str
    scraper_type: str
    status: JobStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    result: Optional[ScrapingResult] = None
    error: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SchedulerMetrics:
    """Scheduler performance metrics"""
    total_jobs_scheduled: int = 0
    total_jobs_executed: int = 0
    successful_jobs: int = 0
    failed_jobs: int = 0
    timeout_jobs: int = 0
    skipped_jobs: int = 0
    avg_execution_time_seconds: float = 0.0
    last_execution_time: Optional[datetime] = None
    active_jobs: Set[str] = field(default_factory=set)

    def calculate_success_rate(self) -> float:
        """Calculate job success rate percentage"""
        if self.total_jobs_executed == 0:
            return 0.0
        return (self.successful_jobs / self.total_jobs_executed) * 100


class ScraperScheduler:
    """
    Advanced scheduler for managing scraper execution with proper error handling,
    concurrency management, and monitoring.
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.redis_client: Optional[aioredis.Redis] = None
        self.db_session_factory: Optional[async_sessionmaker] = None
        self.status = SchedulerStatus.STOPPED

        # Track job executions and metrics
        self.job_executions: Dict[str, JobExecution] = {}
        self.metrics = SchedulerMetrics()
        self.running_jobs: Set[str] = set()

        # Scraper registry - populated dynamically from config
        self.registered_scrapers: Dict[str, Dict[str, Any]] = {}

        # Configuration
        self.max_concurrent_scrapers = settings.MAX_CONCURRENT_SCRAPERS
        self.job_timeout_seconds = 3600  # 1 hour default timeout
        self.max_retries = settings.SCRAPER_MAX_RETRIES
        self.retry_delay_seconds = 300  # 5 minutes between retries

    async def initialize(self) -> None:
        """Initialize the scheduler with database and Redis connections"""
        try:
            self.status = SchedulerStatus.STARTING
            self.logger.info("Initializing scraper scheduler...")

            # Setup Redis connection
            self.redis_client = aioredis.from_url(settings.REDIS_URL)
            await self.redis_client.ping()
            self.logger.info("✓ Redis connection established")

            # Setup database connection
            engine = create_async_engine(settings.DATABASE_URL)
            self.db_session_factory = async_sessionmaker(engine, expire_on_commit=False)
            self.logger.info("✓ Database connection established")

            # Setup APScheduler
            await self._setup_scheduler()

            # Register all scrapers from configuration
            await self._register_scrapers_from_config()

            self.status = SchedulerStatus.RUNNING
            self.logger.info("🚀 Scraper scheduler initialized successfully")

        except Exception as e:
            self.status = SchedulerStatus.ERROR
            self.logger.error(f"Failed to initialize scheduler: {e}")
            raise

    async def _setup_scheduler(self) -> None:
        """Setup APScheduler with proper configuration"""
        # Use SQLite for job persistence in development, PostgreSQL in production
        if settings.is_production:
            jobstore_url = settings.database_url_sync
        else:
            jobstore_url = "sqlite:///./scheduler_jobs.db"

        jobstores = {
            'default': SQLAlchemyJobStore(url=jobstore_url)
        }

        executors = {
            'default': AsyncIOExecutor()
        }

        job_defaults = {
            'coalesce': True,  # Combine multiple pending instances of the same job
            'max_instances': 1,  # Only one instance of each job can run
            'misfire_grace_time': 300  # 5 minutes grace for missed jobs
        }

        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults
        )

        self.logger.info("✓ APScheduler configured")

    async def _register_scrapers_from_config(self) -> None:
        """Register all scrapers from configuration"""
        self.logger.info("Registering scrapers from configuration...")

        # Register API-based scrapers
        for source_name, config in data_sources.API_SOURCES.items():
            await self._register_api_scraper(source_name, config)

        # Register web scraping sources
        for source_name, config in data_sources.SCRAPING_SOURCES.items():
            await self._register_web_scraper(source_name, config)

        self.logger.info(f"✓ Registered {len(self.registered_scrapers)} scrapers")

    async def _register_api_scraper(self, source_name: str, config: Dict[str, Any]) -> None:
        """Register an API-based scraper"""
        scraper_config = {
            'name': source_name,
            'type': 'api',
            'url': config.get('url'),
            'schedule': config.get('schedule'),
            'rate_limit': config.get('rate_limit', 100),
            'auth_required': config.get('auth_required', False),
            'format': config.get('format', 'json'),
            'enabled': True
        }

        self.registered_scrapers[source_name] = scraper_config

        # Schedule the job if schedule is defined
        schedule_key = config.get('schedule')
        if schedule_key and schedule_key in data_sources.SCRAPING_SCHEDULE:
            cron_expression = data_sources.SCRAPING_SCHEDULE[schedule_key]
            await self._schedule_scraper_job(source_name, cron_expression)

    async def _register_web_scraper(self, source_name: str, config: Dict[str, Any]) -> None:
        """Register a web scraping source"""
        scraper_config = {
            'name': source_name,
            'type': 'web_scraper',
            'url': config.get('url') or config.get('base_url'),
            'method': config.get('method', 'http'),
            'schedule': config.get('schedule'),
            'enabled': True
        }

        self.registered_scrapers[source_name] = scraper_config

        # Schedule the job if schedule is defined
        schedule_key = config.get('schedule')
        if schedule_key and schedule_key in data_sources.SCRAPING_SCHEDULE:
            cron_expression = data_sources.SCRAPING_SCHEDULE[schedule_key]
            await self._schedule_scraper_job(source_name, cron_expression)

    async def _schedule_scraper_job(self, scraper_name: str, cron_expression: str) -> None:
        """Schedule a scraper job using cron expression"""
        try:
            # Parse cron expression (minute hour day month day_of_week)
            cron_parts = cron_expression.split()
            if len(cron_parts) != 5:
                raise ValueError(f"Invalid cron expression: {cron_expression}")

            minute, hour, day, month, day_of_week = cron_parts

            # Create cron trigger
            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week
            )

            # Add job to scheduler
            job_id = f"scraper_{scraper_name}"
            self.scheduler.add_job(
                func=self._execute_scraper_job,
                trigger=trigger,
                args=[scraper_name],
                id=job_id,
                name=f"Scraper: {scraper_name}",
                replace_existing=True
            )

            self.metrics.total_jobs_scheduled += 1
            self.logger.info(f"✓ Scheduled {scraper_name} with cron: {cron_expression}")

        except Exception as e:
            self.logger.error(f"Failed to schedule {scraper_name}: {e}")
            raise

    async def _execute_scraper_job(self, scraper_name: str) -> None:
        """Execute a single scraper job with proper error handling and tracking"""
        job_id = f"scraper_{scraper_name}"

        # Check if job is already running
        if job_id in self.running_jobs:
            self.logger.warning(f"Skipping {scraper_name} - already running")
            self._record_job_execution(job_id, scraper_name, JobStatus.SKIPPED,
                                     error="Previous instance still running")
            return

        # Check concurrency limits
        if len(self.running_jobs) >= self.max_concurrent_scrapers:
            self.logger.warning(f"Skipping {scraper_name} - max concurrent jobs reached")
            self._record_job_execution(job_id, scraper_name, JobStatus.SKIPPED,
                                     error=f"Max concurrent jobs ({self.max_concurrent_scrapers}) reached")
            return

        execution = JobExecution(
            job_id=job_id,
            scraper_name=scraper_name,
            scraper_type=self.registered_scrapers[scraper_name].get('type', 'unknown'),
            status=JobStatus.RUNNING,
            start_time=datetime.now()
        )

        self.job_executions[job_id] = execution
        self.running_jobs.add(job_id)
        self.metrics.active_jobs.add(job_id)

        try:
            self.logger.info(f"🔄 Starting scraper job: {scraper_name}")

            # Execute the scraper with timeout
            result = await asyncio.wait_for(
                self._run_scraper(scraper_name),
                timeout=self.job_timeout_seconds
            )

            # Record successful execution
            execution.status = JobStatus.SUCCESS
            execution.result = result
            execution.end_time = datetime.now()
            execution.duration_seconds = (execution.end_time - execution.start_time).total_seconds()

            self.metrics.successful_jobs += 1
            self.logger.info(f"✅ Scraper job completed: {scraper_name} ({execution.duration_seconds:.1f}s)")

            # Store scraping run in database
            await self._store_scraping_run(execution)

        except asyncio.TimeoutError:
            execution.status = JobStatus.TIMEOUT
            execution.error = f"Job timed out after {self.job_timeout_seconds} seconds"
            execution.end_time = datetime.now()

            self.metrics.timeout_jobs += 1
            self.logger.error(f"⏰ Scraper job timeout: {scraper_name}")

        except Exception as e:
            execution.status = JobStatus.FAILED
            execution.error = str(e)
            execution.end_time = datetime.now()

            self.metrics.failed_jobs += 1
            self.logger.error(f"❌ Scraper job failed: {scraper_name} - {e}")
            self.logger.debug(traceback.format_exc())

            # Store error in database
            await self._store_scraping_error(execution, e)

        finally:
            self.running_jobs.discard(job_id)
            self.metrics.active_jobs.discard(job_id)
            self.metrics.total_jobs_executed += 1
            self.metrics.last_execution_time = datetime.now()

            # Update average execution time
            if execution.duration_seconds:
                total_time = self.metrics.avg_execution_time_seconds * (self.metrics.total_jobs_executed - 1)
                self.metrics.avg_execution_time_seconds = (total_time + execution.duration_seconds) / self.metrics.total_jobs_executed

    async def _run_scraper(self, scraper_name: str) -> ScrapingResult:
        """Run the appropriate scraper based on its configuration"""
        scraper_config = self.registered_scrapers[scraper_name]
        scraper_type = scraper_config['type']

        # Import and instantiate the appropriate scraper class
        if scraper_name == 'city_permits':
            from ..scrapers.city_permits import CityPermitsScraper
            scraper = CityPermitsScraper(self.redis_client)
            return await scraper.scrape_permits()

        elif scraper_name == 'census_data':
            from ..scrapers.census_demographics import CensusDemographicsScraper
            scraper = CensusDemographicsScraper(self.redis_client)
            # Default census request for Gainesville demographics
            from ..scrapers.census_demographics import CensusDataRequest
            request = CensusDataRequest(
                variables=["B01001_001E", "B25001_001E"],  # Population, Housing Units
                geography="place:27000",  # Gainesville
                state="12",  # Florida
                dataset="acs5"
            )
            return await scraper.scrape_demographics([request])

        elif scraper_name == 'crime_data':
            from ..scrapers.crime_data import CrimeDataScraper
            scraper = CrimeDataScraper(self.redis_client)
            return await scraper.scrape_crime_data()

        elif scraper_name == 'zoning_data':
            from ..scrapers.zoning import ZoningScraper
            scraper = ZoningScraper(self.redis_client)
            return await scraper.scrape_zoning_data()

        elif scraper_name == 'gainesville_sun':
            from ..scrapers.news_rss_extractor import NewsRSSExtractor
            scraper = NewsRSSExtractor(self.redis_client)
            return await scraper.extract_news()

        elif scraper_name == 'property_appraiser':
            from ..scrapers.property_appraiser_bulk import PropertyAppraisalBulkDownloader
            scraper = PropertyAppraisalBulkDownloader(self.redis_client)
            return await scraper.download_bulk_data()

        elif scraper_name == 'county_permits':
            from ..scrapers.county_permits import CountyPermitsScraper
            scraper = CountyPermitsScraper(self.redis_client)
            return await scraper.scrape_permits()

        elif scraper_name == 'sunbiz_llc':
            from ..scrapers.sunbiz_llc_monitor import SunbizLLCMonitor
            scraper = SunbizLLCMonitor(self.redis_client)
            return await scraper.monitor_llc_formations()

        elif scraper_name == 'city_council':
            from ..scrapers.city_council_scraper import CityCouncilScraper
            scraper = CityCouncilScraper(self.redis_client)
            return await scraper.scrape_agendas_and_minutes()

        else:
            raise ValueError(f"Unknown scraper: {scraper_name}")

    def _record_job_execution(self, job_id: str, scraper_name: str, status: JobStatus, error: Optional[str] = None) -> None:
        """Record a job execution event"""
        execution = JobExecution(
            job_id=job_id,
            scraper_name=scraper_name,
            scraper_type=self.registered_scrapers[scraper_name].get('type', 'unknown'),
            status=status,
            start_time=datetime.now(),
            end_time=datetime.now(),
            error=error
        )

        self.job_executions[job_id] = execution

        if status == JobStatus.SKIPPED:
            self.metrics.skipped_jobs += 1

    async def _store_scraping_run(self, execution: JobExecution) -> None:
        """Store successful scraping run in database"""
        if not self.db_session_factory:
            return

        try:
            async with self.db_session_factory() as session:
                scraping_run = ScrapingRun(
                    scraper_id=execution.scraper_name,
                    scraper_type=ScraperType.API if execution.scraper_type == 'api' else ScraperType.WEB,
                    status=ScraperStatus.COMPLETED,
                    start_time=execution.start_time,
                    end_time=execution.end_time,
                    duration_seconds=execution.duration_seconds,
                    records_processed=execution.result.records_processed if execution.result else 0,
                    records_new=execution.result.records_new if execution.result else 0,
                    records_updated=execution.result.records_updated if execution.result else 0,
                    metadata={
                        'job_id': execution.job_id,
                        'scheduled_execution': True
                    }
                )
                session.add(scraping_run)
                await session.commit()
        except Exception as e:
            self.logger.error(f"Failed to store scraping run: {e}")

    async def _store_scraping_error(self, execution: JobExecution, error: Exception) -> None:
        """Store scraping error in database"""
        if not self.db_session_factory:
            return

        try:
            async with self.db_session_factory() as session:
                scraping_error = ScrapingError(
                    scraper_id=execution.scraper_name,
                    scraper_type=ScraperType.API if execution.scraper_type == 'api' else ScraperType.WEB,
                    error_type=type(error).__name__,
                    error_message=str(error),
                    error_details=traceback.format_exc(),
                    retry_count=execution.retry_count,
                    metadata={
                        'job_id': execution.job_id,
                        'scheduled_execution': True
                    }
                )
                session.add(scraping_error)
                await session.commit()
        except Exception as e:
            self.logger.error(f"Failed to store scraping error: {e}")

    async def start(self) -> None:
        """Start the scheduler"""
        if self.status == SchedulerStatus.RUNNING:
            self.logger.warning("Scheduler is already running")
            return

        if not self.scheduler:
            await self.initialize()

        self.scheduler.start()
        self.status = SchedulerStatus.RUNNING
        self.logger.info("🚀 Scraper scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler gracefully"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=True)

        if self.redis_client:
            await self.redis_client.close()

        self.status = SchedulerStatus.STOPPED
        self.logger.info("🛑 Scraper scheduler stopped")

    async def pause(self) -> None:
        """Pause the scheduler"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.pause()
            self.status = SchedulerStatus.PAUSED
            self.logger.info("⏸️ Scraper scheduler paused")

    async def resume(self) -> None:
        """Resume the scheduler"""
        if self.scheduler and self.status == SchedulerStatus.PAUSED:
            self.scheduler.resume()
            self.status = SchedulerStatus.RUNNING
            self.logger.info("▶️ Scraper scheduler resumed")

    async def trigger_scraper(self, scraper_name: str) -> None:
        """Manually trigger a scraper job"""
        if scraper_name not in self.registered_scrapers:
            raise ValueError(f"Unknown scraper: {scraper_name}")

        self.logger.info(f"🎯 Manually triggering scraper: {scraper_name}")
        await self._execute_scraper_job(scraper_name)

    def get_job_status(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """Get status of jobs"""
        if job_id:
            execution = self.job_executions.get(job_id)
            if execution:
                return {
                    'job_id': execution.job_id,
                    'scraper_name': execution.scraper_name,
                    'status': execution.status.value,
                    'start_time': execution.start_time.isoformat() if execution.start_time else None,
                    'end_time': execution.end_time.isoformat() if execution.end_time else None,
                    'duration_seconds': execution.duration_seconds,
                    'error': execution.error
                }
            return {'error': 'Job not found'}
        else:
            return {
                'scheduler_status': self.status.value,
                'metrics': {
                    'total_jobs_scheduled': self.metrics.total_jobs_scheduled,
                    'total_jobs_executed': self.metrics.total_jobs_executed,
                    'successful_jobs': self.metrics.successful_jobs,
                    'failed_jobs': self.metrics.failed_jobs,
                    'timeout_jobs': self.metrics.timeout_jobs,
                    'skipped_jobs': self.metrics.skipped_jobs,
                    'success_rate': self.metrics.calculate_success_rate(),
                    'avg_execution_time_seconds': self.metrics.avg_execution_time_seconds,
                    'active_jobs': list(self.metrics.active_jobs),
                    'last_execution_time': self.metrics.last_execution_time.isoformat() if self.metrics.last_execution_time else None
                },
                'registered_scrapers': list(self.registered_scrapers.keys()),
                'running_jobs': list(self.running_jobs)
            }

    def list_scheduled_jobs(self) -> List[Dict[str, Any]]:
        """List all scheduled jobs"""
        if not self.scheduler:
            return []

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })

        return jobs


# Global scheduler instance
scheduler_instance = ScraperScheduler()


async def get_scheduler() -> ScraperScheduler:
    """Get the global scheduler instance"""
    return scheduler_instance