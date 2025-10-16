#!/usr/bin/env python3
"""
Quick test script to verify Aurora connection via RDS Data API

Usage:
    python scripts/test_aurora_connection.py \\
        --cluster-arn <ARN> \\
        --secret-arn <ARN>
"""

import argparse
import boto3
import json

def test_connection(cluster_arn, secret_arn, database='dominion'):
    """Test Aurora connection and create extensions"""
    print("\n" + "=" * 80)
    print("TESTING AURORA CONNECTION")
    print("=" * 80)
    print(f"Cluster: {cluster_arn}")
    print(f"Database: {database}")
    print("=" * 80 + "\n")

    rds_data = boto3.client('rds-data', region_name='us-east-1')

    # Test 1: Basic connection
    print("1. Testing basic connection...")
    try:
        response = rds_data.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=database,
            sql='SELECT version();'
        )
        version = response['records'][0][0]['stringValue']
        print(f"   [OK] Connected! PostgreSQL version: {version}")
    except Exception as e:
        print(f"   [FAIL] Connection failed: {e}")
        return False

    # Test 2: Create extensions
    print("\n2. Creating PostgreSQL extensions...")
    try:
        # pgvector for embeddings
        rds_data.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=database,
            sql='CREATE EXTENSION IF NOT EXISTS vector;'
        )
        print("   [OK] pgvector extension created")

        # PostGIS for geospatial
        rds_data.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=database,
            sql='CREATE EXTENSION IF NOT EXISTS postgis;'
        )
        print("   [OK] PostGIS extension created")
    except Exception as e:
        print(f"   [FAIL] Extension creation failed: {e}")
        return False

    # Test 3: Verify extensions
    print("\n3. Verifying extensions...")
    try:
        response = rds_data.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=database,
            sql="SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'postgis') ORDER BY extname;"
        )
        for record in response['records']:
            name = record[0]['stringValue']
            version = record[1]['stringValue']
            print(f"   [OK] {name} version {version}")
    except Exception as e:
        print(f"   [FAIL] Extension verification failed: {e}")
        return False

    # Test 4: Create test table
    print("\n4. Creating test table...")
    try:
        rds_data.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=database,
            sql='''
                CREATE TABLE IF NOT EXISTS connection_test (
                    id SERIAL PRIMARY KEY,
                    test_message TEXT,
                    test_embedding vector(3),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            '''
        )
        print("   [OK] Test table created")

        # Insert test row
        rds_data.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=database,
            sql="INSERT INTO connection_test (test_message, test_embedding) VALUES ('Aurora is ready!', '[1,2,3]');"
        )
        print("   [OK] Test row inserted")

        # Query test row
        response = rds_data.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=database,
            sql='SELECT * FROM connection_test;'
        )
        count = len(response['records'])
        print(f"   [OK] Test query successful ({count} rows)")

        # Cleanup
        rds_data.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=database,
            sql='DROP TABLE connection_test;'
        )
        print("   [OK] Test table cleaned up")
    except Exception as e:
        print(f"   [FAIL] Table test failed: {e}")
        return False

    print("\n" + "=" * 80)
    print("[OK] ALL TESTS PASSED! Aurora is ready for migration!")
    print("=" * 80 + "\n")
    return True


def main():
    parser = argparse.ArgumentParser(description='Test Aurora connection')
    parser.add_argument('--cluster-arn', required=True, help='Aurora cluster ARN')
    parser.add_argument('--secret-arn', required=True, help='Database credentials secret ARN')
    parser.add_argument('--database', default='dominion', help='Database name')
    args = parser.parse_args()

    success = test_connection(args.cluster_arn, args.secret_arn, args.database)
    exit(0 if success else 1)


if __name__ == '__main__':
    main()
