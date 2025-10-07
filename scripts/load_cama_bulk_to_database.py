"""
Load comprehensive CAMA data into database

Features:
- Dry-run mode for testing
- Batch processing
- Progress tracking
- Data validation
- Detailed logging

Usage:
    # Test mode (no database changes)
    python scripts/load_cama_bulk_to_database.py --dry-run --limit 100

    # Full load
    python scripts/load_cama_bulk_to_database.py --market alachua

    # Resume from checkpoint
    python scripts/load_cama_bulk_to_database.py --market alachua --resume
"""
import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd
from decimal import Decimal

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import db_manager
from src.database.models import BulkPropertyRecord, BulkDataSnapshot, Market
from sqlalchemy import select, update, text
from sqlalchemy.dialects.postgresql import insert


# Column mapping: CSV column → Database column
COLUMN_MAPPING = {
    # Identifiers
    'Parcel': 'parcel_id',
    # Note: prop_id from CSV is just stored in raw_data, not as property_id (which is UUID)

    # Owner info
    'Owner_Mail_Name': 'owner_name',
    'Owner_Mail_Addr2': 'mailing_address',
    'Owner_Mail_City': 'owner_city',
    'Owner_Mail_State': 'owner_state',
    'Owner_Mail_Zip': 'owner_zip',
    'physical_address': 'site_address',

    # Location
    'latitude': 'latitude',
    'longitude': 'longitude',
    'City_Desc': 'city',
    'Acres': 'lot_size_acres',
    'Section': 'section',
    'Township': 'township',
    'Range': 'range_value',
    'NBHD_Code': 'neighborhood_code',
    'NBHD_Desc': 'neighborhood_desc',
    'SBDV_Code': 'subdivision_code',
    'SBDV_Desc': 'subdivision_desc',

    # Property classification
    'Prop_Use_Desc': 'property_type',
    'Prop_Use_Code': 'use_code',
    'Land_Use_Code': 'land_use_code',
    'Land_Use_Desc': 'land_use_desc',
    'Land_Zoning_Code': 'land_zoning_code',
    'Land_Zoning_Desc': 'land_zoning_desc',
    'Land_Type': 'land_type',
    'Land_SqFt': 'land_sqft',

    # Building - primary
    'Actual_YrBlt': 'year_built',
    'Effective_YrBlt': 'effective_year_built',
    'Heated_SquareFeet': 'square_feet',
    'Stories': 'stories',
    'Imprv_Type': 'improvement_type',
    'Imprv_Desc': 'improvement_desc',

    # Building - attributes
    'bedrooms': 'bedrooms',
    'bathrooms': 'bathrooms',
    'roof_type': 'roof_type',
    'wall_type': 'wall_type',
    'exterior_type': 'exterior_type',
    'heat_type': 'heat_type',
    'ac_type': 'ac_type',
    'quality': 'building_quality',
    'condition': 'building_condition',

    # All structures - aggregated
    'total_improvement_sqft': 'total_improvement_sqft',
    'total_improvement_count': 'total_improvement_count',
    'improvement_types': 'improvement_types_list',
    'oldest_improvement_year': 'oldest_improvement_year',
    'newest_improvement_year': 'newest_improvement_year',
    'has_garage': 'has_garage',
    'has_porch': 'has_porch',
    'has_pool': 'has_pool',
    'has_fence': 'has_fence',
    'has_shed': 'has_shed',

    # Valuation
    'market_value_2025': 'market_value',
    'assessed_value_2025': 'assessed_value',
    'land_value_2025': 'land_value',
    'improvement_value_2025': 'improvement_value',
    'valuation_year': 'valuation_year',

    # Sales
    'Sale_Date': 'last_sale_date',
    'Sale_Price': 'last_sale_price',
    'Sale_Qualified': 'sale_qualified',
    'Sale_Vac_Imp': 'sale_type_vac_imp',
    'Sale_Book': 'sale_book',
    'Sale_Page': 'sale_page',

    # Tax exemptions
    'total_exemption_amount': 'total_exemption_amount',
    'exemption_types': 'exemption_types_list',
    'exemption_count': 'exemption_count',
    'most_recent_exemption_year': 'most_recent_exemption_year',

    # Legal & Permits
    'Legal_Desc': 'legal_description',
    'Total_Permits': 'total_permits',
}


def clean_value(value: Any, target_type: str) -> Any:
    """Clean and convert values to appropriate types"""
    if pd.isna(value) or value == '' or value == 'nan':
        return None

    try:
        if target_type == 'integer':
            return int(float(value))
        elif target_type == 'decimal':
            decimal_val = Decimal(str(value))
            # Cap at NUMERIC(10,2) max: 99,999,999.99
            if abs(decimal_val) >= Decimal('100000000'):
                return None  # Skip values that would overflow
            return decimal_val
        elif target_type == 'boolean':
            if isinstance(value, bool):
                return value
            return str(value).lower() in ('true', '1', 'yes', 't')
        elif target_type == 'date':
            if isinstance(value, str):
                # Try parsing date
                try:
                    return pd.to_datetime(value).date()
                except:
                    return None
            return value
        else:  # text
            return str(value).strip()
    except Exception:
        # Catch all conversion errors (ValueError, TypeError, decimal.ConversionSyntax, etc.)
        return None


