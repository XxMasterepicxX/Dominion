"""
Resilient scraper base class with proxy rotation, rate limiting, and circuit breaker patterns.
"""
import asyncio
import hashlib
import json
import logging
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field

import aiohttp
import aioredis
from patchright.async_api import async_playwright, Page, Browser
from fake_useragent import UserAgent


class ScraperType(Enum):
    API = "api"
    WEB = "web"
    PDF = "pdf"
    RSS = "rss"


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ProxyConfig:
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"

    @property
    def url(self) -> str:
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"


@dataclass
class RateLimitConfig:
    requests_per_second: float = 1.0
    requests_per_minute: int = 60
    requests_per_hour: int = 3600
    burst_size: int = 5
    adaptive: bool = True
    min_delay: float = 0.1
    max_delay: float = 30.0
    backoff_factor: float = 2.0


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_max_calls: int = 3
    timeout_seconds: int = 30


@dataclass
class ScrapingResult:
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    response_time: Optional[float] = None
    content_hash: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    proxy_used: Optional[str] = None
    retries: int = 0


class RateLimiter:
    def __init__(self, config: RateLimitConfig, redis_client: aioredis.Redis):
        self.config = config
        self.redis = redis_client
        self._last_request = 0.0
        self._request_times: List[float] = []
        self._current_delay = config.min_delay

    async def acquire(self, scraper_id: str) -> None:
        """Acquire permission to make a request with adaptive rate limiting."""
        current_time = time.time()

        # Remove old request times
        cutoff = current_time - 3600  # 1 hour window
        self._request_times = [t for t in self._request_times if t > cutoff]

        # Check various rate limits
        await self._check_rate_limits(scraper_id, current_time)

        # Apply current delay
        time_since_last = current_time - self._last_request
        if time_since_last < self._current_delay:
            await asyncio.sleep(self._current_delay - time_since_last)

        self._last_request = time.time()
        self._request_times.append(self._last_request)

    async def _check_rate_limits(self, scraper_id: str, current_time: float) -> None:
        """Check all configured rate limits."""
        # Per-second limit
        recent_requests = sum(1 for t in self._request_times if t > current_time - 1)
        if recent_requests >= self.config.requests_per_second:
            await asyncio.sleep(1.0)

        # Per-minute limit
        minute_requests = sum(1 for t in self._request_times if t > current_time - 60)
        if minute_requests >= self.config.requests_per_minute:
            await asyncio.sleep(60 - (current_time % 60))

        # Per-hour limit
        hour_requests = len(self._request_times)
        if hour_requests >= self.config.requests_per_hour:
            await asyncio.sleep(3600 - (current_time % 3600))

    def on_success(self) -> None:
        """Called after successful request to potentially reduce delay."""
        if self.config.adaptive and self._current_delay > self.config.min_delay:
            self._current_delay = max(
                self.config.min_delay,
                self._current_delay / self.config.backoff_factor
            )

    def on_failure(self) -> None:
        """Called after failed request to increase delay."""
        if self.config.adaptive:
            self._current_delay = min(
                self.config.max_delay,
                self._current_delay * self.config.backoff_factor
            )


