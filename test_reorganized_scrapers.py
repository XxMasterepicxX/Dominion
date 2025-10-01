#!/usr/bin/env python3
"""
Test script to verify all reorganized scrapers can be imported and instantiated.
Run this from the project root directory.
"""
import sys
from pathlib import Path

# Add project root to path so we can import src as a package
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all scrapers can be imported."""
    print("=" * 80)
    print("TESTING REORGANIZED SCRAPER IMPORTS")
    print("=" * 80)

    results = []

    # Test importing from main package
    print("\n[1/11] Testing main package imports...")
    try:
        from src.scrapers import (
            CityPermitsScraper,
            CountyPermitsScraper,
            CouncilScraper,
            CensusScraper,
            BusinessNewsScraper,
            NewsRSSScraper,
            CrimeDataScraper,
            GISScraper,
            PropertyAppraiserScraper,
            SunbizScraper,
        )
        print("  [+] All scrapers imported from main package")
        results.append(("Main Package Imports", True))
    except Exception as e:
        print(f"  [X] Failed to import from main package: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Main Package Imports", False))
        return results

    # Test instantiation with config
    print("\n[2/11] Loading market config...")
    try:
        from src.config import load_market_config
        config = load_market_config('gainesville_fl')
        print(f"  [+] Config loaded for {config.market.name}")
        results.append(("Config Loading", True))
    except Exception as e:
        print(f"  [X] Failed to load config: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Config Loading", False))
        return results

    # Test each scraper instantiation
    scrapers_to_test = [
        ("City Permits", CityPermitsScraper, True),  # Uses patchright
        ("County Permits", CountyPermitsScraper, True),  # Uses patchright
        ("City Council", CouncilScraper, False),  # No patchright
        ("Census Demographics", CensusScraper, False),  # No patchright
        ("Business Journal", BusinessNewsScraper, False),  # No patchright
        ("News RSS", NewsRSSScraper, False),  # No patchright
        ("Crime Data", CrimeDataScraper, False),  # No patchright
        ("GIS", GISScraper, False),  # No patchright
        ("Property Appraiser", PropertyAppraiserScraper, False),  # No patchright
    ]

    for i, (name, ScraperClass, uses_patchright) in enumerate(scrapers_to_test, start=3):
        print(f"\n[{i}/11] Testing {name}...")
        try:
            if uses_patchright:
                scraper = ScraperClass(config, headless=True)
            else:
                scraper = ScraperClass(config)
            print(f"  [+] {name} instantiated successfully")
            results.append((name, True))
        except Exception as e:
            print(f"  [X] Failed to instantiate {name}: {e}")
            results.append((name, False))

    # Test Sunbiz (no config required)
    print(f"\n[12/11] Testing Sunbiz...")
    try:
        scraper = SunbizScraper()
        print(f"  [+] Sunbiz instantiated successfully")
        results.append(("Sunbiz", True))
    except Exception as e:
        print(f"  [X] Failed to instantiate Sunbiz: {e}")
        results.append(("Sunbiz", False))

    return results


def print_summary(results):
    """Print test summary."""
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for name, success in results:
        status = "[+]" if success else "[X]"
        print(f"{status} {name}")

    total = len(results)
    passed = sum(1 for _, success in results if success)

    print(f"\nPassed: {passed}/{total}")

    return passed == total


if __name__ == "__main__":
    try:
        results = test_imports()
        success = print_summary(results)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[X] Test script failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
