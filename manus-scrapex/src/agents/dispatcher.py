"""
Dispatcher Agent - Strategy selection and resource allocation
"""
import logging
import aiohttp
from typing import Dict, Optional, List
import re

from ..models.scraping import (
    ScrapeRequest, ScrapingStrategy, URLAnalysis, ProxyConfig
)
from ..models.base import ScrapingEngine
from ..services.proxy_service import proxy_pool
from ..config.settings import settings

logger = logging.getLogger(__name__)


class DispatcherAgent:
    """
    Agent responsible for:
    - URL analysis
    - Strategy selection (Scrapy vs Playwright)
    - Resource allocation (Proxy, headers)
    """

    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        ]

    async def dispatch(self, request: ScrapeRequest) -> ScrapingStrategy:
        """
        Main dispatch method

        Args:
            request: Scrape request

        Returns:
            ScrapingStrategy: Selected strategy
        """
        logger.info(f"Dispatching request for URL: {request.url}")

        # Step 1: Analyze URL
        analysis = await self._analyze_url(str(request.url))

        # Step 2: Select engine based on analysis
        engine = self._select_engine(analysis)

        # Step 3: Allocate proxy
        proxy = await self._allocate_proxy(analysis)

        # Step 4: Generate headers
        headers = self._generate_headers(analysis)

        # Step 5: Determine other settings
        wait_time = analysis.estimated_load_time
        javascript_enabled = analysis.has_javascript or analysis.is_spa
        estimated_difficulty = self._estimate_difficulty(analysis)

        strategy = ScrapingStrategy(
            engine=engine,
            proxy=proxy,
            headers=headers,
            wait_time=wait_time,
            javascript_enabled=javascript_enabled,
            screenshot=request.options.get("screenshot", False) if request.options else False,
            estimated_difficulty=estimated_difficulty,
            timeout=request.options.get("timeout", 30) if request.options else 30
        )

        logger.info(
            f"Strategy selected - Engine: {engine.value}, "
            f"JS: {javascript_enabled}, Difficulty: {estimated_difficulty:.2f}"
        )

        return strategy

    async def _analyze_url(self, url: str) -> URLAnalysis:
        """
        Perform initial URL analysis

        Args:
            url: URL to analyze

        Returns:
            URLAnalysis: Analysis results
        """
        logger.debug(f"Analyzing URL: {url}")

        try:
            async with aiohttp.ClientSession() as session:
                # Try HEAD first (faster)
                try:
                    async with session.head(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        status_code = resp.status
                        headers = dict(resp.headers)
                        html_sample = ""
                except:
                    # Fallback to GET
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        status_code = resp.status
                        headers = dict(resp.headers)
                        html_sample = await resp.text()

            # Analyze
            has_javascript = self._detect_javascript(html_sample)
            antibot_detected = self._detect_antibot(headers, html_sample)
            detected_frameworks = self._detect_frameworks(html_sample)
            is_spa = self._is_spa(html_sample, detected_frameworks)
            estimated_load_time = self._estimate_load_time(html_sample, has_javascript)

            return URLAnalysis(
                status_code=status_code,
                headers=headers,
                has_javascript=has_javascript,
                antibot_detected=antibot_detected,
                estimated_load_time=estimated_load_time,
                detected_frameworks=detected_frameworks,
                is_spa=is_spa
            )

        except Exception as e:
            logger.error(f"URL analysis failed: {e}")
            # Return safe defaults
            return URLAnalysis(
                status_code=0,
                headers={},
                has_javascript=True,  # Assume JS to be safe
                antibot_detected=False,
                estimated_load_time=3.0,
                detected_frameworks=[],
                is_spa=True
            )

    def _detect_javascript(self, html: str) -> bool:
        """Detect if page uses JavaScript"""
        if not html:
            return True  # Assume yes if no HTML

        js_indicators = [
            r'<script',
            r'\.js["\']',
            r'javascript:',
            r'React\.',
            r'Vue\.',
            r'angular',
            r'window\.',
            r'document\.',
            r'__NEXT_DATA__',
            r'nuxt',
            r'gatsby'
        ]

        for indicator in js_indicators:
            if re.search(indicator, html, re.IGNORECASE):
                return True

        return False

    def _detect_antibot(self, headers: Dict[str, str], html: str) -> bool:
        """Detect anti-bot protection"""
        # Check headers
        header_indicators = {
            'cf-ray': 'Cloudflare',
            'server': ['cloudflare', 'ddos-guard'],
            'x-sucuri-id': 'Sucuri',
            'x-cdn': 'stackpath'
        }

        for header, values in header_indicators.items():
            header_value = headers.get(header, '').lower()
            if isinstance(values, list):
                if any(v in header_value for v in values):
                    logger.info(f"Anti-bot detected in headers: {header}")
                    return True
            else:
                if header in headers:
                    logger.info(f"Anti-bot detected: {values}")
                    return True

        # Check HTML content
        if html:
            html_indicators = [
                'cloudflare',
                'datadome',
                'perimeterx',
                '_px',
                'recaptcha',
                'hcaptcha',
                'funcaptcha',
                'challenge-platform',
                'cf-browser-verification'
            ]

            html_lower = html.lower()
            for indicator in html_indicators:
                if indicator in html_lower:
                    logger.info(f"Anti-bot detected in HTML: {indicator}")
                    return True

        return False

    def _detect_frameworks(self, html: str) -> List[str]:
        """Detect JavaScript frameworks"""
        if not html:
            return []

        frameworks = []
        framework_indicators = {
            'React': [r'react', r'_jsx', r'__REACT'],
            'Vue': [r'vue', r'v-if', r'v-for', r'@click'],
            'Angular': [r'angular', r'ng-app', r'ng-controller'],
            'Next.js': [r'__NEXT_DATA__', r'next\.js'],
            'Nuxt': [r'nuxt', r'__NUXT__'],
            'Gatsby': [r'gatsby'],
            'Svelte': [r'svelte'],
        }

        html_lower = html.lower()
        for framework, indicators in framework_indicators.items():
            for indicator in indicators:
                if re.search(indicator, html_lower):
                    frameworks.append(framework)
                    break

        return frameworks

    def _is_spa(self, html: str, frameworks: List[str]) -> bool:
        """Determine if site is Single Page Application"""
        # If we detected SPA frameworks
        spa_frameworks = ['React', 'Vue', 'Angular', 'Next.js', 'Nuxt']
        if any(fw in frameworks for fw in spa_frameworks):
            return True

        # Check for minimal HTML (common in SPAs)
        if html and len(html) < 2000:
            if '<div id="root">' in html or '<div id="app">' in html:
                return True

        return False

    def _estimate_load_time(self, html: str, has_javascript: bool) -> float:
        """Estimate page load time"""
        if not html:
            return 3.0

        base_time = 1.0

        # Add time for JavaScript
        if has_javascript:
            base_time += 2.0

        # Add time for page size
        html_size_kb = len(html) / 1024
        if html_size_kb > 100:
            base_time += 1.0
        elif html_size_kb > 500:
            base_time += 2.0

        return min(base_time, 10.0)  # Cap at 10 seconds

    def _select_engine(self, analysis: URLAnalysis) -> ScrapingEngine:
        """
        Select scraping engine based on analysis

        Args:
            analysis: URL analysis

        Returns:
            ScrapingEngine: Selected engine
        """
        # Use Playwright if:
        # - Site is SPA
        # - Has JavaScript
        # - Anti-bot detected
        if analysis.is_spa or analysis.has_javascript or analysis.antibot_detected:
            logger.debug("Selected Playwright engine (dynamic content detected)")
            return ScrapingEngine.PLAYWRIGHT

        # Otherwise use Scrapy (faster for static sites)
        logger.debug("Selected Scrapy engine (static content)")
        return ScrapingEngine.SCRAPY

    async def _allocate_proxy(self, analysis: URLAnalysis) -> Optional[ProxyConfig]:
        """
        Allocate appropriate proxy

        Args:
            analysis: URL analysis

        Returns:
            ProxyConfig or None
        """
        if not settings.proxy_service_enabled:
            return None

        # Use residential proxy if anti-bot detected
        if analysis.antibot_detected:
            logger.debug("Allocating residential proxy (anti-bot detected)")
            return await proxy_pool.get_proxy(proxy_type="residential")

        # Otherwise use datacenter (cheaper)
        logger.debug("Allocating datacenter proxy")
        return await proxy_pool.get_proxy(proxy_type="datacenter")

    def _generate_headers(self, analysis: URLAnalysis) -> Dict[str, str]:
        """
        Generate realistic headers

        Args:
            analysis: URL analysis

        Returns:
            Dict of headers
        """
        import random

        headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        # Add referer if available
        if "referer" in analysis.headers:
            headers["Referer"] = analysis.headers["referer"]

        return headers

    def _estimate_difficulty(self, analysis: URLAnalysis) -> float:
        """
        Estimate scraping difficulty (0-1)

        Args:
            analysis: URL analysis

        Returns:
            float: Difficulty score
        """
        difficulty = 0.0

        # Base difficulty
        if analysis.has_javascript:
            difficulty += 0.2

        if analysis.is_spa:
            difficulty += 0.3

        if analysis.antibot_detected:
            difficulty += 0.4

        if analysis.status_code != 200:
            difficulty += 0.1

        return min(difficulty, 1.0)


# Global instance
dispatcher_agent = DispatcherAgent()
