"""
Playwright Engine - Dynamic content scraping with headless browser
"""
import logging
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from ..models.scraping import ScrapingStrategy, ScrapeResult
from ..models.base import TaskStatus

logger = logging.getLogger(__name__)


class PlaywrightEngine:
    """
    Headless browser engine for dynamic sites (SPA, JavaScript-heavy)
    """

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.playwright = None

    async def _get_browser(self) -> Browser:
        """Get or create browser instance"""
        if self.browser is None:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled'
                ]
            )
            logger.info("Playwright browser launched")

        return self.browser

    async def scrape(
        self,
        url: str,
        strategy: ScrapingStrategy
    ) -> ScrapeResult:
        """
        Scrape URL using Playwright (dynamic sites)

        Args:
            url: URL to scrape
            strategy: Scraping strategy

        Returns:
            ScrapeResult: Scraping results
        """
        import time
        start_time = time.time()

        logger.info(f"Playwright: Scraping {url}")

        context: Optional[BrowserContext] = None
        page: Optional[Page] = None

        try:
            browser = await self._get_browser()

            # Create context with realistic settings
            context_options = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": strategy.headers.get(
                    "User-Agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                ),
                "locale": "en-US",
                "timezone_id": "America/New_York"
            }

            # Add proxy if available
            if strategy.proxy:
                context_options["proxy"] = {
                    "server": f"{strategy.proxy.protocol}://{strategy.proxy.host}:{strategy.proxy.port}",
                }
                if strategy.proxy.username and strategy.proxy.password:
                    context_options["proxy"]["username"] = strategy.proxy.username
                    context_options["proxy"]["password"] = strategy.proxy.password

                logger.debug(f"Using proxy: {strategy.proxy.host}:{strategy.proxy.port}")

            context = await browser.new_context(**context_options)

            # Apply stealth techniques
            await self._apply_stealth(context)

            # Create page
            page = await context.new_page()

            # Set extra headers
            await page.set_extra_http_headers(strategy.headers)

            # Navigate to URL
            try:
                response = await page.goto(
                    url,
                    wait_until='networkidle' if strategy.javascript_enabled else 'domcontentloaded',
                    timeout=strategy.timeout * 1000  # Convert to milliseconds
                )

                if response:
                    status_code = response.status
                else:
                    status_code = 0

            except Exception as e:
                logger.error(f"Navigation failed: {e}")
                status_code = 0

            # Wait for additional time if specified
            if strategy.wait_time > 0:
                logger.debug(f"Waiting {strategy.wait_time}s for content to load")
                await asyncio.sleep(strategy.wait_time)

            # Wait for body to be present
            try:
                await page.wait_for_selector('body', timeout=10000)
            except:
                logger.warning("Body element not found")

            # Get HTML content
            html = await page.content()

            # Take screenshot if requested
            screenshot_path = None
            if strategy.screenshot:
                try:
                    screenshot_path = f"/tmp/screenshot_{int(time.time())}.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    logger.debug(f"Screenshot saved: {screenshot_path}")
                except Exception as e:
                    logger.error(f"Screenshot failed: {e}")

            # Get title
            title = await page.title()

            execution_time = time.time() - start_time

            logger.info(
                f"Playwright: Successfully scraped {url} in {execution_time:.2f}s "
                f"(HTML size: {len(html)} bytes)"
            )

            return ScrapeResult(
                url=url,
                status=TaskStatus.COMPLETED,
                data=None,  # Will be extracted by Extractor Agent
                html=html,
                screenshot_path=screenshot_path,
                error=None,
                strategy_used=strategy,
                execution_time=execution_time,
                retry_count=0
            )

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(f"Playwright: Timeout for {url}")

            return ScrapeResult(
                url=url,
                status=TaskStatus.FAILED,
                data=None,
                html=None,
                error="Page load timeout",
                strategy_used=strategy,
                execution_time=execution_time,
                retry_count=0
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Playwright: Unexpected error for {url}: {e}")

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

        finally:
            # Cleanup
            if page:
                await page.close()
            if context:
                await context.close()

    async def _apply_stealth(self, context: BrowserContext):
        """Apply stealth techniques to avoid detection"""
        # Add init scripts to hide automation
        await context.add_init_script("""
            // Overwrite the navigator.webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });

            // Chrome runtime
            window.chrome = {
                runtime: {}
            };

            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

    async def close(self):
        """Close browser and playwright"""
        if self.browser:
            await self.browser.close()
            self.browser = None

        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

        logger.info("Playwright engine closed")


# Global instance
playwright_engine = PlaywrightEngine()
