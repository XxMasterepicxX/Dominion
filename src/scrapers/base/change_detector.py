"""
Change detection system using MD5 hashing for tracking content updates.
"""
import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum

import aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from ...database.connection import DatabaseManager


class ChangeType(Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    UNCHANGED = "unchanged"


@dataclass
class ContentSnapshot:
    content_hash: str
    url: str
    timestamp: datetime
    size: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_type: Optional[str] = None
    response_code: Optional[int] = None


@dataclass
class ChangeDetectionResult:
    change_type: ChangeType
    url: str
    old_hash: Optional[str]
    new_hash: Optional[str]
    timestamp: datetime
    metadata_changes: Dict[str, Any] = field(default_factory=dict)
    size_change: Optional[int] = None
    first_seen: Optional[datetime] = None


class ChangeDetector:
    """
    Tracks content changes across different data sources using MD5 hashing.
    Stores change history in both PostgreSQL and Redis for performance.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        redis_client: aioredis.Redis,
        retention_days: int = 90
    ):
        self.db_manager = db_manager
        self.redis = redis_client
        self.retention_days = retention_days
        self.logger = logging.getLogger("change_detector")

    async def track_content_change(
        self,
        url: str,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None,
        response_code: Optional[int] = None
    ) -> ChangeDetectionResult:
        """
        Track content change for a given URL.

        Returns:
            ChangeDetectionResult indicating what type of change occurred
        """
        current_hash = hashlib.md5(content).hexdigest()
        timestamp = datetime.utcnow()
        size = len(content)

        # Get previous snapshot
        previous_snapshot = await self._get_latest_snapshot(url)

        # Create current snapshot
        current_snapshot = ContentSnapshot(
            content_hash=current_hash,
            url=url,
            timestamp=timestamp,
            size=size,
            metadata=metadata or {},
            content_type=content_type,
            response_code=response_code
        )

        # Determine change type
        if previous_snapshot is None:
            change_type = ChangeType.ADDED
            old_hash = None
            size_change = size
            first_seen = timestamp
        elif previous_snapshot.content_hash != current_hash:
            change_type = ChangeType.MODIFIED
            old_hash = previous_snapshot.content_hash
            size_change = size - previous_snapshot.size
            first_seen = await self._get_first_seen(url)
        else:
            change_type = ChangeType.UNCHANGED
            old_hash = previous_snapshot.content_hash
            size_change = 0
            first_seen = await self._get_first_seen(url)

        # Calculate metadata changes
        metadata_changes = {}
        if previous_snapshot and metadata:
            for key, value in metadata.items():
                old_value = previous_snapshot.metadata.get(key)
                if old_value != value:
                    metadata_changes[key] = {
                        'old': old_value,
                        'new': value
                    }

        # Store snapshot if changed or first time
        if change_type in [ChangeType.ADDED, ChangeType.MODIFIED]:
            await self._store_snapshot(current_snapshot)
            await self._update_redis_cache(current_snapshot)

        # Create and return result
        result = ChangeDetectionResult(
            change_type=change_type,
            url=url,
            old_hash=old_hash,
            new_hash=current_hash,
            timestamp=timestamp,
            metadata_changes=metadata_changes,
            size_change=size_change,
            first_seen=first_seen
        )

        # Log significant changes
        if change_type != ChangeType.UNCHANGED:
            self.logger.info(
                f"Content change detected: {url} - {change_type.value} "
                f"(size: {size_change:+d} bytes)"
            )

        return result

    async def get_change_history(
        self,
        url: str,
        days: int = 30,
        limit: int = 100
    ) -> List[ContentSnapshot]:
        """Get change history for a specific URL."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        async with self.db_manager.get_session() as session:
            query = """
                SELECT content_hash, url, timestamp, size, metadata,
                       content_type, response_code
                FROM content_snapshots
                WHERE url = $1 AND timestamp >= $2
                ORDER BY timestamp DESC
                LIMIT $3
            """

            result = await session.execute(query, url, cutoff_date, limit)
            rows = await result.fetchall()

            snapshots = []
            for row in rows:
                snapshots.append(ContentSnapshot(
                    content_hash=row['content_hash'],
                    url=row['url'],
                    timestamp=row['timestamp'],
                    size=row['size'],
                    metadata=row['metadata'] or {},
                    content_type=row['content_type'],
                    response_code=row['response_code']
                ))

            return snapshots

    async def get_urls_with_recent_changes(
        self,
        hours: int = 24,
        change_types: Optional[List[ChangeType]] = None
    ) -> List[str]:
        """Get list of URLs that have changed recently."""
        cutoff_date = datetime.utcnow() - timedelta(hours=hours)
        change_types = change_types or [ChangeType.ADDED, ChangeType.MODIFIED]

        # Use Redis for recent changes (faster)
        redis_key = "recent_changes"

        try:
            recent_changes = await self.redis.zrangebyscore(
                redis_key,
                cutoff_date.timestamp(),
                '+inf',
                withscores=True
            )

            urls = []
            for url_data, timestamp in recent_changes:
                url_info = json.loads(url_data)
                if ChangeType(url_info['change_type']) in change_types:
                    urls.append(url_info['url'])

            return list(set(urls))  # Remove duplicates

        except Exception as e:
            self.logger.warning(f"Redis lookup failed, falling back to database: {e}")
            return await self._get_recent_changes_from_db(cutoff_date, change_types)

    async def bulk_check_changes(
        self,
        url_content_pairs: List[Tuple[str, bytes, Optional[Dict[str, Any]]]]
    ) -> List[ChangeDetectionResult]:
        """
        Efficiently check changes for multiple URLs in batch.

        Args:
            url_content_pairs: List of (url, content, metadata) tuples
        """
        tasks = []
        for url, content, metadata in url_content_pairs:
            task = self.track_content_change(url, content, metadata)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and log them
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                url = url_content_pairs[i][0]
                self.logger.error(f"Change detection failed for {url}: {result}")
            else:
                valid_results.append(result)

        return valid_results

    async def cleanup_old_snapshots(self) -> int:
        """Remove snapshots older than retention period."""
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)

        async with self.db_manager.get_session() as session:
            query = """
                DELETE FROM content_snapshots
                WHERE timestamp < $1
            """
            result = await session.execute(query, cutoff_date)
            deleted_count = result.rowcount
            await session.commit()

            self.logger.info(f"Cleaned up {deleted_count} old snapshots")
            return deleted_count

    async def get_change_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get statistics about content changes."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        async with self.db_manager.get_session() as session:
            # Total snapshots
            total_query = """
                SELECT COUNT(*) as total
                FROM content_snapshots
                WHERE timestamp >= $1
            """
            total_result = await session.execute(total_query, cutoff_date)
            total_snapshots = (await total_result.fetchone())['total']

            # Unique URLs
            urls_query = """
                SELECT COUNT(DISTINCT url) as unique_urls
                FROM content_snapshots
                WHERE timestamp >= $1
            """
            urls_result = await session.execute(urls_query, cutoff_date)
            unique_urls = (await urls_result.fetchone())['unique_urls']

            # Changes per day
            daily_query = """
                SELECT DATE(timestamp) as day, COUNT(*) as changes
                FROM content_snapshots
                WHERE timestamp >= $1
                GROUP BY DATE(timestamp)
                ORDER BY day DESC
            """
            daily_result = await session.execute(daily_query, cutoff_date)
            daily_changes = {
                row['day'].isoformat(): row['changes']
                for row in await daily_result.fetchall()
            }

            # Most active URLs
            active_query = """
                SELECT url, COUNT(*) as changes
                FROM content_snapshots
                WHERE timestamp >= $1
                GROUP BY url
                ORDER BY changes DESC
                LIMIT 10
            """
            active_result = await session.execute(active_query, cutoff_date)
            most_active = {
                row['url']: row['changes']
                for row in await active_result.fetchall()
            }

            return {
                'total_snapshots': total_snapshots,
                'unique_urls': unique_urls,
                'daily_changes': daily_changes,
                'most_active_urls': most_active,
                'period_days': days
            }

    async def _get_latest_snapshot(self, url: str) -> Optional[ContentSnapshot]:
        """Get the most recent snapshot for a URL."""
        # Try Redis cache first
        cache_key = f"snapshot:latest:{hashlib.md5(url.encode()).hexdigest()}"

        try:
            cached = await self.redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return ContentSnapshot(
                    content_hash=data['content_hash'],
                    url=data['url'],
                    timestamp=datetime.fromisoformat(data['timestamp']),
                    size=data['size'],
                    metadata=data.get('metadata', {}),
                    content_type=data.get('content_type'),
                    response_code=data.get('response_code')
                )
        except Exception as e:
            self.logger.warning(f"Redis cache lookup failed: {e}")

        # Fall back to database
        async with self.db_manager.get_session() as session:
            query = """
                SELECT content_hash, url, timestamp, size, metadata,
                       content_type, response_code
                FROM content_snapshots
                WHERE url = $1
                ORDER BY timestamp DESC
                LIMIT 1
            """

            result = await session.execute(query, url)
            row = await result.fetchone()

            if row:
                snapshot = ContentSnapshot(
                    content_hash=row['content_hash'],
                    url=row['url'],
                    timestamp=row['timestamp'],
                    size=row['size'],
                    metadata=row['metadata'] or {},
                    content_type=row['content_type'],
                    response_code=row['response_code']
                )

                # Cache for future lookups
                await self._cache_snapshot(cache_key, snapshot)
                return snapshot

        return None

    async def _store_snapshot(self, snapshot: ContentSnapshot) -> None:
        """Store snapshot in database."""
        async with self.db_manager.get_session() as session:
            query = """
                INSERT INTO content_snapshots
                (content_hash, url, timestamp, size, metadata, content_type, response_code)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """

            await session.execute(
                query,
                snapshot.content_hash,
                snapshot.url,
                snapshot.timestamp,
                snapshot.size,
                json.dumps(snapshot.metadata),
                snapshot.content_type,
                snapshot.response_code
            )
            await session.commit()

    async def _update_redis_cache(self, snapshot: ContentSnapshot) -> None:
        """Update Redis cache with latest snapshot."""
        # Cache latest snapshot
        cache_key = f"snapshot:latest:{hashlib.md5(snapshot.url.encode()).hexdigest()}"
        cache_data = {
            'content_hash': snapshot.content_hash,
            'url': snapshot.url,
            'timestamp': snapshot.timestamp.isoformat(),
            'size': snapshot.size,
            'metadata': snapshot.metadata,
            'content_type': snapshot.content_type,
            'response_code': snapshot.response_code
        }

        await self.redis.setex(cache_key, 86400, json.dumps(cache_data))  # 24 hour cache

        # Add to recent changes sorted set
        recent_key = "recent_changes"
        change_data = {
            'url': snapshot.url,
            'change_type': ChangeType.MODIFIED.value,  # Will be overridden if ADDED
            'timestamp': snapshot.timestamp.isoformat()
        }

        await self.redis.zadd(
            recent_key,
            {json.dumps(change_data): snapshot.timestamp.timestamp()}
        )

        # Keep only last 7 days in recent changes
        week_ago = datetime.utcnow() - timedelta(days=7)
        await self.redis.zremrangebyscore(recent_key, 0, week_ago.timestamp())

    async def _cache_snapshot(self, cache_key: str, snapshot: ContentSnapshot) -> None:
        """Cache snapshot data in Redis."""
        try:
            cache_data = {
                'content_hash': snapshot.content_hash,
                'url': snapshot.url,
                'timestamp': snapshot.timestamp.isoformat(),
                'size': snapshot.size,
                'metadata': snapshot.metadata,
                'content_type': snapshot.content_type,
                'response_code': snapshot.response_code
            }

            await self.redis.setex(cache_key, 86400, json.dumps(cache_data))
        except Exception as e:
            self.logger.warning(f"Failed to cache snapshot: {e}")

    async def _get_first_seen(self, url: str) -> Optional[datetime]:
        """Get first seen timestamp for a URL."""
        async with self.db_manager.get_session() as session:
            query = """
                SELECT MIN(timestamp) as first_seen
                FROM content_snapshots
                WHERE url = $1
            """

            result = await session.execute(query, url)
            row = await result.fetchone()
            return row['first_seen'] if row else None

    async def _get_recent_changes_from_db(
        self,
        cutoff_date: datetime,
        change_types: List[ChangeType]
    ) -> List[str]:
        """Fallback method to get recent changes from database."""
        async with self.db_manager.get_session() as session:
            query = """
                SELECT DISTINCT url
                FROM content_snapshots
                WHERE timestamp >= $1
                ORDER BY url
            """

            result = await session.execute(query, cutoff_date)
            rows = await result.fetchall()
            return [row['url'] for row in rows]