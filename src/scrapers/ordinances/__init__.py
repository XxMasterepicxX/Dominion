"""
Ordinance Scrapers

Scrapes municipal ordinances from multiple platforms:
- Municode (416+ Florida cities) - PRODUCTION READY
- General Code (future)
- American Legal (future)

Usage:
    from src.scrapers.ordinances import run_municode_scraper
    await run_municode_scraper(market_config)
"""

from .municode.scraper import run_from_config as run_municode_scraper

__all__ = ['run_municode_scraper']
