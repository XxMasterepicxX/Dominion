#!/usr/bin/env python3
"""
Comprehensive check of all data available that the agent SHOULD be using
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import db_manager
from sqlalchemy import text
import json

async def comprehensive_check():
    await db_manager.initialize()
    async with db_manager.get_session() as session:

        # 1. Check what historical sales data we have (2008-2015 crash investigation)
        print('=' * 80)
        print('1. HISTORICAL SALES DATA (Why did values crash?)')
        print('=' * 80)
        result = await session.execute(
            text("""
            SELECT
                parcel_id,
                site_address,
                last_sale_date,
                last_sale_price,
                market_value,
                (market_value - last_sale_price) as value_change,
                CASE
                    WHEN last_sale_price > 0
                    THEN ROUND(((market_value - last_sale_price) / last_sale_price * 100)::numeric, 1)
                    ELSE NULL
                END as pct_change
            FROM bulk_property_records_gainesville_fl
            WHERE parcel_id IN ('06397-055-000', '06397-053-000', '06397-051-000')
            ORDER BY parcel_id
            """)
        )
        print("\nRecommended properties - sales history:")
        for row in result:
            print(f"\n{row[0]}: {row[1]}")
            if row[2]:
                print(f"  Last sale: {row[2]} for ${row[3]:,.0f}")
                print(f"  Current value: ${row[4]:,.0f}")
                print(f"  Change: ${row[5]:,.0f} ({row[6]}%)")
            else:
                print(f"  No sale data")

        # 2. Check D.R. Horton permit activity
        print('\n\n' + '=' * 80)
        print('2. D.R. HORTON PERMIT ACTIVITY (Are they building or just hoarding?)')
        print('=' * 80)
        result = await session.execute(
            text("""
            SELECT COUNT(*) as permit_count,
                   MIN(issued_date) as first_permit,
                   MAX(issued_date) as last_permit,
                   SUM(CASE WHEN status = 'Final' THEN 1 ELSE 0 END) as completed_count
            FROM permits_gainesville_fl
            WHERE owner_name = 'D R HORTON INC'
            """)
        )
        row = result.first()
        print(f"\nD.R. Horton permits: {row[0]} total")
        if row[0] > 0:
            print(f"Date range: {row[1]} to {row[2]}")
            print(f"Completed (Final status): {row[3]}")
        else:
            print("  NO PERMIT ACTIVITY FOUND")
            print("  This means D.R. Horton is HOARDING land, not building!")

        # Check contractor permits
        result = await session.execute(
            text("""
            SELECT permit_number, permit_type, project_description, issued_date, project_value, status
            FROM permits_gainesville_fl
            WHERE owner_name = 'D R HORTON INC'
            ORDER BY issued_date DESC
            LIMIT 5
            """)
        )
        rows = result.fetchall()
        if rows:
            print(f"\nRecent D.R. Horton permits ({len(rows)} shown):")
            for row in rows:
                value = f'${row[4]:,.0f}' if row[4] else 'N/A'
                desc = row[2][:50] if row[2] else 'N/A'
                print(f"  {row[0]}: {row[1]} - {desc}")
                print(f"    Issued: {row[3]}, Value: {value}, Status: {row[5]}")

        # 3. Check D.R. Horton sales activity (are they selling their properties?)
        print('\n\n' + '=' * 80)
        print('3. D.R. HORTON SALES ACTIVITY (Are they selling properties?)')
        print('=' * 80)
        result = await session.execute(
            text("""
            SELECT COUNT(*),
                   COUNT(CASE WHEN last_sale_date > '2024-01-01' THEN 1 END) as recent_sales
            FROM bulk_property_records_gainesville_fl
            WHERE owner_name = 'D R HORTON INC'
            """)
        )
        row = result.first()
        print(f"\nD.R. Horton currently owns: {row[0]} properties")
        print(f"Sales in 2024: {row[1]}")
        print(f"(Note: These are properties they OWN now, not ones they've sold)")

        # 4. Check recent vacant lot sales comps
        print('\n\n' + '=' * 80)
        print('4. RECENT VACANT LOT SALES (Comps for exit strategy validation)')
        print('=' * 80)
        result = await session.execute(
            text("""
            SELECT
                parcel_id,
                site_address,
                last_sale_date,
                last_sale_price,
                lot_size_acres,
                CASE
                    WHEN lot_size_acres > 0
                    THEN ROUND((last_sale_price / lot_size_acres)::numeric, 0)
                    ELSE NULL
                END as price_per_acre
            FROM bulk_property_records_gainesville_fl
            WHERE property_type = 'VACANT'
            AND last_sale_date > '2023-01-01'
            AND last_sale_price > 5000
            AND last_sale_price < 100000
            AND lot_size_acres BETWEEN 0.25 AND 0.5
            ORDER BY last_sale_date DESC
            LIMIT 10
            """)
        )
        rows = result.fetchall()
        print(f"\nRecent vacant lot sales (2023+, similar size, under $100k): {len(rows)} found")
        for row in rows:
            ppa = f'${row[5]:,.0f}/acre' if row[5] else 'N/A'
            print(f"\n{row[0]}: {row[1]}")
            print(f"  Sold {row[2]}: ${row[3]:,.0f} ({row[4]:.2f} acres) = {ppa}")

        # Calculate average
        if rows:
            avg_price = sum(row[3] for row in rows) / len(rows)
            avg_ppa = sum(row[5] for row in rows if row[5]) / len([r for r in rows if r[5]])
            print(f"\nAVERAGE COMP: ${avg_price:,.0f} (${avg_ppa:,.0f}/acre)")
            print(f"Agent's projection: $40k-$60k per lot")
            print(f"Actual market: ${avg_price:,.0f} average")

        # 5. Check neighborhood permit activity
        print('\n\n' + '=' * 80)
        print('5. NEIGHBORHOOD PERMIT ACTIVITY (Is area active or dead?)')
        print('=' * 80)
        result = await session.execute(
            text("""
            SELECT COUNT(*) as permit_count,
                   MIN(issued_date) as first_permit,
                   MAX(issued_date) as last_permit,
                   COUNT(DISTINCT parcel_id) as unique_parcels
            FROM permits_gainesville_fl
            WHERE parcel_id LIKE '06397%'
            AND issued_date > '2020-01-01'
            """)
        )
        row = result.first()
        print(f"\nNeighborhood 06397-xxx permits (2020+): {row[0]} total")
        if row[0] > 0:
            print(f"Date range: {row[1]} to {row[2]}")
            print(f"Unique parcels: {row[3]}")
        else:
            print("  WARNING: NO RECENT PERMIT ACTIVITY")
            print("  This neighborhood may be DEAD for development!")

        # Show recent permits
        result = await session.execute(
            text("""
            SELECT permit_number, parcel_id, site_address, permit_type, issued_date, status
            FROM permits_gainesville_fl
            WHERE parcel_id LIKE '06397%'
            AND issued_date > '2020-01-01'
            ORDER BY issued_date DESC
            LIMIT 5
            """)
        )
        rows = result.fetchall()
        if rows:
            print(f"\nRecent neighborhood permits ({len(rows)} shown):")
            for row in rows:
                print(f"  {row[0]}: {row[2]}")
                print(f"    Type: {row[3]}, Issued: {row[4]}, Status: {row[5]}")

        # 6. Check neighborhood market stats
        print('\n\n' + '=' * 80)
        print('6. NEIGHBORHOOD MARKET STATS (The $357k mystery)')
        print('=' * 80)
        result = await session.execute(
            text("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN property_type = 'VACANT' THEN 1 END) as vacant,
                COUNT(CASE WHEN property_type != 'VACANT' THEN 1 END) as developed,
                AVG(market_value) as avg_all,
                AVG(CASE WHEN property_type != 'VACANT' AND market_value > 0 THEN market_value END) as avg_developed
            FROM bulk_property_records_gainesville_fl
            WHERE parcel_id LIKE '06397%'
            """)
        )
        row = result.first()
        print(f"\nNeighborhood 06397-xxx:")
        print(f"  Total properties: {row[0]}")
        print(f"  Vacant: {row[1]}")
        print(f"  Developed: {row[2]}")
        print(f"  Average value (all): ${row[3]:,.2f}")
        print(f"  Average value (developed only): ${row[4]:,.2f}")
        print(f"\n  Agent claimed: $357,011")
        print(f"  Actual: ${row[4]:,.2f}")
        print(f"  Error: ${row[4] - 357011:,.2f} ({((row[4] - 357011) / 357011 * 100):.1f}%)")

    await db_manager.close()

if __name__ == '__main__':
    asyncio.run(comprehensive_check())