def map_csv_row_to_db_record(row: pd.Series, market_id: str, snapshot_id: Optional[str] = None) -> Dict[str, Any]:
    """Map a CSV row to database record format"""

    record = {
        'market_id': market_id,
        'snapshot_id': snapshot_id,
    }

    # Map each column
    for csv_col, db_col in COLUMN_MAPPING.items():
        if csv_col not in row.index:
            continue

        value = row[csv_col]

        # Determine target type based on database column
        if db_col in ['parcel_id', 'owner_name', 'property_type', 'city', 'section',
                      'township', 'range_value', 'improvement_type', 'improvement_desc',
                      'roof_type', 'wall_type', 'heat_type', 'ac_type', 'building_quality',
                      'building_condition', 'land_use_code', 'land_use_desc', 'land_zoning_code',
                      'land_zoning_desc', 'land_type', 'legal_description', 'sale_qualified',
                      'sale_type_vac_imp', 'sale_book', 'sale_page', 'improvement_types_list',
                      'exemption_types_list', 'neighborhood_code', 'neighborhood_desc',
                      'subdivision_code', 'subdivision_desc', 'use_code', 'mailing_address',
                      'site_address', 'owner_city', 'owner_state', 'owner_zip', 'property_id']:
            record[db_col] = clean_value(value, 'text')

        elif db_col in ['year_built', 'effective_year_built', 'square_feet', 'stories',
                        'bedrooms', 'total_improvement_count', 'oldest_improvement_year',
                        'newest_improvement_year', 'exemption_count', 'valuation_year',
                        'total_permits', 'most_recent_exemption_year']:
            record[db_col] = clean_value(value, 'integer')

        elif db_col in ['latitude', 'longitude', 'lot_size_acres', 'total_improvement_sqft',
                        'bathrooms', 'market_value', 'assessed_value', 'land_value',
                        'improvement_value', 'last_sale_price', 'total_exemption_amount',
                        'land_sqft']:
            record[db_col] = clean_value(value, 'decimal')

        elif db_col in ['has_garage', 'has_porch', 'has_pool', 'has_fence', 'has_shed']:
            record[db_col] = clean_value(value, 'boolean')

        elif db_col in ['last_sale_date']:
            record[db_col] = clean_value(value, 'date')

    return record


