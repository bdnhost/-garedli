"""
Scrapy Engine - Fast scraping for static sites
"""
import logging
import asyncio
from typing import Optional, Dict, Any
import aiohttp
from bs4 import BeautifulSoup

from ..models.scraping import ScrapingStrategy, ScrapeResult
from ..models.base import TaskStatus

logger = logging.getLogger(__name__)


class ScrapyEngine:
    """
    Fast scraping engine for static sites using aiohttp
    """

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def scrape(
        self,
        url: str,
        strategy: ScrapingStrategy
    ) -> ScrapeResult:
        """
        Scrape URL using Scrapy approach (static sites)

        Args:
            url: URL to scrape
            strategy: Scraping strategy

        Returns:
            ScrapeResult: Scraping results
        """
        import time
        start_time = time.time()

        logger.info(f"Scrapy: Scraping {url}")

        try:
            session = await self._get_session()

            # Build request kwargs
            kwargs = {
                "headers": strategy.headers,
                "timeout": aiohttp.ClientTimeout(total=strategy.timeout)
            }

            # Add proxy if available
            if strategy.proxy:
                kwargs["proxy"] = strategy.proxy.url
                logger.debug(f"Using proxy: {strategy.proxy.host}:{strategy.proxy.port}")

            # Make request
            async with session.get(url, **kwargs) as response:
                status_code = response.status
                html = await response.text()

                # Check if successful
                if status_code != 200:
                    logger.warning(f"Non-200 status code: {status_code}")

                # Parse HTML
                soup = BeautifulSoup(html, 'lxml')

                # Extract basic info
                title = soup.title.string if soup.title else ""

                execution_time = time.time() - start_time

                logger.info(f"Scrapy: Successfully scraped {url} in {execution_time:.2f}s")

                return ScrapeResult(
                    url=url,
                    status=TaskStatus.COMPLETED,
                    data=None,  # Will be extracted by Extractor Agent
                    html=html,
                    screenshot_path=None,
                    error=None,
                    strategy_used=strategy,
                    execution_time=execution_time,
                    retry_count=0
                )

        except aiohttp.ClientError as e:
            execution_time = time.time() - start_time
            logger.error(f"Scrapy: HTTP error for {url}: {e}")

            return ScrapeResult(
                url=url,
                status=TaskStatus.FAILED,
                data=None,
                html=None,
                error=f"HTTP error: {str(e)}",
                strategy_used=strategy,
                execution_time=execution_time,
                retry_count=0
            )

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(f"Scrapy: Timeout for {url}")

            return ScrapeResult(
                url=url,
                status=TaskStatus.FAILED,
                data=None,
                html=None,
                error="Request timeout",
                strategy_used=strategy,
                execution_time=execution_time,
                retry_count=0
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Scrapy: Unexpected error for {url}: {e}")

            return ScrapeResult(
                url=url,
                status=TaskStatus.FAILED,
                data=None,
                html=None,
                error=str(e),
                strategy_used=strategy,
                execution_time=execution_time,
                retry_count=0
            )

    async def close(self):
        """Close session"""
        if self.session and not self.session.closed:
            await self.session.close()


# Global instance
scrapy_engine = ScrapyEngine()
