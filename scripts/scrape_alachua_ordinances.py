#!/usr/bin/env python3
"""
Scrape Alachua County Ordinances

Scrapes ordinances for ALL municipalities in Alachua County:
- Alachua
- Archer
- Gainesville
- Hawthorne
- High Springs
- La Crosse
- Micanopy
- Newberry
- Waldo

This provides comprehensive county-level ordinance coverage for
analyzing regulatory differences and identifying opportunities.

Usage:
    python scripts/scrape_alachua_ordinances.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.loader import load_market_config
from src.scrapers.ordinances import run_municode_scraper


async def main():
    print("=" * 80)
    print("ALACHUA COUNTY ORDINANCES SCRAPER")
    print("=" * 80)
    print()
    print("This will scrape ordinances for ALL 9 Alachua County municipalities:")
    print("  1. Alachua")
    print("  2. Archer")
    print("  3. Gainesville")
    print("  4. Hawthorne")
    print("  5. High Springs")
    print("  6. La Crosse")
    print("  7. Micanopy")
    print("  8. Newberry")
    print("  9. Waldo")
    print()
    print("Estimated time: ~5-10 minutes")
    print("=" * 80)
    print()

    # Confirm
    response = input("Continue? [y/N]: ")
    if response.lower() != "y":
        print("Aborted.")
        return

    # Load Gainesville config as base (any Alachua market would work)
    config = load_market_config("gainesville_fl")

    # Override to county scope
    config.scrapers.ordinances.scope = "county"
    config.scrapers.ordinances.output_dir = "data/ordinances/alachua_county"

    print("\n🚀 Starting county-wide scrape...\n")

    # Run scraper
    results = await run_municode_scraper(config)

    # Summary
    print("\n\n" + "=" * 80)
    print("ALACHUA COUNTY SCRAPE COMPLETE")
    print("=" * 80)

    successful = [r for r in results if r.get("status") == "success"]
    failed = [r for r in results if r.get("status") != "success"]

    print(f"\n✅ Successfully scraped: {len(successful)}/{len(results)} municipalities")

    if successful:
        total_ordinances = sum(r.get('ordinances_scraped', 0) for r in successful)
        total_size = sum(r.get('total_size', 0) for r in successful)
        print(f"📄 Total ordinances: {total_ordinances}")
        print(f"💾 Total data: {total_size:,} chars ({total_size/1024/1024:.1f} MB)")

        print("\n📊 By Municipality:")
        for r in successful:
            name = r.get('municipality', 'Unknown')
            ords = r.get('ordinances_scraped', 0)
            size = r.get('total_size', 0)
            print(f"  • {name:20} - {ords:2} ordinances, {size:8,} chars")

    if failed:
        print(f"\n⚠️  Failed: {len(failed)} municipalities")
        for r in failed:
            name = r.get('municipality', 'Unknown')
            status = r.get('status', 'unknown')
            print(f"  • {name:20} - {status}")

    print(f"\n📁 Output directory: data/ordinances/alachua_county/")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
