#!/usr/bin/env python3
"""
Dominion Scraper Entrypoint

Runs scheduled scraping tasks based on SCRAPER_MODE:
- daily: Permits, sales (default)
- enrichment: Entity enrichment from SunBiz
- ordinances: Update ordinance documents
"""

import os
import sys
import time
from datetime import datetime

import structlog
import boto3
from botocore.exceptions import ClientError

# Add src to path
sys.path.insert(0, '/app/src')

from scrapers.permits.alachua_permits import AlachuaPermitScraper
from scrapers.sales.alachua_sales import AlachuaSalesScraper
from services.sunbiz_enrichment import SunBizEnrichment
from database.connection import get_connection

logger = structlog.get_logger()

# Environment variables
SCRAPER_MODE = os.environ.get('SCRAPER_MODE', 'daily')
CLUSTER_ARN = os.environ.get('CLUSTER_ARN')
SECRET_ARN = os.environ.get('SECRET_ARN')
DATABASE_NAME = os.environ.get('DATABASE_NAME', 'dominion')


class RDSDataAPIConnection:
    """Simple RDS Data API connection wrapper"""

    def __init__(self, cluster_arn: str, secret_arn: str, database: str):
        self.cluster_arn = cluster_arn
        self.secret_arn = secret_arn
        self.database = database
        self.rds_client = boto3.client('rds-data')

    def execute(self, sql: str, parameters=None):
        """Execute SQL via RDS Data API"""
        params = {
            'resourceArn': self.cluster_arn,
            'secretArn': self.secret_arn,
            'database': self.database,
            'sql': sql,
        }
        if parameters:
            params['parameters'] = parameters

        return self.rds_client.execute_statement(**params)


def run_daily_scrapers():
    """Run daily permit and sales scrapers"""
    logger.info("Starting daily scrapers", mode="daily")

    conn = RDSDataAPIConnection(CLUSTER_ARN, SECRET_ARN, DATABASE_NAME)

    # Run permit scraper
    logger.info("Running permit scraper...")
    try:
        permit_scraper = AlachuaPermitScraper(conn)
        permits = permit_scraper.scrape_permits(days_back=1)  # Yesterday only
        logger.info("Permit scraping complete", count=len(permits))
    except Exception as e:
        logger.error("Permit scraping failed", error=str(e), exc_info=True)

    # Run sales scraper
    logger.info("Running sales scraper...")
    try:
        sales_scraper = AlachuaSalesScraper(conn)
        sales = sales_scraper.scrape_sales(days_back=7)  # Last week
        logger.info("Sales scraping complete", count=len(sales))
    except Exception as e:
        logger.error("Sales scraping failed", error=str(e), exc_info=True)

    logger.info("Daily scrapers complete")


def run_entity_enrichment():
    """Run weekly entity enrichment from SunBiz"""
    logger.info("Starting entity enrichment", mode="enrichment")

    conn = RDSDataAPIConnection(CLUSTER_ARN, SECRET_ARN, DATABASE_NAME)

    try:
        enrichment = SunBizEnrichment(conn)

        # Get entities needing enrichment (no SunBiz data)
        result = conn.execute(
            """
            SELECT entity_id, name
            FROM entities
            WHERE sunbiz_document_number IS NULL
            AND entity_type IN ('LLC', 'Corporation', 'Partnership')
            LIMIT 100
            """
        )

        entities = result.get('records', [])
        logger.info("Found entities to enrich", count=len(entities))

        enriched_count = 0
        for entity_row in entities:
            entity_id = entity_row[0]['longValue']
            entity_name = entity_row[1]['stringValue']

            try:
                enrichment.enrich_by_name(entity_name)
                enriched_count += 1
                time.sleep(2)  # Rate limiting
            except Exception as e:
                logger.warning(
                    "Failed to enrich entity",
                    entity_id=entity_id,
                    name=entity_name,
                    error=str(e)
                )

        logger.info("Entity enrichment complete", enriched=enriched_count)

    except Exception as e:
        logger.error("Entity enrichment failed", error=str(e), exc_info=True)


def run_ordinance_updates():
    """Run monthly ordinance updates"""
    logger.info("Starting ordinance updates", mode="ordinances")

    # This would scrape municipal websites for ordinance updates
    # For hackathon, this can be a stub
    logger.info("Ordinance updates not yet implemented")


def main():
    """Main entrypoint"""
    start_time = datetime.utcnow()
    logger.info(
        "Dominion scraper starting",
        mode=SCRAPER_MODE,
        timestamp=start_time.isoformat()
    )

    try:
        if SCRAPER_MODE == 'daily':
            run_daily_scrapers()
        elif SCRAPER_MODE == 'enrichment':
            run_entity_enrichment()
        elif SCRAPER_MODE == 'ordinances':
            run_ordinance_updates()
        else:
            logger.error("Unknown scraper mode", mode=SCRAPER_MODE)
            sys.exit(1)

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            "Scraper completed successfully",
            mode=SCRAPER_MODE,
            elapsed_seconds=elapsed
        )
        sys.exit(0)

    except Exception as e:
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            "Scraper failed",
            mode=SCRAPER_MODE,
            error=str(e),
            elapsed_seconds=elapsed,
            exc_info=True
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
