"""
Current Market Context Manager

Provides global market context for all scrapers and services.
This is the foundation for multi-market support.

Usage:
    # Initialize at startup
    await CurrentMarket.initialize('gainesville_fl')

    # Use in scrapers
    market_id = CurrentMarket.get_id()
    market_code = CurrentMarket.get_code()

    # Switch markets (if needed)
    await CurrentMarket.set_market('tampa_fl')
"""

import logging
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class CurrentMarketError(Exception):
    """Raised when market operations fail"""
    pass


class CurrentMarket:
    """
    Global singleton for current market context.

    Thread-safe market context that persists across the application.
    Must be initialized before use.
    """

    _market_id: Optional[UUID] = None
    _market_code: Optional[str] = None
    _market_name: Optional[str] = None
    _market_config: Optional[dict] = None
    _initialized: bool = False

    @classmethod
    async def initialize(cls, market_code: str = 'gainesville_fl') -> None:
        """
        Initialize market context from database.

        Args:
            market_code: Market code (e.g., 'gainesville_fl')

        Raises:
            CurrentMarketError: If market not found or database error
        """
        try:
            # Import here to avoid circular dependency
            from ..database.connection import db_manager

            logger.info(f"Initializing CurrentMarket with: {market_code}")

            # Query market from database
            async with db_manager.get_connection() as conn:
                result = await conn.fetchrow(
                    """
                    SELECT id, market_code, market_name, config
                    FROM markets
                    WHERE market_code = $1 AND is_active = TRUE
                    """,
                    market_code
                )

                if not result:
                    raise CurrentMarketError(
                        f"Market '{market_code}' not found or not active. "
                        f"Please seed the market first with seed_gainesville_market.sql"
                    )

                cls._market_id = result['id']
                cls._market_code = result['market_code']
                cls._market_name = result['market_name']
                cls._market_config = result['config'] or {}
                cls._initialized = True

                logger.info(
                    f"CurrentMarket initialized: {cls._market_name} "
                    f"(ID: {cls._market_id})"
                )

        except Exception as e:
            logger.error(f"Failed to initialize CurrentMarket: {e}")
            raise CurrentMarketError(f"Market initialization failed: {e}")

    @classmethod
    async def set_market(cls, market_code: str) -> None:
        """
        Switch to a different market.

        Args:
            market_code: Market code to switch to

        Raises:
            CurrentMarketError: If market not found
        """
        logger.info(f"Switching market to: {market_code}")
        await cls.initialize(market_code)

    @classmethod
    def get_id(cls) -> UUID:
        """
        Get current market ID.

        Returns:
            Market UUID

        Raises:
            CurrentMarketError: If not initialized
        """
        if not cls._initialized or cls._market_id is None:
            raise CurrentMarketError(
                "CurrentMarket not initialized. "
                "Call await CurrentMarket.initialize() first"
            )
        return cls._market_id

    @classmethod
    def get_code(cls) -> str:
        """
        Get current market code.

        Returns:
            Market code (e.g., 'gainesville_fl')

        Raises:
            CurrentMarketError: If not initialized
        """
        if not cls._initialized or cls._market_code is None:
            raise CurrentMarketError(
                "CurrentMarket not initialized. "
                "Call await CurrentMarket.initialize() first"
            )
        return cls._market_code

    @classmethod
    def get_name(cls) -> str:
        """
        Get current market name.

        Returns:
            Market name (e.g., 'Gainesville, FL')

        Raises:
            CurrentMarketError: If not initialized
        """
        if not cls._initialized or cls._market_name is None:
            raise CurrentMarketError(
                "CurrentMarket not initialized. "
                "Call await CurrentMarket.initialize() first"
            )
        return cls._market_name

    @classmethod
    def get_config(cls) -> dict:
        """
        Get current market configuration.

        Returns:
            Market config dict (from markets.config JSONB)

        Raises:
            CurrentMarketError: If not initialized
        """
        if not cls._initialized or cls._market_config is None:
            raise CurrentMarketError(
                "CurrentMarket not initialized. "
                "Call await CurrentMarket.initialize() first"
            )
        return cls._market_config

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if market context is initialized"""
        return cls._initialized

    @classmethod
    def reset(cls) -> None:
        """Reset market context (mainly for testing)"""
        cls._market_id = None
        cls._market_code = None
        cls._market_name = None
        cls._market_config = None
        cls._initialized = False
        logger.info("CurrentMarket reset")

    @classmethod
    def get_status(cls) -> dict:
        """
        Get current market status for debugging.

        Returns:
            Dict with current market state
        """
        return {
            'initialized': cls._initialized,
            'market_id': str(cls._market_id) if cls._market_id else None,
            'market_code': cls._market_code,
            'market_name': cls._market_name,
            'has_config': bool(cls._market_config)
        }


# Convenience function for quick market initialization
async def init_market(market_code: str = 'gainesville_fl') -> None:
    """
    Quick market initialization helper.

    Args:
        market_code: Market code to initialize
    """
    await CurrentMarket.initialize(market_code)


# Convenience function to get market ID in sync code
def require_market_id() -> UUID:
    """
    Get market ID, ensuring it's initialized.

    Returns:
        Market UUID

    Raises:
        CurrentMarketError: If not initialized

    Note:
        This is a sync function for use in sync contexts.
        For async initialization, use CurrentMarket.initialize()
    """
    return CurrentMarket.get_id()
