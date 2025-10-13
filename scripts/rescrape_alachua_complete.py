#!/usr/bin/env python3
"""
Re-scrape all Alachua County municipalities with 728 comprehensive keywords

This will run in the background and save results to data/ordinances_complete/
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.ordinances.municode.scraper import scrape_municipality_hierarchical
from src.scrapers.ordinances.municode.get_cities import get_alachua_county_municipalities
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig

async def main():
    start_time = datetime.now()

    print("=" * 80)
    print("ALACHUA COUNTY COMPLETE RE-SCRAPE")
    print("With 728 comprehensive real estate keywords")
    print("=" * 80)

    # Get all Alachua County municipalities
    municipalities = get_alachua_county_municipalities()

    print(f"\nMunicipalities to scrape: {len(municipalities)}")
    for m in municipalities:
        print(f"  • {m['name']}")

    # Output to new directory
    output_dir = Path("data/ordinances_complete")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nOutput directory: {output_dir}")
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Configure browser
    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        extra_args=['--disable-blink-features=AutomationControlled']
    )

    # Run scraper for all municipalities
    results = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for i, municipality in enumerate(municipalities, 1):
            print(f"\n[{i}/{len(municipalities)}] Processing {municipality['name']}...")

            try:
                result = await scrape_municipality_hierarchical(
                    crawler,
                    municipality,
                    str(output_dir)
                )
                results.append(result)

                if result['status'] == 'success':
                    print(f"✓ {municipality['name']}: {result.get('ordinances_scraped', 0)} ordinances, {result.get('total_size', 0):,} chars")
                else:
                    print(f"✗ {municipality['name']}: {result['status']}")

            except Exception as e:
                print(f"✗ {municipality['name']}: ERROR - {e}")
                results.append({
                    "municipality": municipality['name'],
                    "status": "error",
                    "error": str(e)
                })

    # Print summary
    end_time = datetime.now()
    duration = end_time - start_time

    print("\n" + "=" * 80)
    print("COMPLETE SCRAPE SUMMARY")
    print("=" * 80)

    successful = [r for r in results if r.get('status') == 'success']
    failed = [r for r in results if r.get('status') != 'success']

    print(f"\nTotal municipalities: {len(municipalities)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")

    if successful:
        total_ordinances = sum(r.get('ordinances_scraped', 0) for r in successful)
        total_size = sum(r.get('total_size', 0) for r in successful)
        print(f"\nTotal ordinances scraped: {total_ordinances}")
        print(f"Total data collected: {total_size:,} chars ({total_size/1024/1024:.1f} MB)")

    print(f"\nStarted: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Ended: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {duration}")

    # Save results log
    import json
    log_file = output_dir / f"scrape_log_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, 'w') as f:
        json.dump({
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration.total_seconds(),
            'municipalities': len(municipalities),
            'successful': len(successful),
            'failed': len(failed),
            'results': results
        }, f, indent=2)

    print(f"\nLog saved to: {log_file}")

if __name__ == "__main__":
    asyncio.run(main())
