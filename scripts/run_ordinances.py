#!/usr/bin/env python3
"""
Run Ordinances Scraper

Scrapes municipal ordinances for the current market based on YAML config.

Usage:
    python scripts/run_ordinances.py
    python scripts/run_ordinances.py --market gainesville_fl
    python scripts/run_ordinances.py --scope county  # Override to county-level
"""

import asyncio
import argparse
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.loader import load_market_config
from src.config.current_market import get_current_market
from src.scrapers.ordinances import run_municode_scraper


async def main():
    parser = argparse.ArgumentParser(description="Run Municipal Ordinances Scraper")
    parser.add_argument(
        "--market",
        type=str,
        help="Market config to use (e.g., 'gainesville_fl'). Defaults to current market."
    )
    parser.add_argument(
        "--scope",
        type=str,
        choices=["market", "county", "state", "custom"],
        help="Override scope from config ('market', 'county', 'state', 'custom')"
    )
    parser.add_argument(
        "--cities",
        type=str,
        nargs="+",
        help="Specific cities to scrape (only when scope='custom')"
    )

    args = parser.parse_args()

    # Load market config
    if args.market:
        market_id = args.market
    else:
        market_id = get_current_market()

    print(f"Loading market config: {market_id}")
    config = load_market_config(market_id)

    if not config.scrapers.ordinances:
        print(f"❌ Ordinances scraper not configured for {market_id}")
        print(f"   Add 'ordinances' section to src/config/markets/{market_id}.yaml")
        return

    if not config.scrapers.ordinances.enabled:
        print(f"❌ Ordinances scraper is disabled for {market_id}")
        print(f"   Set 'enabled: true' in config")
        return

    # Override scope if provided
    if args.scope:
        print(f"⚙️  Overriding scope: {config.scrapers.ordinances.scope} → {args.scope}")
        config.scrapers.ordinances.scope = args.scope

    # Override cities if provided
    if args.cities:
        if args.scope != "custom":
            print("⚠️  --cities requires --scope custom, setting scope to custom")
            config.scrapers.ordinances.scope = "custom"
        config.scrapers.ordinances.municipalities = args.cities
        print(f"⚙️  Scraping custom cities: {', '.join(args.cities)}")

    # Run scraper
    print(f"\n{'=' * 80}")
    print(f"STARTING ORDINANCES SCRAPER")
    print(f"Market: {config.market.name}")
    print(f"Scope: {config.scrapers.ordinances.scope}")
    print(f"Platform: {config.scrapers.ordinances.platform}")
    print(f"Output: {config.scrapers.ordinances.output_dir}")
    print(f"{'=' * 80}\n")

    results = await run_municode_scraper(config)

    print(f"\n{'=' * 80}")
    print(f"✅ SCRAPER COMPLETE")
    print(f"{'=' * 80}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
