"""
Metrics Aggregation Service

Aggregates entity resolution metrics for production monitoring.
Runs periodically to populate entity_resolution_metrics table.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class MetricsAggregator:
    """Aggregates entity resolution metrics for monitoring"""

    async def aggregate_hourly_metrics(
        self,
        db_session: AsyncSession,
        target_date: Optional[datetime] = None,
        target_hour: Optional[int] = None
    ) -> None:
        """
        Aggregate metrics for a specific hour

        Args:
            db_session: Database session
            target_date: Date to aggregate (default: today)
            target_hour: Hour to aggregate (0-23, default: previous hour)
        """
        if target_date is None:
            target_date = datetime.now().date()

        if target_hour is None:
            target_hour = (datetime.now().hour - 1) % 24

        start_time = datetime.combine(target_date, datetime.min.time()).replace(hour=target_hour)
        end_time = start_time + timedelta(hours=1)

        # Aggregate from entity_resolution_log
        await db_session.execute(
            text("""
                INSERT INTO entity_resolution_metrics (
                    id, date, hour,
                    total_resolutions,
                    definitive_matches,
                    multi_signal_matches,
                    llm_matches,
                    new_entities_created,
                    queued_for_review,
                    high_confidence_count,
                    medium_confidence_count,
                    low_confidence_count,
                    avg_confidence,
                    created_at
                )
                SELECT
                    CAST(:id AS uuid),
                    CAST(:date AS date),
                    CAST(:hour AS integer),
                    COUNT(*),
                    COUNT(*) FILTER (WHERE method = 'definitive'),
                    COUNT(*) FILTER (WHERE method = 'multi_signal'),
                    COUNT(*) FILTER (WHERE method = 'llm'),
                    COUNT(*) FILTER (WHERE method = 'creation'),
                    COUNT(*) FILTER (WHERE method = 'needs_review'),
                    COUNT(*) FILTER (WHERE confidence >= 0.85),
                    COUNT(*) FILTER (WHERE confidence >= 0.60 AND confidence < 0.85),
                    COUNT(*) FILTER (WHERE confidence < 0.60),
                    AVG(confidence),
                    NOW()
                FROM entity_resolution_log
                WHERE created_at >= :start_time AND created_at < :end_time
                ON CONFLICT (date, hour) DO UPDATE SET
                    total_resolutions = EXCLUDED.total_resolutions,
                    definitive_matches = EXCLUDED.definitive_matches,
                    multi_signal_matches = EXCLUDED.multi_signal_matches,
                    llm_matches = EXCLUDED.llm_matches,
                    new_entities_created = EXCLUDED.new_entities_created,
                    queued_for_review = EXCLUDED.queued_for_review,
                    high_confidence_count = EXCLUDED.high_confidence_count,
                    medium_confidence_count = EXCLUDED.medium_confidence_count,
                    low_confidence_count = EXCLUDED.low_confidence_count,
                    avg_confidence = EXCLUDED.avg_confidence
            """),
            {
                'id': str(uuid4()),
                'date': target_date,
                'hour': target_hour,
                'start_time': start_time,
                'end_time': end_time
            }
        )
        await db_session.commit()

        logger.info(f"Aggregated metrics for {target_date} hour {target_hour}")

    async def aggregate_daily_metrics(
        self,
        db_session: AsyncSession,
        target_date: Optional[datetime] = None
    ) -> None:
        """
        Aggregate metrics for entire day (all hours)

        Args:
            db_session: Database session
            target_date: Date to aggregate (default: yesterday)
        """
        if target_date is None:
            target_date = (datetime.now() - timedelta(days=1)).date()

        for hour in range(24):
            await self.aggregate_hourly_metrics(db_session, target_date, hour)

        logger.info(f"Aggregated all hourly metrics for {target_date}")

    async def get_current_metrics(self, db_session: AsyncSession) -> dict:
        """Get current quality metrics for monitoring"""
        result = await db_session.execute(
            text("""
                SELECT
                    SUM(total_resolutions) as total,
                    SUM(definitive_matches) as definitive,
                    SUM(multi_signal_matches) as multi_signal,
                    SUM(queued_for_review) as review_queue,
                    AVG(avg_confidence) as avg_confidence,
                    SUM(high_confidence_count) as high_conf,
                    SUM(medium_confidence_count) as medium_conf,
                    SUM(low_confidence_count) as low_conf
                FROM entity_resolution_metrics
                WHERE date >= CURRENT_DATE - INTERVAL '7 days'
            """)
        )

        row = result.fetchone()
        if not row:
            return {}

        return {
            'total_resolutions': row.total or 0,
            'definitive_matches': row.definitive or 0,
            'multi_signal_matches': row.multi_signal or 0,
            'queued_for_review': row.review_queue or 0,
            'avg_confidence': float(row.avg_confidence) if row.avg_confidence else 0.0,
            'high_confidence_pct': (row.high_conf / row.total * 100) if row.total else 0,
            'medium_confidence_pct': (row.medium_conf / row.total * 100) if row.total else 0,
            'low_confidence_pct': (row.low_conf / row.total * 100) if row.total else 0
        }
