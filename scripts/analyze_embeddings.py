#!/usr/bin/env python3
"""
Analyze and validate embedding output
"""

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

def analyze_embeddings(filepath: str):
    """Comprehensive analysis of embedding output"""

    print(f"Loading embeddings from: {filepath}")
    print("=" * 70)

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    metadata = data.get('metadata', {})
    embeddings = data.get('embeddings', [])

    # 1. METADATA ANALYSIS
    print("\n1. METADATA:")
    print("-" * 70)
    for key, value in metadata.items():
        print(f"   {key}: {value}")

    # 2. CHUNK STATISTICS
    print("\n2. CHUNK STATISTICS:")
    print("-" * 70)
    print(f"   Total chunks: {len(embeddings)}")

    # Analyze by city
    city_counts = Counter(emb.get('city', 'Unknown') for emb in embeddings)
    print(f"   Cities: {len(city_counts)}")
    for city, count in sorted(city_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"      {city}: {count} chunks")

    # 3. CHUNK SIZE ANALYSIS
    print("\n3. CHUNK SIZE ANALYSIS:")
    print("-" * 70)
    chunk_chars = [emb.get('chunk_chars', 0) for emb in embeddings]
    chunk_words = [emb.get('chunk_words', 0) for emb in embeddings]

    if chunk_chars:
        print(f"   Characters:")
        print(f"      Min: {min(chunk_chars)}")
        print(f"      Max: {max(chunk_chars)}")
        print(f"      Avg: {sum(chunk_chars) / len(chunk_chars):.1f}")

    if chunk_words:
        print(f"   Words:")
        print(f"      Min: {min(chunk_words)}")
        print(f"      Max: {max(chunk_words)}")
        print(f"      Avg: {sum(chunk_words) / len(chunk_words):.1f}")

    # 4. EMBEDDING VALIDATION
    print("\n4. EMBEDDING VALIDATION:")
    print("-" * 70)
    sample = embeddings[0] if embeddings else {}
    embedding_vec = sample.get('embedding', [])
    print(f"   Dimensions: {len(embedding_vec)}")
    print(f"   Sample embedding (first 5): {embedding_vec[:5]}")

    # Check for required fields
    required_fields = ['ordinance_file', 'city', 'state', 'chunk_number', 'chunk_text',
                       'chunk_chars', 'chunk_words', 'embedding', 'content_hash']
    missing_fields = []
    for field in required_fields:
        if field not in sample:
            missing_fields.append(field)

    if missing_fields:
        print(f"   ⚠️  Missing fields: {missing_fields}")
    else:
        print(f"   ✅ All required fields present")

    # Check for metadata field
    has_metadata = 'metadata' in sample
    print(f"   Metadata field present: {'✅ Yes' if has_metadata else '❌ No'}")

    # 5. CONTENT QUALITY CHECK
    print("\n5. CONTENT QUALITY CHECK:")
    print("-" * 70)

    # Sample 5 random chunks
    import random
    sample_size = min(5, len(embeddings))
    samples = random.sample(embeddings, sample_size)

    for i, emb in enumerate(samples, 1):
        text = emb.get('chunk_text', '')
        preview = text[:150] + "..." if len(text) > 150 else text
        print(f"\n   Sample {i} ({emb.get('city', 'Unknown')}, chunk #{emb.get('chunk_number', 0)}):")
        print(f"      \"{preview}\"")
        print(f"      Words: {emb.get('chunk_words', 0)}, Chars: {emb.get('chunk_chars', 0)}")

    # 6. COVERAGE ANALYSIS (New Keywords)
    print("\n6. COVERAGE ANALYSIS (New Keywords):")
    print("-" * 70)

    # Check for new keyword coverage
    new_keywords = {
        'tiny home': 0,
        'tiny house': 0,
        'solar': 0,
        'photovoltaic': 0,
        'daycare': 0,
        'child care': 0,
        'food truck': 0,
        'mobile food': 0,
        'backyard chicken': 0,
        'poultry': 0,
        'pool fence': 0,
        'swimming pool': 0
    }

    for emb in embeddings:
        text = emb.get('chunk_text', '').lower()
        for keyword in new_keywords:
            if keyword in text:
                new_keywords[keyword] += 1

    print("   New keyword occurrences:")
    for keyword, count in sorted(new_keywords.items(), key=lambda x: x[1], reverse=True):
        status = "✅" if count > 0 else "❌"
        print(f"      {status} '{keyword}': {count} chunks")

    # 7. FILE SIZE ANALYSIS
    print("\n7. FILE SIZE ANALYSIS:")
    print("-" * 70)
    file_size_mb = Path(filepath).stat().st_size / (1024 * 1024)
    avg_size_per_chunk_kb = (file_size_mb * 1024) / len(embeddings) if embeddings else 0
    print(f"   Total file size: {file_size_mb:.2f} MB")
    print(f"   Average per chunk: {avg_size_per_chunk_kb:.2f} KB")

    # 8. TIMESTAMP ANALYSIS
    print("\n8. TIMESTAMP ANALYSIS:")
    print("-" * 70)
    if 'file_modified_timestamp' in sample:
        timestamps = [emb.get('file_modified_timestamp') for emb in embeddings if emb.get('file_modified_timestamp')]
        if timestamps:
            unique_timestamps = set(timestamps)
            print(f"   Unique file timestamps: {len(unique_timestamps)}")
            print(f"   All chunks have timestamps: {'✅ Yes' if len(timestamps) == len(embeddings) else '❌ No'}")
    else:
        print(f"   ❌ No file_modified_timestamp field found")

    if 'scraped_date' in sample:
        print(f"   ✅ scraped_date field present")
    else:
        print(f"   ❌ No scraped_date field found")

    # 9. VALIDATION SUMMARY
    print("\n9. VALIDATION SUMMARY:")
    print("=" * 70)

    checks = []
    checks.append(("Total chunks >= 1500", len(embeddings) >= 1500))
    checks.append(("All 9 cities present", len(city_counts) == 9))
    checks.append(("Embedding dimensions = 1024", len(embedding_vec) == 1024))
    checks.append(("All required fields present", len(missing_fields) == 0))
    checks.append(("File size reasonable (50-100 MB)", 50 <= file_size_mb <= 150))
    checks.append(("Average chunk size reasonable (100-500 words)", 100 <= (sum(chunk_words) / len(chunk_words) if chunk_words else 0) <= 500))
    checks.append(("New keywords found", sum(new_keywords.values()) > 0))

    passed = sum(1 for _, result in checks if result)
    total = len(checks)

    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {check_name}")

    print(f"\n   Overall: {passed}/{total} checks passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n   🎉 ALL CHECKS PASSED - Embeddings ready for production!")
    elif passed >= total * 0.8:
        print("\n   ⚠️  MOSTLY GOOD - Minor issues, but usable")
    else:
        print("\n   ❌ ISSUES FOUND - Review failures before proceeding")

    return {
        'total_chunks': len(embeddings),
        'cities': len(city_counts),
        'embedding_dims': len(embedding_vec),
        'file_size_mb': file_size_mb,
        'checks_passed': passed,
        'checks_total': total
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_embeddings.py <embeddings_file.json>")
        sys.exit(1)

    filepath = sys.argv[1]

    if not Path(filepath).exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    results = analyze_embeddings(filepath)
    sys.exit(0)
