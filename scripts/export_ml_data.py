"""Export ML training data to CSV files"""
import asyncio
import asyncpg
import csv
import json
from pathlib import Path

async def export_ml_data():
    conn = await asyncpg.connect('postgresql://postgres:dominion@localhost/dominion')

    output_dir = Path(__file__).parent

    print("=" * 80)
    print("EXPORTING ML TRAINING DATA")
    print("=" * 80)

    # 1. Export entity_resolution_log (confirmed matches)
    print("\n[1/2] Exporting entity_resolution_log...")

    resolution_data = await conn.fetch('SELECT * FROM entity_resolution_log ORDER BY created_at DESC')

    resolution_file = output_dir / 'ml_training_data.csv'
    with open(resolution_file, 'w', newline='', encoding='utf-8') as f:
        if resolution_data:
            # Get column names
            columns = resolution_data[0].keys()
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()

            for row in resolution_data:
                # Convert row to dict and handle JSONB fields
                row_dict = dict(row)

                # Convert JSONB to JSON strings
                if 'scraped_features' in row_dict and row_dict['scraped_features']:
                    row_dict['scraped_features'] = json.dumps(row_dict['scraped_features'])
                if 'signals' in row_dict and row_dict['signals']:
                    row_dict['signals'] = json.dumps(row_dict['signals'])

                # Convert UUIDs to strings
                for key, value in row_dict.items():
                    if hasattr(value, 'hex'):  # UUID
                        row_dict[key] = str(value)
                    elif value is None:
                        row_dict[key] = ''

                writer.writerow(row_dict)

    print(f"   [OK] Exported {len(resolution_data):,} records to: {resolution_file}")
    print(f"   File size: {resolution_file.stat().st_size / 1024:.1f} KB")

    # 2. Export entity_review_queue (uncertain matches for labeling)
    print("\n[2/2] Exporting entity_review_queue...")

    review_data = await conn.fetch('''
        SELECT
            erq.*,
            e.canonical_name as matched_entity_name
        FROM entity_review_queue erq
        LEFT JOIN entities e ON erq.candidate_entity_id = e.id
        WHERE erq.status = 'pending'
        ORDER BY erq.confidence DESC
    ''')

    review_file = output_dir / 'review_queue.csv'
    with open(review_file, 'w', newline='', encoding='utf-8') as f:
        if review_data:
            columns = review_data[0].keys()
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()

            for row in review_data:
                row_dict = dict(row)

                # Convert JSONB to JSON strings
                if 'scraped_features' in row_dict and row_dict['scraped_features']:
                    row_dict['scraped_features'] = json.dumps(row_dict['scraped_features'])
                if 'signals' in row_dict and row_dict['signals']:
                    row_dict['signals'] = json.dumps(row_dict['signals'])

                # Convert UUIDs to strings
                for key, value in row_dict.items():
                    if hasattr(value, 'hex'):  # UUID
                        row_dict[key] = str(value)
                    elif value is None:
                        row_dict[key] = ''

                writer.writerow(row_dict)

    print(f"   [OK] Exported {len(review_data):,} records to: {review_file}")
    print(f"   File size: {review_file.stat().st_size / 1024:.1f} KB")

    # Summary
    print("\n" + "=" * 80)
    print("EXPORT COMPLETE")
    print("=" * 80)
    print(f"\nML Training Data:")
    print(f"  - Auto-accepted matches: {resolution_file.name} ({len(resolution_data):,} records)")
    print(f"  - Uncertain matches (need labels): {review_file.name} ({len(review_data):,} records)")

    print(f"\nTotal ML dataset size: {len(resolution_data) + len(review_data):,} entity matching decisions")

    print("\n" + "=" * 80)
    print("HOW TO USE THIS DATA")
    print("=" * 80)
    print("\n1. ml_training_data.csv - Auto-accepted matches (confidence ≥ 0.85)")
    print("   - Use as positive training examples")
    print("   - These are high-confidence matches already accepted by the system")
    print("   - Contains: scraped_features, matched_entity_id, confidence, signals")

    print("\n2. review_queue.csv - Uncertain matches (0.30 ≤ confidence < 0.85)")
    print("   - Use for human labeling")
    print("   - Add a 'correct_match' column (True/False)")
    print("   - Train ML model to predict: should these be matched?")

    print("\n3. Next Steps:")
    print("   - Label review_queue.csv with correct/incorrect")
    print("   - Combine with ml_training_data.csv")
    print("   - Train ML model (Random Forest, XGBoost, Neural Network)")
    print("   - Model learns to predict match confidence from signals")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(export_ml_data())
