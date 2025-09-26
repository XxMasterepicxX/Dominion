"""
FastAPI routes for scheduler management

Provides REST API endpoints for controlling and monitoring the scraper scheduler.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from datetime import datetime

from ..scheduler import get_scheduler, SchedulerStatus, JobStatus
from ..utils.logging import get_logger


logger = get_logger(__name__)
router = APIRouter(prefix="/scheduler", tags=["Scheduler Management"])


@router.post("/start")
async def start_scheduler(background_tasks: BackgroundTasks):
    """Start the scraper scheduler"""
    try:
        scheduler = await get_scheduler()
        if scheduler.status == SchedulerStatus.RUNNING:
            return {"message": "Scheduler is already running", "status": "running"}

        background_tasks.add_task(scheduler.start)
        return {"message": "Scheduler start initiated", "status": "starting"}

    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start scheduler: {str(e)}")


@router.post("/stop")
async def stop_scheduler(background_tasks: BackgroundTasks):
    """Stop the scraper scheduler"""
    try:
        scheduler = await get_scheduler()
        if scheduler.status == SchedulerStatus.STOPPED:
            return {"message": "Scheduler is already stopped", "status": "stopped"}

        background_tasks.add_task(scheduler.stop)
        return {"message": "Scheduler stop initiated", "status": "stopping"}

    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop scheduler: {str(e)}")


@router.post("/pause")
async def pause_scheduler():
    """Pause the scraper scheduler"""
    try:
        scheduler = await get_scheduler()
        if scheduler.status != SchedulerStatus.RUNNING:
            raise HTTPException(status_code=400, detail="Scheduler is not running")

        await scheduler.pause()
        return {"message": "Scheduler paused", "status": "paused"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to pause scheduler: {str(e)}")


@router.post("/resume")
async def resume_scheduler():
    """Resume the scraper scheduler"""
    try:
        scheduler = await get_scheduler()
        if scheduler.status != SchedulerStatus.PAUSED:
            raise HTTPException(status_code=400, detail="Scheduler is not paused")

        await scheduler.resume()
        return {"message": "Scheduler resumed", "status": "running"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resume scheduler: {str(e)}")


@router.get("/status")
async def get_scheduler_status() -> Dict[str, Any]:
    """Get scheduler status and metrics"""
    try:
        scheduler = await get_scheduler()
        status = scheduler.get_job_status()
        return status

    except Exception as e:
        logger.error(f"Failed to get scheduler status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scheduler status: {str(e)}")


@router.get("/jobs")
async def list_scheduled_jobs() -> List[Dict[str, Any]]:
    """List all scheduled jobs"""
    try:
        scheduler = await get_scheduler()
        jobs = scheduler.list_scheduled_jobs()
        return jobs

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> Dict[str, Any]:
    """Get status of a specific job"""
    try:
        scheduler = await get_scheduler()
        status = scheduler.get_job_status(job_id)

        if 'error' in status and status['error'] == 'Job not found':
            raise HTTPException(status_code=404, detail="Job not found")

        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@router.post("/trigger/{scraper_name}")
async def trigger_scraper(scraper_name: str, background_tasks: BackgroundTasks):
    """Manually trigger a specific scraper"""
    try:
        scheduler = await get_scheduler()

        if scraper_name not in scheduler.registered_scrapers:
            available_scrapers = list(scheduler.registered_scrapers.keys())
            raise HTTPException(
                status_code=404,
                detail=f"Scraper '{scraper_name}' not found. Available: {available_scrapers}"
            )

        background_tasks.add_task(scheduler.trigger_scraper, scraper_name)
        return {
            "message": f"Scraper '{scraper_name}' triggered",
            "scraper_name": scraper_name,
            "triggered_at": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger scraper: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger scraper: {str(e)}")


@router.get("/scrapers")
async def list_scrapers() -> Dict[str, Any]:
    """List all available scrapers with their configurations"""
    try:
        scheduler = await get_scheduler()

        scrapers_info = []
        for name, config in scheduler.registered_scrapers.items():
            scrapers_info.append({
                "name": name,
                "type": config.get("type", "unknown"),
                "schedule": config.get("schedule"),
                "enabled": config.get("enabled", False),
                "url": config.get("url"),
                "method": config.get("method")
            })

        return {
            "total_scrapers": len(scrapers_info),
            "scrapers": scrapers_info
        }

    except Exception as e:
        logger.error(f"Failed to list scrapers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list scrapers: {str(e)}")


@router.get("/metrics")
async def get_scheduler_metrics() -> Dict[str, Any]:
    """Get detailed scheduler metrics"""
    try:
        scheduler = await get_scheduler()
        status = scheduler.get_job_status()

        # Get recent job executions (last 10)
        recent_executions = []
        for execution in list(scheduler.job_executions.values())[-10:]:
            recent_executions.append({
                "job_id": execution.job_id,
                "scraper_name": execution.scraper_name,
                "status": execution.status.value,
                "start_time": execution.start_time.isoformat() if execution.start_time else None,
                "end_time": execution.end_time.isoformat() if execution.end_time else None,
                "duration_seconds": execution.duration_seconds,
                "error": execution.error
            })

        return {
            "scheduler_status": status["scheduler_status"],
            "metrics": status["metrics"],
            "recent_executions": recent_executions,
            "scraper_count": len(scheduler.registered_scrapers),
            "uptime_info": {
                "status": status["scheduler_status"],
                "last_execution": status["metrics"]["last_execution_time"]
            }
        }

    except Exception as e:
        logger.error(f"Failed to get scheduler metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scheduler metrics: {str(e)}")


@router.get("/health")
async def scheduler_health_check() -> Dict[str, Any]:
    """Health check endpoint for scheduler"""
    try:
        scheduler = await get_scheduler()

        is_healthy = (
            scheduler.status in [SchedulerStatus.RUNNING, SchedulerStatus.PAUSED] and
            len(scheduler.running_jobs) < scheduler.max_concurrent_scrapers
        )

        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "scheduler_status": scheduler.status.value,
            "active_jobs": len(scheduler.running_jobs),
            "max_concurrent": scheduler.max_concurrent_scrapers,
            "total_scrapers": len(scheduler.registered_scrapers),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Scheduler health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }