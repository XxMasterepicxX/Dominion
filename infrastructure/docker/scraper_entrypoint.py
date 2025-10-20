#!/usr/bin/env python3
"""
Dominion Scraper Entrypoint

Executes scheduled scraping workloads inside the ECS Fargate task. The behaviour is
controlled via the SCRAPER_MODE environment variable:

  - daily       → runs the day-centric scrapers (permits, crime, news, council)
  - enrichment  → runs qPublic batch enrichment for properties needing updates
  - ordinances  → re-embeds scraped ordinance markdown files

All modes rely on application code under /app/src and scripts under /app/scripts.
The entrypoint is responsible for:
  * fetching database credentials from Secrets Manager
  * configuring settings.DATABASE_URL for SQLAlchemy/asyncpg based services
  * invoking the appropriate async pipeline
"""

import asyncio
import json
import os
import signal
import sys
from contextlib import suppress
from typing import Any, Dict

import boto3
import structlog
from botocore.exceptions import ClientError
from urllib.parse import quote_plus


# Ensure src/ and scripts/ are importable even if PYTHONPATH not provided
SRC_ROOT = "/app/src"
SCRIPTS_ROOT = "/app/scripts"
for path in (SRC_ROOT, SCRIPTS_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

logger = structlog.get_logger()


def configure_logging() -> None:
    """Set a sensible default structlog configuration for ECS."""
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )


def fetch_database_secret(secret_arn: str, region: str | None = None) -> Dict[str, Any]:
    """Retrieve and parse the Aurora credentials from Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_arn)
    secret_string = response.get("SecretString")

    if not secret_string:
        raise ValueError("Secrets Manager response did not contain SecretString")

    return json.loads(secret_string)


def build_database_url(secret_payload: Dict[str, Any], database_name: str) -> str:
    """Construct an asyncpg-compatible SQLAlchemy URL from the secret payload."""
    username = secret_payload.get("username")
    password = secret_payload.get("password")
    host = secret_payload.get("host")
    port = secret_payload.get("port", 5432)
    dbname = secret_payload.get("dbname") or secret_payload.get("database") or database_name

    if not all([username, password, host, dbname]):
        raise ValueError("Secret payload missing host/username/password/database fields")

    return (
        f"postgresql+asyncpg://{quote_plus(username)}:{quote_plus(password)}@"
        f"{host}:{port}/{dbname}"
    )


def configure_database() -> None:
    """Fetch credentials (if provided) and set DATABASE_URL for downstream modules."""
    secret_arn = os.environ.get("SECRET_ARN")
    default_db = os.environ.get("DATABASE_NAME", "dominion")
    region = os.environ.get("AWS_REGION")

    if not secret_arn:
        logger.warning("No SECRET_ARN supplied – expecting DATABASE_URL to be preset")
        return

    try:
        secret = fetch_database_secret(secret_arn, region=region)
        database_url = build_database_url(secret, default_db)
        os.environ["DATABASE_URL"] = database_url
        os.environ.setdefault("PGHOST", secret.get("host", ""))
        os.environ.setdefault("PGUSER", secret.get("username", ""))
        os.environ.setdefault("PGPASSWORD", secret.get("password", ""))
        logger.info("database_url_configured", host=secret.get("host"), database=default_db)
    except (ClientError, ValueError) as exc:
        logger.error("database_configuration_failed", error=str(exc))
        raise


async def run_daily_mode() -> None:
    """Run the day-to-day scraper pipeline."""
    logger.info("scraper_mode_daily_start")
    from scripts.run_daily_scrapers import main as run_daily_main  # local import to ensure env ready

    await run_daily_main()
    logger.info("scraper_mode_daily_complete")


async def run_enrichment_mode() -> None:
    """Run qPublic enrichment batch for properties lacking enhanced data."""
    limit = int(os.environ.get("ENRICH_LIMIT", "200"))
    headless = os.environ.get("ENRICH_HEADLESS", "false").lower() == "true"
    parallel = int(os.environ.get("ENRICH_PARALLEL", "5"))

    logger.info(
        "scraper_mode_enrichment_start",
        limit=limit,
        headless=headless,
        parallel=parallel,
    )

    from scripts.enrich_qpublic_batch import enrich_qpublic_batch

    await enrich_qpublic_batch(limit=limit, headless=headless, parallel=parallel)
    logger.info("scraper_mode_enrichment_complete")


def run_ordinance_mode() -> None:
    """Embed ordinance markdown files and emit fresh embedding payloads."""
    input_dir = os.environ.get("ORDINANCE_INPUT_DIR", "data/ordinances")
    output_dir = os.environ.get("ORDINANCE_OUTPUT_DIR", "data/embeddings")
    model_name = os.environ.get("ORDINANCE_MODEL_NAME", "BAAI/bge-large-en-v1.5")

    logger.info(
        "scraper_mode_ordinances_start",
        input_dir=input_dir,
        output_dir=output_dir,
        model=model_name,
    )

    from scripts.embed_ordinances import embed_ordinances

    embed_ordinances(
        ordinance_dir=input_dir,
        model_name=model_name,
        output_dir=output_dir,
        device="cpu",
    )
    logger.info("scraper_mode_ordinances_complete")


async def dispatch_mode(mode: str) -> None:
    """Dispatch to the appropriate mode handler."""
    if mode == "daily":
        await run_daily_mode()
    elif mode == "enrichment":
        await run_enrichment_mode()
    elif mode == "ordinances":
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, run_ordinance_mode)
    else:
        raise ValueError(f"Unsupported SCRAPER_MODE '{mode}'")


def install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    """Ensure the process terminates cleanly when ECS stops the task."""

    def _graceful_shutdown(signame: str) -> None:
        logger.warning("received_shutdown_signal", signal=signame)
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for signame in ("SIGINT", "SIGTERM"):
        with suppress(NotImplementedError):
            loop.add_signal_handler(getattr(signal, signame), lambda s=signame: _graceful_shutdown(s))


def main() -> None:
    configure_logging()
    configure_database()

    mode = os.environ.get("SCRAPER_MODE", "daily").lower()
    logger.info("scraper_entrypoint_start", mode=mode)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    install_signal_handlers(loop)

    try:
        loop.run_until_complete(dispatch_mode(mode))
        logger.info("scraper_entrypoint_complete", mode=mode)
    except asyncio.CancelledError:
        logger.warning("scraper_entrypoint_cancelled")
    except Exception as exc:
        logger.error("scraper_entrypoint_failed", error=str(exc), mode=mode, exc_info=True)
        raise
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    main()