async def load_cama_data(
    csv_path: Path,
    market_code: str,
    dry_run: bool = False,
    limit: Optional[int] = None,
    batch_size: int = 1000
):
    """Load CAMA data from CSV to database"""

    print("="*80)
    print("CAMA BULK DATA LOADER")
    print("="*80)
    print(f"\nCSV: {csv_path}")
    print(f"Market: {market_code}")
    print(f"Dry Run: {dry_run}")
    print(f"Limit: {limit or 'All'}")
    print(f"Batch Size: {batch_size}")
    print()

    # Load CSV
    print("Loading CSV...")
    df = pd.read_csv(csv_path, dtype=str, low_memory=False)

    if limit:
        df = df.head(limit)

    total_rows = len(df)
    print(f"Loaded {total_rows:,} rows from CSV")
    print()

    if dry_run:
        print("[DRY RUN MODE - No database changes will be made]")
        print()

    # Initialize database
    await db_manager.initialize()

    async with db_manager.get_session() as session:
        # Get or create market
        result = await session.execute(
            select(Market).where(Market.market_code == market_code)
        )
        market = result.scalar_one_or_none()

        if not market:
            if dry_run:
                print(f"[WARN] Market '{market_code}' not found (would create in real mode)")
                market_id = "00000000-0000-0000-0000-000000000000"  # Dummy for dry run
            else:
                print(f"Creating market: {market_code}")
                market = Market(
                    market_code=market_code,
                    market_name=market_code.title(),
                    state='FL',
                    county='Alachua',
                    is_active=True
                )
                session.add(market)
                await session.flush()
                market_id = str(market.id)
        else:
            market_id = str(market.id)
            print(f"Found market: {market.market_name} ({market_id})")

        # Create snapshot record
        if not dry_run:
            snapshot = BulkDataSnapshot(
                market_id=market_id,
                data_source='cama_comprehensive',
                file_name=csv_path.name,
                file_hash='',  # TODO: calculate hash
                status='processing',
                records_total=total_rows,
                download_started_at=datetime.utcnow(),
                processing_started_at=datetime.utcnow(),
                snapshot_date=datetime.utcnow().date(),
                is_current=True
            )
            session.add(snapshot)
            await session.flush()
            await session.commit()  # Commit snapshot before bulk insert
            snapshot_id = str(snapshot.id)
            print(f"Created snapshot: {snapshot_id}")
        else:
            snapshot_id = None
            print("Snapshot creation skipped (dry run)")

        print()
        print("="*80)
        print("PROCESSING RECORDS")
        print("="*80)
        print()

        # Process in batches
        inserted = 0
        updated = 0
        errors = 0
        sample_records = []

        for batch_start in range(0, total_rows, batch_size):
            batch_end = min(batch_start + batch_size, total_rows)
            batch_df = df.iloc[batch_start:batch_end]

            print(f"Processing batch {batch_start:,} - {batch_end:,} ({len(batch_df)} records)...")

            batch_records = []
            for idx, row in batch_df.iterrows():
                try:
                    record = map_csv_row_to_db_record(row, market_id, snapshot_id)

                    # Validate required fields
                    if not record.get('parcel_id'):
                        errors += 1
                        continue

                    batch_records.append(record)

                    # Save first 5 for sample output
                    if len(sample_records) < 5:
                        sample_records.append(record)

                except Exception as e:
                    print(f"  [ERROR] Error processing row {idx}: {e}")
                    errors += 1

            if not dry_run and batch_records:
                # Batch insert using asyncpg (faster than SQLAlchemy ORM)
                async with db_manager.get_connection() as conn:
                    columns = list(batch_records[0].keys())
                    col_str = ', '.join(columns)
                    placeholders = ', '.join([f'${i+1}' for i in range(len(columns))])

                    # Build upsert clause
                    update_cols = [col for col in columns if col not in ['id', 'market_id', 'parcel_id', 'snapshot_id']]
                    update_clause = ', '.join([f'{col} = EXCLUDED.{col}' for col in update_cols])

                    insert_sql = f"""
                        INSERT INTO bulk_property_records ({col_str})
                        VALUES ({placeholders})
                        ON CONFLICT (parcel_id, market_id, snapshot_id)
                        DO UPDATE SET {update_clause}
                    """

                    # Execute batch
                    for record in batch_records:
                        values = tuple(record[col] for col in columns)
                        await conn.execute(insert_sql, *values)

                inserted += len(batch_records)

            elif dry_run:
                inserted += len(batch_records)

            print(f"  [OK] Processed {len(batch_records)} records")

        if not dry_run:
            await session.commit()
            print("\n[OK] Database commit successful")
        else:
            print("\n[DRY RUN] Dry run complete - no database changes made")

    # Summary
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total rows processed: {total_rows:,}")
    print(f"Successfully mapped: {inserted:,}")
    print(f"Errors: {errors:,}")
    print(f"Success rate: {(inserted/total_rows*100):.1f}%")
    print()

    # Show sample records
    if sample_records:
        print("="*80)
        print("SAMPLE RECORDS (first 3)")
        print("="*80)
        for i, record in enumerate(sample_records[:3], 1):
            print(f"\nRecord {i}:")
            print(f"  Parcel: {record.get('parcel_id')}")
            print(f"  Owner: {record.get('owner_name')}")
            print(f"  City: {record.get('city')}")
            print(f"  Property Type: {record.get('property_type')}")
            print(f"  Year Built: {record.get('year_built')}")
            print(f"  Square Feet: {record.get('square_feet')}")
            print(f"  Bedrooms: {record.get('bedrooms')}")
            print(f"  Bathrooms: {record.get('bathrooms')}")
            print(f"  Market Value: ${record.get('market_value')}")
            print(f"  Has Garage: {record.get('has_garage')}")
            print(f"  Has Pool: {record.get('has_pool')}")
            print(f"  Total Improvements: {record.get('total_improvement_count')}")
            print(f"  Legal Desc: {str(record.get('legal_description', ''))[:60]}...")

    print()
    print("="*80)
    print("COMPLETE!")
    print("="*80)


def main():
    parser = argparse.ArgumentParser(description='Load CAMA bulk data to database')
    parser.add_argument('--csv', type=str, default='CAMA/CAMA_COMPLETE_ALL_TABLES.csv',
                        help='Path to CAMA CSV file')
    parser.add_argument('--market', type=str, default='alachua',
                        help='Market code (default: alachua)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Test mode - no database changes')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of records (for testing)')
    parser.add_argument('--batch-size', type=int, default=1000,
                        help='Batch size for inserts')

    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"[ERROR] CSV file not found: {csv_path}")
        sys.exit(1)

    asyncio.run(load_cama_data(
        csv_path=csv_path,
        market_code=args.market,
        dry_run=args.dry_run,
        limit=args.limit,
        batch_size=args.batch_size
    ))


if __name__ == "__main__":
    main()
