"""
Anti-Bot Agent - Detection and evasion of bot protection
"""
import logging
import asyncio
from typing import Optional, Dict
import aiohttp

from ..models.scraping import BlockAnalysis, EvasionResult, ScrapingStrategy
from ..models.base import BlockType
from ..services.proxy_service import proxy_pool
from ..services.llm_service import llm_service, LLMProvider
from ..config.settings import settings

logger = logging.getLogger(__name__)


class AntiBotAgent:
    """
    Agent responsible for:
    - Detecting bot blocks/challenges
    - Evading anti-bot measures
    - Solving CAPTCHAs
    - Managing IP rotation
    """

    CLOUDFLARE_INDICATORS = [
        "Checking your browser",
        "cf-browser-verification",
        "cf_clearance",
        "Just a moment",
        "ray ID",
        "cloudflare"
    ]

    CAPTCHA_INDICATORS = [
        "recaptcha",
        "hcaptcha",
        "funcaptcha",
        "I'm not a robot",
        "g-recaptcha",
        "h-captcha"
    ]

    RATE_LIMIT_INDICATORS = [
        "Too many requests",
        "Rate limit exceeded",
        "429",
        "slow down"
    ]

    def __init__(self):
        pass

    async def analyze(
        self,
        html: str,
        status_code: int,
        headers: Dict[str, str]
    ) -> BlockAnalysis:
        """
        Analyze if response indicates blocking

        Args:
            html: HTML content
            status_code: HTTP status code
            headers: Response headers

        Returns:
            BlockAnalysis: Analysis results
        """
        logger.debug(f"Analyzing for bot blocks - Status: {status_code}")

        # Detect block type
        block_type, confidence, indicators = await self._detect_block(
            html, status_code, headers
        )

        if block_type == BlockType.NONE:
            return BlockAnalysis(
                is_blocked=False,
                block_type=BlockType.NONE,
                confidence=1.0,
                indicators=[],
                suggested_tactics=[]
            )

        # Get suggested tactics
        tactics = await self._suggest_tactics(block_type, html, headers)

        return BlockAnalysis(
            is_blocked=True,
            block_type=block_type,
            confidence=confidence,
            indicators=indicators,
            suggested_tactics=tactics
        )

    async def _detect_block(
        self,
        html: str,
        status_code: int,
        headers: Dict[str, str]
    ) -> tuple[BlockType, float, list]:
        """Detect type of block"""
        html_lower = html.lower() if html else ""
        indicators = []

        # Status code checks
        if status_code == 403:
            indicators.append("HTTP 403 Forbidden")
            return BlockType.IP_BLOCK, 0.9, indicators

        if status_code == 429:
            indicators.append("HTTP 429 Too Many Requests")
            return BlockType.RATE_LIMIT, 0.95, indicators

        # Cloudflare detection
        if any(ind.lower() in html_lower for ind in self.CLOUDFLARE_INDICATORS):
            indicators.extend([
                ind for ind in self.CLOUDFLARE_INDICATORS
                if ind.lower() in html_lower
            ])
            return BlockType.CLOUDFLARE, 0.9, indicators

        if 'cf-ray' in headers or 'cloudflare' in headers.get('server', '').lower():
            indicators.append("Cloudflare headers detected")
            return BlockType.CLOUDFLARE, 0.85, indicators

        # CAPTCHA detection
        if any(ind in html_lower for ind in self.CAPTCHA_INDICATORS):
            captcha_indicators = [
                ind for ind in self.CAPTCHA_INDICATORS
                if ind in html_lower
            ]
            indicators.extend(captcha_indicators)

            # Determine CAPTCHA type
            if 'recaptcha' in html_lower:
                return BlockType.RECAPTCHA, 0.95, indicators
            elif 'hcaptcha' in html_lower:
                return BlockType.HCAPTCHA, 0.95, indicators
            elif 'funcaptcha' in html_lower:
                return BlockType.FUNCAPTCHA, 0.90, indicators
            else:
                return BlockType.CAPTCHA_UNKNOWN, 0.80, indicators

        # DataDome
        if 'datadome' in html_lower:
            indicators.append("DataDome detected")
            return BlockType.DATADOME, 0.9, indicators

        # PerimeterX
        if '_px' in html_lower or 'perimeterx' in html_lower:
            indicators.append("PerimeterX detected")
            return BlockType.PERIMETER_X, 0.9, indicators

        # Rate limiting
        if any(ind.lower() in html_lower for ind in self.RATE_LIMIT_INDICATORS):
            indicators.extend([
                ind for ind in self.RATE_LIMIT_INDICATORS
                if ind.lower() in html_lower
            ])
            return BlockType.RATE_LIMIT, 0.85, indicators

        # No block detected
        return BlockType.NONE, 0.0, []

    async def _suggest_tactics(
        self,
        block_type: BlockType,
        html: str,
        headers: Dict[str, str]
    ) -> list:
        """Suggest evasion tactics using LLM"""
        try:
            prompt = f"""You are an anti-bot evasion expert.

Block Type Detected: {block_type.value}

HTTP Headers:
```json
{dict(list(headers.items())[:10])}
```

HTML Sample:
```html
{html[:2000] if html else 'N/A'}
```

Task: Suggest the top 3 evasion tactics for this block type, ordered by priority.

Output (JSON):
{{
  "tactics": [
    {{
      "tactic": "rotate_proxy|wait|stealth_browser|solve_captcha|change_headers",
      "priority": 1,
      "reasoning": "why this tactic would work",
      "wait_time": 0
    }}
  ]
}}
"""

            response = await llm_service.complete(
                prompt=prompt,
                model=LLMProvider.DEEPSEEK_V3,
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            import json
            data = json.loads(response)
            return data.get("tactics", [])

        except Exception as e:
            logger.error(f"Failed to get LLM tactics: {e}")
            # Fallback to rule-based tactics
            return self._get_default_tactics(block_type)

    def _get_default_tactics(self, block_type: BlockType) -> list:
        """Default rule-based tactics"""
        tactics_map = {
            BlockType.IP_BLOCK: [
                {
                    "tactic": "rotate_proxy",
                    "priority": 1,
                    "reasoning": "IP is blocked, need new IP",
                    "wait_time": 0
                }
            ],
            BlockType.RATE_LIMIT: [
                {
                    "tactic": "wait",
                    "priority": 1,
                    "reasoning": "Rate limit requires cooldown",
                    "wait_time": 60
                },
                {
                    "tactic": "rotate_proxy",
                    "priority": 2,
                    "reasoning": "Get fresh IP to reset rate limit",
                    "wait_time": 0
                }
            ],
            BlockType.CLOUDFLARE: [
                {
                    "tactic": "stealth_browser",
                    "priority": 1,
                    "reasoning": "Cloudflare requires browser fingerprint",
                    "wait_time": 5
                },
                {
                    "tactic": "rotate_proxy",
                    "priority": 2,
                    "reasoning": "Try residential proxy",
                    "wait_time": 0
                }
            ],
            BlockType.RECAPTCHA: [
                {
                    "tactic": "solve_captcha",
                    "priority": 1,
                    "reasoning": "Need to solve reCAPTCHA",
                    "wait_time": 0
                }
            ],
            BlockType.HCAPTCHA: [
                {
                    "tactic": "solve_captcha",
                    "priority": 1,
                    "reasoning": "Need to solve hCAPTCHA",
                    "wait_time": 0
                }
            ]
        }

        return tactics_map.get(block_type, [])

    async def evade(
        self,
        url: str,
        block_type: BlockType,
        current_strategy: ScrapingStrategy,
        tactic: Optional[Dict] = None
    ) -> EvasionResult:
        """
        Execute evasion tactic

        Args:
            url: URL to access
            block_type: Type of block
            current_strategy: Current strategy
            tactic: Specific tactic to use

        Returns:
            EvasionResult: Result of evasion attempt
        """
        if not tactic:
            tactics = self._get_default_tactics(block_type)
            if not tactics:
                return EvasionResult(
                    success=False,
                    message=f"No tactics available for {block_type.value}"
                )
            tactic = tactics[0]

        tactic_name = tactic.get("tactic", "")
        logger.info(f"Executing evasion tactic: {tactic_name}")

        try:
            if tactic_name == "rotate_proxy":
                return await self._rotate_proxy(url, current_strategy)

            elif tactic_name == "wait":
                wait_time = tactic.get("wait_time", 60)
                return await self._wait_and_retry(url, wait_time)

            elif tactic_name == "stealth_browser":
                return await self._use_stealth_browser(url)

            elif tactic_name == "solve_captcha":
                return await self._solve_captcha(url, block_type)

            elif tactic_name == "change_headers":
                return await self._change_headers(url, current_strategy)

            else:
                return EvasionResult(
                    success=False,
                    message=f"Unknown tactic: {tactic_name}"
                )

        except Exception as e:
            logger.error(f"Evasion failed: {e}")
            return EvasionResult(
                success=False,
                message=str(e)
            )

    async def _rotate_proxy(
        self,
        url: str,
        strategy: ScrapingStrategy
    ) -> EvasionResult:
        """Rotate to a new proxy"""
        logger.info("Rotating proxy...")

        # Get new residential proxy
        new_proxy = await proxy_pool.get_proxy(proxy_type="residential")

        if not new_proxy:
            return EvasionResult(
                success=False,
                message="No proxies available"
            )

        # Try request with new proxy
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    proxy=new_proxy.url,
                    headers=strategy.headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    html = await response.text()

                    # Check if still blocked
                    block_type, _, _ = await self._detect_block(
                        html,
                        response.status,
                        dict(response.headers)
                    )

                    if block_type == BlockType.NONE:
                        await proxy_pool.report_success(new_proxy)
                        return EvasionResult(
                            success=True,
                            html=html,
                            message="Successfully evaded with new proxy"
                        )
                    else:
                        await proxy_pool.report_failure(
                            new_proxy,
                            f"Still blocked: {block_type.value}"
                        )
                        return EvasionResult(
                            success=False,
                            message=f"Still blocked after proxy rotation: {block_type.value}"
                        )

        except Exception as e:
            if new_proxy:
                await proxy_pool.report_failure(new_proxy, str(e))
            return EvasionResult(
                success=False,
                message=f"Proxy rotation failed: {e}"
            )

    async def _wait_and_retry(self, url: str, wait_time: int) -> EvasionResult:
        """Wait and retry"""
        logger.info(f"Waiting {wait_time} seconds before retry...")
        await asyncio.sleep(wait_time)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    html = await response.text()

                    return EvasionResult(
                        success=response.status == 200,
                        html=html,
                        message=f"Retry after {wait_time}s - Status: {response.status}"
                    )

        except Exception as e:
            return EvasionResult(
                success=False,
                message=f"Retry failed: {e}"
            )

    async def _use_stealth_browser(self, url: str) -> EvasionResult:
        """Use stealth browser (Playwright)"""
        logger.info("Using stealth browser...")

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch(headless=True)

                # Create context with realistic settings
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York'
                )

                page = await context.new_page()

                # Navigate
                await page.goto(url, wait_until='networkidle', timeout=30000)

                # Wait for potential challenges
                await asyncio.sleep(5)

                # Get content
                html = await page.content()
                cookies = await context.cookies()

                await browser.close()

                return EvasionResult(
                    success=True,
                    html=html,
                    cookies={c['name']: c['value'] for c in cookies},
                    message="Successfully accessed with stealth browser"
                )

        except Exception as e:
            logger.error(f"Stealth browser failed: {e}")
            return EvasionResult(
                success=False,
                message=f"Stealth browser failed: {e}"
            )

    async def _solve_captcha(self, url: str, block_type: BlockType) -> EvasionResult:
        """Solve CAPTCHA using vision model or service"""
        logger.info(f"Attempting to solve CAPTCHA: {block_type.value}")

        # For now, return failure - actual CAPTCHA solving would require
        # integration with services like 2Captcha or GPT-4 Vision
        return EvasionResult(
            success=False,
            message="CAPTCHA solving not yet implemented"
        )

    async def _change_headers(
        self,
        url: str,
        strategy: ScrapingStrategy
    ) -> EvasionResult:
        """Try with different headers"""
        logger.info("Changing headers...")

        import random
        new_user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        ]

        new_headers = strategy.headers.copy()
        new_headers["User-Agent"] = random.choice(new_user_agents)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=new_headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    html = await response.text()

                    return EvasionResult(
                        success=response.status == 200,
                        html=html,
                        message=f"Headers changed - Status: {response.status}"
                    )

        except Exception as e:
            return EvasionResult(
                success=False,
                message=f"Header change failed: {e}"
            )


# Global instance
antibot_agent = AntiBotAgent()
