"""
Fetch census data and store in database

Integrates census scraper with database to populate market_demographics table.
Run this script periodically (e.g., quarterly) to update demographics.
"""
import asyncio
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.config import load_market_config
from src.database.connection import db_manager
from src.scrapers.demographics.census_demographics import CensusScraper
from sqlalchemy import text
import structlog

logger = structlog.get_logger(__name__)


async def fetch_and_store_demographics(market_id: str = 'gainesville_fl'):
    """Fetch census data and store in market_demographics table"""

    # Load market config
    logger.info("loading_market_config", market_id=market_id)
    config = load_market_config(market_id)

    # Get market UUID from database
    await db_manager.initialize()
    async with db_manager.get_session() as session:
        result = await session.execute(
            text("SELECT id FROM markets WHERE market_code = :code"),
            {'code': market_id}
        )
        row = result.fetchone()
        if not row:
            logger.error("market_not_found", market_code=market_id)
            return False

        market_uuid = str(row[0])
        logger.info("market_found", market_uuid=market_uuid)

        # Fetch census data
        logger.info("fetching_census_data")
        scraper = CensusScraper(config)
        census_data = scraper.fetch_county_data()

        if not census_data:
            logger.error("census_fetch_failed")
            return False

        # Extract variables
        population = int(census_data.get('B01003_001E', 0))
        median_income = int(census_data.get('B19013_001E', 0))
        median_home_value = int(census_data.get('B25077_001E', 0))

        logger.info("census_data_retrieved",
                   population=population,
                   median_income=median_income,
                   median_home_value=median_home_value)

        # Store in database (upsert - update if exists, insert if not)
        query = text("""
            INSERT INTO market_demographics (
                market_id,
                total_population,
                median_household_income,
                median_home_value,
                census_variables,
                data_year,
                census_dataset
            ) VALUES (
                :market_id,
                :population,
                :income,
                :home_value,
                :census_vars,
                2022,
                'acs5'
            )
            ON CONFLICT (market_id, data_year)
            DO UPDATE SET
                total_population = EXCLUDED.total_population,
                median_household_income = EXCLUDED.median_household_income,
                median_home_value = EXCLUDED.median_home_value,
                census_variables = EXCLUDED.census_variables,
                scraped_at = NOW()
            RETURNING id
        """)

        result = await session.execute(query, {
            'market_id': market_uuid,
            'population': population,
            'income': median_income,
            'home_value': median_home_value,
            'census_vars': json.dumps(census_data)  # Convert dict to JSON string
        })

        await session.commit()

        demo_id = result.fetchone()[0]
        logger.info("demographics_stored",
                   demographics_id=str(demo_id),
                   market_id=market_uuid)

        print(f"\nSUCCESS: Stored demographics for {config.market.name}")
        print(f"  Population: {population:,}")
        print(f"  Median Income: ${median_income:,}")
        print(f"  Median Home Value: ${median_home_value:,}")

        return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fetch and store census demographics")
    parser.add_argument(
        "--market",
        default="gainesville_fl",
        help="Market ID (default: gainesville_fl)"
    )

    args = parser.parse_args()

    success = asyncio.run(fetch_and_store_demographics(args.market))
    sys.exit(0 if success else 1)
