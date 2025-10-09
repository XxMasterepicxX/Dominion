"""
REAL DATABASE VERIFICATION - No fake tests!

Checks actual data in the database:
1. Counts real records
2. Verifies date ranges
3. Checks data quality
4. Tests 3-month backfill completion
"""
import sys
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import db_manager
from src.config.current_market import CurrentMarket


async def main():
    print("=" * 80)
    print("REAL DATABASE VERIFICATION")
    print("=" * 80)

    await db_manager.initialize()
    await CurrentMarket.initialize(market_code='gainesville_fl')
    market_id = CurrentMarket.get_id()

    print(f"\nMarket ID: {market_id}")
    print(f"Test Date: {datetime.now().date()}")
    print(f"3-Month Period: {(datetime.now() - timedelta(days=90)).date()} to {datetime.now().date()}")

    issues = []
    three_months_ago = (datetime.now() - timedelta(days=90)).date()

    async with db_manager.get_connection() as conn:

        # 1. COUNCIL MEETINGS
        print(f"\n" + "-" * 80)
        print("1. COUNCIL MEETINGS")
        print("-" * 80)

        result = await conn.fetch("SELECT COUNT(*) FROM council_meetings WHERE market_id = $1", market_id)
        total_meetings = result[0][0]

        result = await conn.fetch("""
            SELECT COUNT(*) FROM council_meetings
            WHERE market_id = $1
            AND (agenda_items IS NOT NULL AND agenda_items::text != '[]' AND agenda_items::text != 'null')
        """, market_id)
        meetings_with_content = result[0][0]

        result = await conn.fetch("""
            SELECT COUNT(*) FROM council_meetings
            WHERE market_id = $1
            AND meeting_date >= $2
        """, market_id, three_months_ago)
        meetings_3m = result[0][0]

        result = await conn.fetch("""
            SELECT MIN(meeting_date), MAX(meeting_date)
            FROM council_meetings
            WHERE market_id = $1
        """, market_id)
        date_range = result[0] if result else (None, None)

        content_pct = (meetings_with_content / total_meetings * 100) if total_meetings > 0 else 0

        print(f"  Total meetings: {total_meetings}")
        print(f"  With content: {meetings_with_content} ({content_pct:.1f}%)")
        print(f"  Last 3 months: {meetings_3m}")
        print(f"  Date range: {date_range[0]} to {date_range[1]}")

        if total_meetings == 0:
            issues.append("CRITICAL: No council meetings!")
        elif meetings_3m < 10:
            issues.append(f"WARNING: Only {meetings_3m} meetings in last 3 months (expected 30-40)")
        if content_pct < 40:
            issues.append(f"WARNING: Only {content_pct:.1f}% meetings have content")

        # 2. CRIME REPORTS
        print(f"\n" + "-" * 80)
        print("2. CRIME REPORTS")
        print("-" * 80)

        result = await conn.fetch("SELECT COUNT(*) FROM crime_reports WHERE market_id = $1", market_id)
        total_crime = result[0][0]

        result = await conn.fetch("""
            SELECT COUNT(*) FROM crime_reports
            WHERE market_id = $1
            AND latitude IS NOT NULL AND longitude IS NOT NULL
        """, market_id)
        crime_with_coords = result[0][0]

        result = await conn.fetch("""
            SELECT COUNT(*) FROM crime_reports
            WHERE market_id = $1
            AND incident_date >= $2
        """, market_id, three_months_ago)
        crime_3m = result[0][0]

        result = await conn.fetch("""
            SELECT MIN(incident_date), MAX(incident_date)
            FROM crime_reports
            WHERE market_id = $1
        """, market_id)
        crime_range = result[0] if result else (None, None)

        coords_pct = (crime_with_coords / total_crime * 100) if total_crime > 0 else 0

        print(f"  Total crimes: {total_crime}")
        print(f"  With coordinates: {crime_with_coords} ({coords_pct:.1f}%)")
        print(f"  Last 3 months: {crime_3m}")
        print(f"  Date range: {crime_range[0]} to {crime_range[1]}")

        if total_crime == 0:
            issues.append("CRITICAL: No crime data!")
        elif crime_3m < 500:
            issues.append(f"WARNING: Only {crime_3m} crimes in last 3 months (expected 1500+)")
        if coords_pct < 90:
            issues.append(f"WARNING: Only {coords_pct:.1f}% crimes have coordinates")

        # 3. NEWS ARTICLES
        print(f"\n" + "-" * 80)
        print("3. NEWS ARTICLES")
        print("-" * 80)

        result = await conn.fetch("SELECT COUNT(*) FROM news_articles WHERE market_id = $1", market_id)
        total_news = result[0][0]

        result = await conn.fetch("""
            SELECT COUNT(*) FROM news_articles
            WHERE market_id = $1
            AND published_date >= $2
        """, market_id, datetime.now() - timedelta(days=90))
        news_3m = result[0][0]

        result = await conn.fetch("""
            SELECT source, COUNT(*)
            FROM news_articles
            WHERE market_id = $1
            GROUP BY source
        """, market_id)

        print(f"  Total articles: {total_news}")
        print(f"  Last 3 months: {news_3m}")
        print(f"  Sources: {len(result)}")
        for row in result:
            print(f"    - {row[0]}: {row[1]} articles")

        if total_news == 0:
            issues.append("CRITICAL: No news articles!")
        elif news_3m < 100:
            issues.append(f"WARNING: Only {news_3m} news in last 3 months (expected 500+)")

        # 4. PERMITS
        print(f"\n" + "-" * 80)
        print("4. PERMITS")
        print("-" * 80)

        result = await conn.fetch("SELECT COUNT(*) FROM permits WHERE market_id = $1", market_id)
        total_permits = result[0][0]

        result = await conn.fetch("""
            SELECT COUNT(*) FROM permits
            WHERE market_id = $1
            AND jurisdiction = 'city'
        """, market_id)
        city_permits = result[0][0]

        result = await conn.fetch("""
            SELECT COUNT(*) FROM permits
            WHERE market_id = $1
            AND jurisdiction = 'county'
        """, market_id)
        county_permits = result[0][0]

        result = await conn.fetch("""
            SELECT COUNT(*) FROM permits
            WHERE market_id = $1
            AND issued_date >= $2
        """, market_id, three_months_ago)
        permits_3m = result[0][0]

        result = await conn.fetch("""
            SELECT MIN(issued_date), MAX(issued_date)
            FROM permits
            WHERE market_id = $1
        """, market_id)
        permits_range = result[0] if result else (None, None)

        print(f"  Total permits: {total_permits}")
        print(f"  City: {city_permits}")
        print(f"  County: {county_permits}")
        print(f"  Last 3 months: {permits_3m}")
        print(f"  Date range: {permits_range[0]} to {permits_range[1]}")

        if total_permits == 0:
            issues.append("CRITICAL: No permits!")
        elif permits_3m < 100:
            issues.append(f"WARNING: Only {permits_3m} permits in last 3 months (expected 1000+)")

        # 5. BULK LLCs (Sunbiz)
        print(f"\n" + "-" * 80)
        print("5. BULK LLCs (SUNBIZ)")
        print("-" * 80)

        result = await conn.fetch("""
            SELECT COUNT(*) FROM bulk_llc_records blr
            JOIN bulk_data_snapshots bds ON blr.snapshot_id = bds.id
            WHERE bds.market_id = $1
        """, market_id)
        total_llcs = result[0][0]

        result = await conn.fetch("""
            SELECT COUNT(*) FROM bulk_llc_records blr
            JOIN bulk_data_snapshots bds ON blr.snapshot_id = bds.id
            WHERE bds.market_id = $1
            AND blr.filing_date >= $2
        """, market_id, three_months_ago)
        llcs_3m = result[0][0]

        result = await conn.fetch("""
            SELECT COUNT(DISTINCT bds.id) FROM bulk_data_snapshots bds
            WHERE bds.market_id = $1
            AND bds.data_source LIKE '%sunbiz%'
        """, market_id)
        llc_snapshots = result[0][0]

        result = await conn.fetch("""
            SELECT MAX(snapshot_date) FROM bulk_data_snapshots
            WHERE market_id = $1
            AND data_source LIKE '%sunbiz%'
        """, market_id)
        latest_llc = result[0][0] if result else None

        print(f"  Total LLCs: {total_llcs}")
        print(f"  Filed in last 3 months: {llcs_3m}")
        print(f"  Snapshots: {llc_snapshots}")
        print(f"  Latest snapshot: {latest_llc}")

        if total_llcs == 0:
            issues.append("CRITICAL: No Sunbiz LLCs!")
        elif llc_snapshots < 3:
            issues.append(f"WARNING: Only {llc_snapshots} Sunbiz snapshots (expected daily)")

        # 6. BULK PROPERTIES (CAMA)
        print(f"\n" + "-" * 80)
        print("6. BULK PROPERTIES (CAMA)")
        print("-" * 80)

        result = await conn.fetch("""
            SELECT COUNT(*) FROM bulk_property_records bpr
            JOIN bulk_data_snapshots bds ON bpr.snapshot_id = bds.id
            WHERE bds.market_id = $1
        """, market_id)
        total_props = result[0][0]

        result = await conn.fetch("""
            SELECT COUNT(*) FROM bulk_property_records bpr
            JOIN bulk_data_snapshots bds ON bpr.snapshot_id = bds.id
            WHERE bds.market_id = $1
            AND bpr.latitude IS NOT NULL AND bpr.longitude IS NOT NULL
        """, market_id)
        props_with_coords = result[0][0]

        coords_pct = (props_with_coords / total_props * 100) if total_props > 0 else 0

        print(f"  Total properties: {total_props}")
        print(f"  With coordinates: {props_with_coords} ({coords_pct:.1f}%)")

        if total_props == 0:
            issues.append("CRITICAL: No CAMA properties!")
        elif total_props < 100000:
            issues.append(f"WARNING: Only {total_props} properties (expected ~118,000)")

    # SUMMARY
    print(f"\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"\nDATA COUNTS:")
    print(f"  Council Meetings: {total_meetings:,} ({meetings_3m:,} in last 3 months)")
    print(f"  Crime Reports: {total_crime:,} ({crime_3m:,} in last 3 months)")
    print(f"  News Articles: {total_news:,} ({news_3m:,} in last 3 months)")
    print(f"  Permits: {total_permits:,} ({permits_3m:,} in last 3 months)")
    print(f"  Sunbiz LLCs: {total_llcs:,} ({llcs_3m:,} in last 3 months)")
    print(f"  CAMA Properties: {total_props:,}")

    print(f"\nISSUES FOUND: {len(issues)}")
    if issues:
        critical = [i for i in issues if 'CRITICAL' in i]
        warnings = [i for i in issues if 'WARNING' in i]

        if critical:
            print(f"\nCRITICAL ({len(critical)}):")
            for issue in critical:
                print(f"  - {issue}")

        if warnings:
            print(f"\nWARNINGS ({len(warnings)}):")
            for issue in warnings:
                print(f"  - {issue}")
    else:
        print("  No issues found!")

    print(f"\n" + "=" * 80)
    if len([i for i in issues if 'CRITICAL' in i]) > 0:
        print("VERDICT: CRITICAL ISSUES - NEEDS IMMEDIATE ATTENTION")
    elif len(issues) > 3:
        print("VERDICT: MULTIPLE ISSUES - NEEDS REVIEW")
    elif len(issues) > 0:
        print("VERDICT: MINOR ISSUES - MOSTLY GOOD")
    else:
        print("VERDICT: ALL GOOD - NO ISSUES")
    print("=" * 80)

    await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
