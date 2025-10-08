#!/usr/bin/env python3
"""
Find SPECIFIC land parcels to buy for resale to D.R. Horton

This script will:
1. Find all D.R. Horton's vacant land parcels
2. Identify geographic clusters
3. Find adjacent vacant parcels NOT owned by them
4. Give specific parcel IDs, addresses, and prices
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.database.connection import db_manager


async def analyze_dr_horton_holdings():
    """Find D.R. Horton's actual parcels and identify opportunities"""

    print("=" * 80)
    print("FINDING SPECIFIC LAND OPPORTUNITIES FOR D.R. HORTON RESALE")
    print("=" * 80)

    await db_manager.initialize()

    async with db_manager.get_session() as session:

        # Step 1: Find ALL D.R. Horton properties
        print("\n1. D.R. HORTON'S CURRENT HOLDINGS:")
        print("-" * 80)

        result = await session.execute(text("""
            SELECT
                parcel_id,
                site_address,
                property_type,
                market_value,
                lot_size_acres,
                latitude,
                longitude,
                last_sale_date
            FROM bulk_property_records
            WHERE owner_name ILIKE '%D R HORTON%'
               OR owner_name ILIKE '%DR HORTON%'
               OR owner_name ILIKE '%HORTON%D%R%'
            ORDER BY last_sale_date DESC NULLS LAST
        """))

        horton_parcels = result.fetchall()
        print(f"Total D.R. Horton properties found: {len(horton_parcels)}")

        if len(horton_parcels) == 0:
            print("\nNo D.R. Horton properties found. Trying alternative search...")

            # Try searching for other major developers
            result = await session.execute(text("""
                SELECT DISTINCT owner_name, COUNT(*) as count
                FROM bulk_property_records
                WHERE (owner_name ILIKE '%LLC%'
                   OR owner_name ILIKE '%INC%'
                   OR owner_name ILIKE '%CORP%'
                   OR owner_name ILIKE '%BUILDER%'
                   OR owner_name ILIKE '%DEVELOPMENT%'
                   OR owner_name ILIKE '%HOMES%')
                  AND property_type ILIKE '%vacant%'
                GROUP BY owner_name
                HAVING COUNT(*) >= 10
                ORDER BY COUNT(*) DESC
                LIMIT 10
            """))

            print("\nTop developers with vacant land (10+ parcels):")
            for row in result:
                print(f"  {row[0]}: {row[1]} vacant parcels")

            print("\nLet's analyze the top developer instead...")
            return

        # Separate by property type
        vacant = [p for p in horton_parcels if 'VACANT' in (p[2] or '').upper()]
        developed = [p for p in horton_parcels if 'VACANT' not in (p[2] or '').upper()]

        print(f"  Vacant parcels: {len(vacant)}")
        print(f"  Developed properties: {len(developed)}")

        # Step 2: Show sample vacant parcels
        print("\n2. SAMPLE D.R. HORTON VACANT PARCELS (First 10):")
        print("-" * 80)

        for i, p in enumerate(vacant[:10], 1):
            print(f"\n{i}. Parcel ID: {p[0]}")
            print(f"   Address: {p[1] or 'N/A'}")
            print(f"   Type: {p[2]}")
            print(f"   Value: ${p[3]:,.0f}" if p[3] else "   Value: N/A")
            print(f"   Size: {p[4]:.2f} acres" if p[4] else "   Size: N/A")
            print(f"   Coordinates: {p[5]}, {p[6]}" if p[5] and p[6] else "   Coordinates: N/A")
            print(f"   Last Sale: {p[7]}" if p[7] else "   Last Sale: N/A")

        # Step 3: Identify geographic clusters
        print("\n3. GEOGRAPHIC CLUSTERING ANALYSIS:")
        print("-" * 80)

        # Find areas where D.R. Horton has multiple parcels
        result = await session.execute(text("""
            SELECT
                SUBSTRING(site_address FROM '.*?(SW|SE|NW|NE) [0-9]+') as street_pattern,
                COUNT(*) as parcel_count,
                AVG(market_value) as avg_value,
                SUM(lot_size_acres) as total_acres,
                array_agg(parcel_id) as parcel_ids
            FROM bulk_property_records
            WHERE (owner_name ILIKE '%D R HORTON%'
               OR owner_name ILIKE '%DR HORTON%'
               OR owner_name ILIKE '%HORTON%D%R%')
              AND property_type ILIKE '%vacant%'
              AND site_address IS NOT NULL
              AND site_address ~ '(SW|SE|NW|NE) [0-9]+'
            GROUP BY street_pattern
            HAVING COUNT(*) >= 2
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """))

        clusters = result.fetchall()
        print(f"\nFound {len(clusters)} street clusters where D.R. Horton owns 2+ parcels:")

        for cluster in clusters:
            print(f"\n  {cluster[0]}")
            print(f"    D.R. Horton owns: {cluster[1]} parcels here")
            print(f"    Average value: ${cluster[2]:,.0f}" if cluster[2] else "    Average value: N/A")
            print(f"    Total acres: {cluster[3]:.2f}" if cluster[3] else "    Total acres: N/A")

        # Step 4: Find opportunity parcels (vacant land near D.R. Horton holdings)
        print("\n4. OPPORTUNITY PARCELS (Vacant land adjacent to D.R. Horton clusters):")
        print("-" * 80)

        if clusters:
            # Take the top cluster
            top_cluster = clusters[0][0]
            print(f"\nAnalyzing opportunities near: {top_cluster}")

            result = await session.execute(text("""
                SELECT
                    parcel_id,
                    site_address,
                    owner_name,
                    market_value,
                    lot_size_acres,
                    latitude,
                    longitude,
                    land_zoning_desc
                FROM bulk_property_records
                WHERE property_type ILIKE '%vacant%'
                  AND site_address ILIKE :pattern
                  AND owner_name NOT ILIKE '%D R HORTON%'
                  AND owner_name NOT ILIKE '%DR HORTON%'
                  AND market_value IS NOT NULL
                  AND market_value > 0
                  AND market_value < 100000
                  AND lot_size_acres > 0.25
                ORDER BY market_value / NULLIF(lot_size_acres, 0)
                LIMIT 15
            """), {'pattern': f'%{top_cluster}%'})

            opportunities = result.fetchall()

            if opportunities:
                print(f"\nFound {len(opportunities)} opportunity parcels:")

                for i, opp in enumerate(opportunities, 1):
                    print(f"\n{'='*80}")
                    print(f"OPPORTUNITY #{i}")
                    print(f"{'='*80}")
                    print(f"Parcel ID: {opp[0]}")
                    print(f"Address: {opp[1]}")
                    print(f"Current Owner: {opp[2]}")
                    print(f"Market Value: ${opp[3]:,.0f}" if opp[3] else "Market Value: N/A")
                    print(f"Lot Size: {opp[4]:.2f} acres" if opp[4] else "Lot Size: N/A")
                    print(f"Price per Acre: ${opp[3]/opp[4]:,.0f}" if opp[3] and opp[4] else "Price per Acre: N/A")
                    print(f"Coordinates: {opp[5]}, {opp[6]}" if opp[5] and opp[6] else "Coordinates: N/A")
                    print(f"Zoning: {opp[7] if opp[7] else 'N/A'}")

                    # Calculate investment recommendation
                    if opp[3] and float(opp[3]) < 75000:
                        markup = float(opp[3]) * 1.4  # 40% markup
                        profit = markup - float(opp[3])
                        print(f"\nINVESTMENT ANALYSIS:")
                        print(f"  Buy at: ${opp[3]:,.0f}")
                        print(f"  Sell to D.R. Horton at: ${markup:,.0f} (40% markup)")
                        print(f"  Expected Profit: ${profit:,.0f}")
                        print(f"  Strategy: Adjacent to D.R. Horton cluster")
            else:
                print("\nNo opportunity parcels found in this cluster.")

        # Step 5: Find ALL vacant parcels in hotspot areas
        print("\n\n5. TOP 20 UNDERVALUED VACANT PARCELS (Entire Market):")
        print("-" * 80)

        result = await session.execute(text("""
            SELECT
                parcel_id,
                site_address,
                owner_name,
                market_value,
                lot_size_acres,
                latitude,
                longitude,
                land_zoning_desc,
                city
            FROM bulk_property_records
            WHERE property_type ILIKE '%vacant%'
              AND market_value IS NOT NULL
              AND market_value > 1000
              AND market_value < 80000
              AND lot_size_acres > 0.5
              AND lot_size_acres < 10
              AND site_address IS NOT NULL
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            ORDER BY market_value / NULLIF(lot_size_acres, 0)
            LIMIT 20
        """))

        best_parcels = result.fetchall()

        print(f"\nFound {len(best_parcels)} high-potential parcels:")

        for i, parcel in enumerate(best_parcels, 1):
            print(f"\n{'='*80}")
            print(f"PARCEL #{i}")
            print(f"{'='*80}")
            print(f"Parcel ID: {parcel[0]}")
            print(f"Address: {parcel[1]}")
            print(f"Owner: {parcel[2]}")
            print(f"Market Value: ${parcel[3]:,.0f}")
            print(f"Lot Size: {parcel[4]:.2f} acres")
            print(f"Price per Acre: ${parcel[3]/parcel[4]:,.0f}")
            print(f"Location: {parcel[8] if parcel[8] else 'Unincorporated'}")
            print(f"Zoning: {parcel[7] if parcel[7] else 'Unknown'}")
            print(f"Coordinates: {parcel[5]}, {parcel[6]}")

            # Investment recommendation
            target_price = float(parcel[3]) * 1.15  # Buy at 15% above market
            sell_price = target_price * 1.35  # Sell at 35% above acquisition
            profit = sell_price - target_price

            print(f"\nINVESTMENT RECOMMENDATION:")
            print(f"  Offer Price: ${target_price:,.0f} (15% above market)")
            print(f"  Target Sale: ${sell_price:,.0f} (35% markup)")
            print(f"  Expected Profit: ${profit:,.0f}")
            print(f"  Hold Time: 3-6 months")

    await db_manager.close()


async def main():
    try:
        await analyze_dr_horton_holdings()
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