class CircuitBreaker:
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0

    async def call(self, func, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.config.half_open_max_calls:
                    raise Exception("Too many calls in HALF_OPEN state")
                self.half_open_calls += 1

            result = await func(*args, **kwargs)
            await self._on_success()
            return result

        except Exception as e:
            await self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.config.recovery_timeout

    async def _on_success(self) -> None:
        """Reset circuit breaker on successful call."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.half_open_calls = 0

    async def _on_failure(self) -> None:
        """Handle failure - increment counter and potentially open circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN


class ProxyRotator:
    def __init__(self, proxies: List[ProxyConfig]):
        self.proxies = proxies
        self.current_index = 0
        self.failed_proxies: Set[str] = set()
        self.proxy_stats: Dict[str, Dict[str, Any]] = {}

        for proxy in proxies:
            self.proxy_stats[proxy.url] = {
                'success_count': 0,
                'failure_count': 0,
                'last_used': None,
                'response_times': []
            }

    def get_next_proxy(self) -> Optional[ProxyConfig]:
        """Get next available proxy using round-robin with health checks."""
        if not self.proxies:
            return None

        available_proxies = [p for p in self.proxies if p.url not in self.failed_proxies]
        if not available_proxies:
            # Reset failed proxies if all are failed (give them another chance)
            self.failed_proxies.clear()
            available_proxies = self.proxies

        if not available_proxies:
            return None

        # Use weighted selection based on success rate
        return self._select_best_proxy(available_proxies)

    def _select_best_proxy(self, proxies: List[ProxyConfig]) -> ProxyConfig:
        """Select proxy with best success rate and lowest response time."""
        if len(proxies) == 1:
            return proxies[0]

        proxy_scores = []
        for proxy in proxies:
            stats = self.proxy_stats[proxy.url]
            total_requests = stats['success_count'] + stats['failure_count']

            if total_requests == 0:
                # New proxy - give it high priority
                score = 1.0
            else:
                success_rate = stats['success_count'] / total_requests
                avg_response_time = sum(stats['response_times'][-10:]) / len(stats['response_times'][-10:]) if stats['response_times'] else 1.0

                # Combine success rate and response time (lower is better for response time)
                score = success_rate * (1.0 / (avg_response_time + 0.1))

            proxy_scores.append((proxy, score))

        # Sort by score descending and return best
        proxy_scores.sort(key=lambda x: x[1], reverse=True)
        return proxy_scores[0][0]

    def mark_success(self, proxy: ProxyConfig, response_time: float) -> None:
        """Mark proxy as successful and record response time."""
        stats = self.proxy_stats[proxy.url]
        stats['success_count'] += 1
        stats['last_used'] = time.time()
        stats['response_times'].append(response_time)

        # Keep only last 50 response times
        if len(stats['response_times']) > 50:
            stats['response_times'] = stats['response_times'][-50:]

        # Remove from failed if it was there
        self.failed_proxies.discard(proxy.url)

    def mark_failure(self, proxy: ProxyConfig) -> None:
        """Mark proxy as failed."""
        stats = self.proxy_stats[proxy.url]
        stats['failure_count'] += 1

        # Add to failed set if failure rate is too high
        total = stats['success_count'] + stats['failure_count']
        if total >= 10 and stats['failure_count'] / total > 0.3:
            self.failed_proxies.add(proxy.url)


class ResilientScraper(ABC):
    """Base class for resilient scrapers with all reliability features."""

    def __init__(
        self,
        scraper_id: str,
        scraper_type: ScraperType,
        redis_client: aioredis.Redis,
        proxies: Optional[List[ProxyConfig]] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        max_retries: int = 3,
        timeout: int = 30,
        enable_js: bool = False
    ):
        self.scraper_id = scraper_id
        self.scraper_type = scraper_type
        self.redis = redis_client
        self.max_retries = max_retries
        self.timeout = timeout
        self.enable_js = enable_js

        # Initialize components
        self.rate_limiter = RateLimiter(
            rate_limit_config or RateLimitConfig(),
            redis_client
        )
        self.circuit_breaker = CircuitBreaker(
            circuit_breaker_config or CircuitBreakerConfig()
        )
        self.proxy_rotator = ProxyRotator(proxies or []) if proxies else None

        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self.browser: Optional[Browser] = None
        self.user_agent = UserAgent()

        # Logging
        self.logger = logging.getLogger(f"scraper.{scraper_id}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

    async def initialize(self) -> None:
        """Initialize scraper resources."""
        if self.scraper_type in [ScraperType.API, ScraperType.RSS]:
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=10)
            timeout_config = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout_config,
                headers={'User-Agent': self.user_agent.random}
            )

        elif self.scraper_type == ScraperType.WEB and self.enable_js:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )

    async def cleanup(self) -> None:
        """Clean up scraper resources."""
        if self.session:
            await self.session.close()
        if self.browser:
            await self.browser.close()

    async def scrape(self, url: str, **kwargs) -> ScrapingResult:
        """Main scraping method with all resilience features."""
        await self.rate_limiter.acquire(self.scraper_id)

        try:
            result = await self.circuit_breaker.call(
                self._scrape_with_retries, url, **kwargs
            )
            self.rate_limiter.on_success()
            return result

        except Exception as e:
            self.rate_limiter.on_failure()
            self.logger.error(f"Scraping failed for {url}: {e}")
            return ScrapingResult(
                success=False,
                error=str(e)
            )

    async def _scrape_with_retries(self, url: str, **kwargs) -> ScrapingResult:
        """Execute scraping with retry logic."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                start_time = time.time()
                result = await self._perform_scrape(url, attempt, **kwargs)
                response_time = time.time() - start_time

                if result.success:
                    # Update proxy stats on success
                    if self.proxy_rotator and result.proxy_used:
                        proxy = next((p for p in self.proxy_rotator.proxies if p.url == result.proxy_used), None)
                        if proxy:
                            self.proxy_rotator.mark_success(proxy, response_time)

                    result.response_time = response_time
                    result.retries = attempt
                    return result

            except Exception as e:
                last_error = e
                self.logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")

                # Update proxy stats on failure
                if self.proxy_rotator:
                    current_proxy = self.proxy_rotator.proxies[self.proxy_rotator.current_index % len(self.proxy_rotator.proxies)]
                    self.proxy_rotator.mark_failure(current_proxy)

                # Exponential backoff between retries
                if attempt < self.max_retries:
                    backoff_time = (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(backoff_time)

        return ScrapingResult(
            success=False,
            error=f"Failed after {self.max_retries + 1} attempts: {last_error}",
            retries=self.max_retries + 1
        )

    async def _perform_scrape(self, url: str, attempt: int, **kwargs) -> ScrapingResult:
        """Perform the actual scraping - implemented by subclasses."""
        if self.scraper_type == ScraperType.WEB and self.enable_js:
            return await self._scrape_with_browser(url, **kwargs)
        else:
            return await self._scrape_with_session(url, **kwargs)

    async def _scrape_with_session(self, url: str, **kwargs) -> ScrapingResult:
        """Scrape using aiohttp session."""
        proxy = None
        if self.proxy_rotator:
            proxy_config = self.proxy_rotator.get_next_proxy()
            if proxy_config:
                proxy = proxy_config.url

        headers = kwargs.get('headers', {})
        headers.update({'User-Agent': self.user_agent.random})

        async with self.session.request(
            method=kwargs.get('method', 'GET'),
            url=url,
            headers=headers,
            proxy=proxy,
            **{k: v for k, v in kwargs.items() if k not in ['method', 'headers']}
        ) as response:
            content = await response.read()

            # Process content based on scraper type
            data = await self.process_response(content, response)

            # Calculate content hash for change detection
            content_hash = hashlib.md5(content).hexdigest()

            return ScrapingResult(
                success=response.status < 400,
                data=data,
                status_code=response.status,
                content_hash=content_hash,
                proxy_used=proxy
            )

    async def _scrape_with_browser(self, url: str, **kwargs) -> ScrapingResult:
        """Scrape using Playwright browser."""
        page = await self.browser.new_page()

        try:
            # Set user agent
            await page.set_extra_http_headers({'User-Agent': self.user_agent.random})

            # Navigate to page
            response = await page.goto(url, wait_until='networkidle')

            # Process page content
            content = await page.content()
            data = await self.process_page_content(page, content)

            # Calculate content hash
            content_hash = hashlib.md5(content.encode()).hexdigest()

            return ScrapingResult(
                success=response.status < 400,
                data=data,
                status_code=response.status,
                content_hash=content_hash
            )

        finally:
            await page.close()

    @abstractmethod
    async def process_response(self, content: bytes, response: aiohttp.ClientResponse) -> Any:
        """Process HTTP response content - implemented by subclasses."""
        pass

    async def process_page_content(self, page: Page, content: str) -> Any:
        """Process browser page content - override in subclasses if needed."""
        return content

    async def check_for_changes(self, url: str, last_hash: Optional[str] = None) -> Tuple[bool, str]:
        """Check if content has changed since last scrape."""
        result = await self.scrape(url)

        if not result.success or not result.content_hash:
            return False, ""

        has_changed = last_hash != result.content_hash
        return has_changed, result.content_hash

    async def get_cached_result(self, cache_key: str, ttl: int = 3600) -> Optional[Dict[str, Any]]:
        """Get cached scraping result from Redis."""
        try:
            cached = await self.redis.get(f"scraper_cache:{self.scraper_id}:{cache_key}")
            if cached:
                return json.loads(cached)
        except Exception as e:
            self.logger.warning(f"Cache retrieval failed: {e}")
        return None

    async def set_cached_result(self, cache_key: str, data: Dict[str, Any], ttl: int = 3600) -> None:
        """Cache scraping result in Redis."""
        try:
            await self.redis.setex(
                f"scraper_cache:{self.scraper_id}:{cache_key}",
                ttl,
                json.dumps(data, default=str)
            )
        except Exception as e:
            self.logger.warning(f"Cache storage failed: {e}")