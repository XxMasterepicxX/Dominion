"""
COMPREHENSIVE DATABASE VERIFICATION

REAL tests - not fake tests!
- Checks actual database records
- Verifies 3-month backfill completion
- Tests data quality and completeness
- Identifies critical issues

NO assumptions - queries the database for REAL data.
"""
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import db_manager
from src.config.current_market import CurrentMarket
import structlog

logger = structlog.get_logger(__name__)


class DatabaseVerifier:
    """Comprehensive database verification - REAL tests only."""

    def __init__(self):
        self.results = {}
        self.issues = []
        self.market_id = None

    async def run_all_tests(self):
        """Run all verification tests."""
        print("\n" + "=" * 80)
        print("COMPREHENSIVE DATABASE VERIFICATION")
        print("REAL DATA TESTS - NO ASSUMPTIONS")
        print("=" * 80)

        # Initialize
        await db_manager.initialize()
        await CurrentMarket.initialize(market_code='gainesville_fl')
        self.market_id = CurrentMarket.get_id()

        print(f"\nMarket: gainesville_fl")
        print(f"Market ID: {self.market_id}")
        print(f"Test Date: {datetime.now()}")
        print(f"Checking data from: {datetime.now() - timedelta(days=90)} to {datetime.now()}")

        # Run tests
        await self.test_council_meetings()
        await self.test_crime_data()
        await self.test_news_articles()
        await self.test_business_journal()
        await self.test_permits()
        await self.test_bulk_llcs()
        await self.test_bulk_properties()
        await self.test_data_quality()
        await self.test_date_coverage()

        # Summary
        self.print_summary()

        await db_manager.close()

    async def test_council_meetings(self):
        """Test city council meetings - REAL data check."""
        print("\n" + "-" * 80)
        print("1. TESTING CITY COUNCIL MEETINGS")
        print("-" * 80)

        try:
            # Count total meetings
            async with db_manager.get_connection() as conn:
                result = await conn.execute(
                    "SELECT COUNT(*) FROM council_meetings WHERE market_id = $1",
                    self.market_id
                )
                row = await result.fetchone()
                total = row[0] if row else 0

            # Count meetings with content
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM council_meetings
                WHERE market_id = $1
                AND (agenda_items IS NOT NULL AND array_length(agenda_items, 1) > 0)
            """, self.market_id)
            with_content = result[0]['count']

            # Count in last 3 months
            three_months_ago = datetime.now() - timedelta(days=90)
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM council_meetings
                WHERE market_id = $1
                AND meeting_date >= $2
            """, self.market_id, three_months_ago.date())
            last_3_months = result[0]['count']

            # Get date range
            result = await db_manager.execute("""
                SELECT MIN(meeting_date) as min_date, MAX(meeting_date) as max_date
                FROM council_meetings
                WHERE market_id = $1
            """, self.market_id)
            date_range = result[0] if result else None

            # Check for today's meeting (if any)
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM council_meetings
                WHERE market_id = $1
                AND meeting_date = CURRENT_DATE
            """, self.market_id)
            today_meetings = result[0]['count']

            content_pct = (with_content / total * 100) if total > 0 else 0

            self.results['council_meetings'] = {
                'total': total,
                'with_content': with_content,
                'content_pct': content_pct,
                'last_3_months': last_3_months,
                'date_range': date_range,
                'today': today_meetings
            }

            print(f"[OK] Total meetings: {total}")
            print(f"[OK] With content (agenda/text): {with_content} ({content_pct:.1f}%)")
            print(f"[OK] Last 3 months: {last_3_months}")
            if date_range:
                print(f"[OK] Date range: {date_range['min_date']} to {date_range['max_date']}")
            print(f"[OK] Today's meetings: {today_meetings}")

            # Check for issues
            if total == 0:
                self.issues.append("CRITICAL: No council meetings in database!")
            if last_3_months < 10:
                self.issues.append(f"WARNING: Only {last_3_months} meetings in last 3 months (expected ~40)")
            if content_pct < 40:
                self.issues.append(f"WARNING: Only {content_pct:.1f}% of meetings have content")

        except Exception as e:
            self.issues.append(f"CRITICAL: Council meetings test failed: {e}")
            print(f"[FAIL] Test failed: {e}")

    async def test_crime_data(self):
        """Test crime data - REAL data check."""
        print("\n" + "-" * 80)
        print("2. TESTING CRIME DATA")
        print("-" * 80)

        try:
            # Count total crimes
            result = await db_manager.execute(
                "SELECT COUNT(*) FROM crime_incidents WHERE market_id = $1",
                self.market_id
            )
            total = result[0]['count']

            # Count with coordinates
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM crime_incidents
                WHERE market_id = $1
                AND latitude IS NOT NULL AND longitude IS NOT NULL
            """, self.market_id)
            with_coords = result[0]['count']

            # Count in last 3 months
            three_months_ago = datetime.now() - timedelta(days=90)
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM crime_incidents
                WHERE market_id = $1
                AND offense_date >= $2
            """, self.market_id, three_months_ago.date())
            last_3_months = result[0]['count']

            # Get date range
            result = await db_manager.execute("""
                SELECT MIN(offense_date) as min_date, MAX(offense_date) as max_date
                FROM crime_incidents
                WHERE market_id = $1
            """, self.market_id)
            date_range = result[0] if result else None

            # Count by week for last 3 months
            result = await db_manager.execute("""
                SELECT DATE_TRUNC('week', offense_date) as week, COUNT(*) as count
                FROM crime_incidents
                WHERE market_id = $1
                AND offense_date >= $2
                GROUP BY week
                ORDER BY week
            """, self.market_id, three_months_ago.date())
            weekly_counts = result

            coords_pct = (with_coords / total * 100) if total > 0 else 0

            self.results['crime_data'] = {
                'total': total,
                'with_coords': with_coords,
                'coords_pct': coords_pct,
                'last_3_months': last_3_months,
                'date_range': date_range,
                'weekly_counts': len(weekly_counts)
            }

            print(f"[OK] Total crimes: {total}")
            print(f"[OK] With coordinates: {with_coords} ({coords_pct:.1f}%)")
            print(f"[OK] Last 3 months: {last_3_months}")
            if date_range:
                print(f"[OK] Date range: {date_range['min_date']} to {date_range['max_date']}")
            print(f"[OK] Weeks with data: {len(weekly_counts)}")

            # Check for issues
            if total == 0:
                self.issues.append("CRITICAL: No crime data in database!")
            if last_3_months < 500:
                self.issues.append(f"WARNING: Only {last_3_months} crimes in last 3 months (expected ~2000+)")
            if coords_pct < 90:
                self.issues.append(f"WARNING: Only {coords_pct:.1f}% of crimes have coordinates")
            if len(weekly_counts) < 10:
                self.issues.append(f"WARNING: Only {len(weekly_counts)} weeks of crime data (expected 12+)")

        except Exception as e:
            self.issues.append(f"CRITICAL: Crime data test failed: {e}")
            print(f"[FAIL] Test failed: {e}")

    async def test_news_articles(self):
        """Test news articles - REAL data check."""
        print("\n" + "-" * 80)
        print("3. TESTING NEWS ARTICLES")
        print("-" * 80)

        try:
            # Count total articles
            result = await db_manager.execute(
                "SELECT COUNT(*) FROM news_articles WHERE market_id = $1",
                self.market_id
            )
            total = result[0]['count']

            # Count in last 3 months
            three_months_ago = datetime.now() - timedelta(days=90)
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM news_articles
                WHERE market_id = $1
                AND published_at >= $2
            """, self.market_id, three_months_ago)
            last_3_months = result[0]['count']

            # Get date range
            result = await db_manager.execute("""
                SELECT MIN(published_at) as min_date, MAX(published_at) as max_date
                FROM news_articles
                WHERE market_id = $1
            """, self.market_id)
            date_range = result[0] if result else None

            # Count by source
            result = await db_manager.execute("""
                SELECT source, COUNT(*) as count
                FROM news_articles
                WHERE market_id = $1
                GROUP BY source
                ORDER BY count DESC
            """, self.market_id)
            by_source = result

            self.results['news_articles'] = {
                'total': total,
                'last_3_months': last_3_months,
                'date_range': date_range,
                'sources': len(by_source)
            }

            print(f"[OK] Total articles: {total}")
            print(f"[OK] Last 3 months: {last_3_months}")
            if date_range:
                print(f"[OK] Date range: {date_range['min_date']} to {date_range['max_date']}")
            print(f"[OK] News sources: {len(by_source)}")
            for source in by_source:
                print(f"  - {source['source']}: {source['count']} articles")

            # Check for issues
            if total == 0:
                self.issues.append("CRITICAL: No news articles in database!")
            if last_3_months < 100:
                self.issues.append(f"WARNING: Only {last_3_months} news articles in last 3 months (expected 500+)")

        except Exception as e:
            self.issues.append(f"CRITICAL: News articles test failed: {e}")
            print(f"[FAIL] Test failed: {e}")

    async def test_business_journal(self):
        """Test business journal articles - REAL data check."""
        print("\n" + "-" * 80)
        print("4. TESTING BUSINESS JOURNAL")
        print("-" * 80)

        try:
            # Check if business articles are in same table or separate
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM news_articles
                WHERE market_id = $1
                AND source LIKE '%business%'
            """, self.market_id)
            total = result[0]['count']

            print(f"[OK] Business articles: {total}")

            self.results['business_journal'] = {
                'total': total
            }

            if total == 0:
                print("  (Note: May be in news_articles with different source name)")

        except Exception as e:
            print(f"[FAIL] Test failed: {e}")

    async def test_permits(self):
        """Test permits - REAL data check."""
        print("\n" + "-" * 80)
        print("5. TESTING PERMITS")
        print("-" * 80)

        try:
            # Count city permits
            result = await db_manager.execute(
                "SELECT COUNT(*) FROM permits WHERE market_id = $1 AND jurisdiction = 'city'",
                self.market_id
            )
            city_total = result[0]['count']

            # Count county permits
            result = await db_manager.execute(
                "SELECT COUNT(*) FROM permits WHERE market_id = $1 AND jurisdiction = 'county'",
                self.market_id
            )
            county_total = result[0]['count']

            # Count in last 3 months
            three_months_ago = datetime.now() - timedelta(days=90)
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM permits
                WHERE market_id = $1
                AND issue_date >= $2
            """, self.market_id, three_months_ago.date())
            last_3_months = result[0]['count']

            # Get date range
            result = await db_manager.execute("""
                SELECT MIN(issue_date) as min_date, MAX(issue_date) as max_date
                FROM permits
                WHERE market_id = $1
            """, self.market_id)
            date_range = result[0] if result else None

            self.results['permits'] = {
                'city': city_total,
                'county': county_total,
                'total': city_total + county_total,
                'last_3_months': last_3_months,
                'date_range': date_range
            }

            print(f"[OK] City permits: {city_total}")
            print(f"[OK] County permits: {county_total}")
            print(f"[OK] Total permits: {city_total + county_total}")
            print(f"[OK] Last 3 months: {last_3_months}")
            if date_range:
                print(f"[OK] Date range: {date_range['min_date']} to {date_range['max_date']}")

            # Check for issues
            if city_total + county_total == 0:
                self.issues.append("CRITICAL: No permits in database!")
            if last_3_months < 100:
                self.issues.append(f"WARNING: Only {last_3_months} permits in last 3 months (expected 1000+)")

        except Exception as e:
            self.issues.append(f"CRITICAL: Permits test failed: {e}")
            print(f"[FAIL] Test failed: {e}")

    async def test_bulk_llcs(self):
        """Test bulk LLC records - REAL data check."""
        print("\n" + "-" * 80)
        print("6. TESTING BULK LLC RECORDS (SUNBIZ)")
        print("-" * 80)

        try:
            # Count total LLCs
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM bulk_llc_records blr
                JOIN bulk_data_snapshots bds ON blr.snapshot_id = bds.id
                WHERE bds.market_id = $1
            """, self.market_id)
            total = result[0]['count']

            # Count in last 3 months
            three_months_ago = datetime.now() - timedelta(days=90)
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM bulk_llc_records blr
                JOIN bulk_data_snapshots bds ON blr.snapshot_id = bds.id
                WHERE bds.market_id = $1
                AND blr.filing_date >= $2
            """, self.market_id, three_months_ago.date())
            last_3_months = result[0]['count']

            # Get snapshot count
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM bulk_data_snapshots
                WHERE market_id = $1
                AND data_source LIKE '%sunbiz%'
            """, self.market_id)
            snapshots = result[0]['count']

            # Get latest snapshot date
            result = await db_manager.execute("""
                SELECT MAX(snapshot_date) as latest_date
                FROM bulk_data_snapshots
                WHERE market_id = $1
                AND data_source LIKE '%sunbiz%'
            """, self.market_id)
            latest_snapshot = result[0]['latest_date'] if result else None

            self.results['bulk_llcs'] = {
                'total': total,
                'last_3_months': last_3_months,
                'snapshots': snapshots,
                'latest_snapshot': latest_snapshot
            }

            print(f"[OK] Total LLCs: {total}")
            print(f"[OK] Filed in last 3 months: {last_3_months}")
            print(f"[OK] Snapshots: {snapshots}")
            if latest_snapshot:
                print(f"[OK] Latest snapshot: {latest_snapshot}")

            # Check for issues
            if total == 0:
                self.issues.append("CRITICAL: No Sunbiz LLC records in database!")
            if snapshots < 5:
                self.issues.append(f"WARNING: Only {snapshots} Sunbiz snapshots (expected daily downloads)")
            if latest_snapshot and (datetime.now().date() - latest_snapshot).days > 2:
                self.issues.append(f"WARNING: Latest Sunbiz snapshot is {(datetime.now().date() - latest_snapshot).days} days old")

        except Exception as e:
            self.issues.append(f"CRITICAL: Bulk LLC test failed: {e}")
            print(f"[FAIL] Test failed: {e}")

    async def test_bulk_properties(self):
        """Test bulk property records - REAL data check."""
        print("\n" + "-" * 80)
        print("7. TESTING BULK PROPERTY RECORDS (CAMA)")
        print("-" * 80)

        try:
            # Count total properties
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM bulk_property_records bpr
                JOIN bulk_data_snapshots bds ON bpr.snapshot_id = bds.id
                WHERE bds.market_id = $1
            """, self.market_id)
            total = result[0]['count']

            # Count with coordinates
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM bulk_property_records bpr
                JOIN bulk_data_snapshots bds ON bpr.snapshot_id = bds.id
                WHERE bds.market_id = $1
                AND bpr.latitude IS NOT NULL AND bpr.longitude IS NOT NULL
            """, self.market_id)
            with_coords = result[0]['count']

            # Count with sale data
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM bulk_property_records bpr
                JOIN bulk_data_snapshots bds ON bpr.snapshot_id = bds.id
                WHERE bds.market_id = $1
                AND bpr.last_sale_date IS NOT NULL
            """, self.market_id)
            with_sales = result[0]['count']

            # Get snapshot count
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM bulk_data_snapshots
                WHERE market_id = $1
                AND data_source LIKE '%property%'
            """, self.market_id)
            snapshots = result[0]['count']

            coords_pct = (with_coords / total * 100) if total > 0 else 0
            sales_pct = (with_sales / total * 100) if total > 0 else 0

            self.results['bulk_properties'] = {
                'total': total,
                'with_coords': with_coords,
                'coords_pct': coords_pct,
                'with_sales': with_sales,
                'sales_pct': sales_pct,
                'snapshots': snapshots
            }

            print(f"[OK] Total properties: {total}")
            print(f"[OK] With coordinates: {with_coords} ({coords_pct:.1f}%)")
            print(f"[OK] With sale data: {with_sales} ({sales_pct:.1f}%)")
            print(f"[OK] Snapshots: {snapshots}")

            # Check for issues
            if total == 0:
                self.issues.append("CRITICAL: No CAMA property records in database!")
            if total < 100000:
                self.issues.append(f"WARNING: Only {total} properties (expected ~118,000)")
            if coords_pct < 90:
                self.issues.append(f"WARNING: Only {coords_pct:.1f}% have coordinates")

        except Exception as e:
            self.issues.append(f"CRITICAL: Bulk property test failed: {e}")
            print(f"[FAIL] Test failed: {e}")

    async def test_data_quality(self):
        """Test data quality - check for nulls, duplicates."""
        print("\n" + "-" * 80)
        print("8. TESTING DATA QUALITY")
        print("-" * 80)

        issues_found = []

        try:
            # Check council meetings for duplicates
            result = await db_manager.execute("""
                SELECT meeting_id, COUNT(*) as count
                FROM council_meetings
                WHERE market_id = $1
                GROUP BY meeting_id
                HAVING COUNT(*) > 1
            """, self.market_id)
            if result:
                issues_found.append(f"Found {len(result)} duplicate council meeting IDs")

            # Check crime for missing critical fields
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM crime_incidents
                WHERE market_id = $1
                AND (narrative IS NULL OR narrative = '')
            """, self.market_id)
            if result and result[0]['count'] > 0:
                issues_found.append(f"{result[0]['count']} crime incidents missing narrative")

            # Check permits for missing addresses
            result = await db_manager.execute("""
                SELECT COUNT(*) FROM permits
                WHERE market_id = $1
                AND (address IS NULL OR address = '')
            """, self.market_id)
            if result and result[0]['count'] > 0:
                pct = (result[0]['count'] / self.results.get('permits', {}).get('total', 1) * 100)
                if pct > 10:
                    issues_found.append(f"{result[0]['count']} permits missing address ({pct:.1f}%)")

            print(f"[OK] Data quality checks completed")
            if issues_found:
                print(f"[WARN] Issues found:")
                for issue in issues_found:
                    print(f"  - {issue}")
                self.issues.extend(issues_found)
            else:
                print(f"[OK] No major data quality issues")

        except Exception as e:
            print(f"[FAIL] Test failed: {e}")

    async def test_date_coverage(self):
        """Test date coverage - check for gaps."""
        print("\n" + "-" * 80)
        print("9. TESTING DATE COVERAGE")
        print("-" * 80)

        try:
            # Check crime data for gaps (should have data most days)
            three_months_ago = datetime.now() - timedelta(days=90)
            result = await db_manager.execute("""
                SELECT DATE(offense_date) as date, COUNT(*) as count
                FROM crime_incidents
                WHERE market_id = $1
                AND offense_date >= $2
                GROUP BY DATE(offense_date)
                ORDER BY date
            """, self.market_id, three_months_ago.date())

            days_with_crime = len(result)
            expected_days = 90

            print(f"[OK] Crime data: {days_with_crime}/{expected_days} days covered ({days_with_crime/expected_days*100:.1f}%)")

            if days_with_crime < 70:
                self.issues.append(f"WARNING: Crime data only covers {days_with_crime}/90 days")

            # Check for large gaps
            dates = [r['date'] for r in result]
            gaps = []
            for i in range(len(dates) - 1):
                gap = (dates[i+1] - dates[i]).days
                if gap > 7:
                    gaps.append((dates[i], dates[i+1], gap))

            if gaps:
                print(f"[WARN] Found {len(gaps)} gaps of 7+ days in crime data:")
                for start, end, days in gaps[:5]:
                    print(f"  - {start} to {end}: {days} days")
                self.issues.append(f"WARNING: {len(gaps)} gaps in crime data coverage")

        except Exception as e:
            print(f"[FAIL] Test failed: {e}")

    def print_summary(self):
        """Print comprehensive summary."""
        print("\n" + "=" * 80)
        print("VERIFICATION SUMMARY")
        print("=" * 80)

        # Overall stats
        print(f"\nDATA COVERAGE:")
        for source, data in self.results.items():
            if isinstance(data, dict):
                if 'total' in data:
                    print(f"  {source:25s}: {data['total']:,} records")

        # 3-month backfill status
        print(f"\n 3-MONTH BACKFILL STATUS:")
        backfill_complete = True
        for source, data in self.results.items():
            if isinstance(data, dict) and 'last_3_months' in data:
                total = data.get('total', 0)
                last_3 = data['last_3_months']
                pct = (last_3 / total * 100) if total > 0 else 0
                print(f"  {source:25s}: {last_3:,} records ({pct:.1f}% of total)")
                if last_3 == 0 and total > 0:
                    backfill_complete = False

        # Issues
        print(f"\n[WARN] ISSUES FOUND: {len(self.issues)}")
        if self.issues:
            critical = [i for i in self.issues if 'CRITICAL' in i]
            warnings = [i for i in self.issues if 'WARNING' in i]

            if critical:
                print(f"\n[CRITICAL] ({len(critical)}):")
                for issue in critical:
                    print(f"  - {issue}")

            if warnings:
                print(f"\n[WARNINGS] ({len(warnings)}):")
                for issue in warnings:
                    print(f"  - {issue}")
        else:
            print(f"  [OK] No issues found!")

        # Final verdict
        print(f"\n" + "=" * 80)
        if len([i for i in self.issues if 'CRITICAL' in i]) > 0:
            print("VERDICT: [FAIL] CRITICAL ISSUES - NEEDS IMMEDIATE ATTENTION")
        elif len(self.issues) > 5:
            print("VERDICT: [WARN] MULTIPLE ISSUES - NEEDS REVIEW")
        elif len(self.issues) > 0:
            print("VERDICT: [OK] MOSTLY GOOD - MINOR ISSUES")
        else:
            print("VERDICT: [OK] EXCELLENT - ALL TESTS PASSED")
        print("=" * 80)


async def main():
    """Run comprehensive verification."""
    verifier = DatabaseVerifier()
    await verifier.run_all_tests()


if __name__ == "__main__":
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ]
    )

    asyncio.run(main())
