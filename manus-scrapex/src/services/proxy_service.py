"""
Proxy Service - Manages rotating proxy pool
"""
import asyncio
import logging
import random
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from collections import deque

from ..models.scraping import ProxyConfig
from ..config.settings import settings

logger = logging.getLogger(__name__)


class ProxyPool:
    """
    Rotating proxy pool with health checking
    """

    def __init__(self):
        self.datacenter_proxies: deque = deque()
        self.residential_proxies: deque = deque()
        self.mobile_proxies: deque = deque()

        # Health tracking
        self.proxy_health: Dict[str, Dict] = {}

        # Load proxies from config
        self._load_proxies()

    def _load_proxies(self):
        """Load proxies from configuration"""
        if settings.proxy_list:
            proxy_urls = settings.proxy_list.split(',')
            for proxy_url in proxy_urls:
                proxy_url = proxy_url.strip()
                if proxy_url:
                    proxy_config = self._parse_proxy_url(proxy_url)
                    if proxy_config:
                        self.add_proxy(proxy_config)

        logger.info(
            f"Loaded proxies - "
            f"Datacenter: {len(self.datacenter_proxies)}, "
            f"Residential: {len(self.residential_proxies)}, "
            f"Mobile: {len(self.mobile_proxies)}"
        )

    def _parse_proxy_url(self, proxy_url: str) -> Optional[ProxyConfig]:
        """Parse proxy URL into ProxyConfig"""
        try:
            # Format: protocol://username:password@host:port
            # or: protocol://host:port
            from urllib.parse import urlparse

            parsed = urlparse(proxy_url)

            return ProxyConfig(
                protocol=parsed.scheme or "http",
                username=parsed.username,
                password=parsed.password,
                host=parsed.hostname or "",
                port=parsed.port or 8080,
                proxy_type="datacenter"  # Default, can be configured
            )
        except Exception as e:
            logger.error(f"Failed to parse proxy URL {proxy_url}: {e}")
            return None

    def add_proxy(self, proxy: ProxyConfig):
        """Add proxy to pool"""
        proxy_key = proxy.url

        # Initialize health tracking
        self.proxy_health[proxy_key] = {
            "success_count": 0,
            "failure_count": 0,
            "last_used": None,
            "last_success": None,
            "last_failure": None,
            "is_healthy": True,
            "consecutive_failures": 0
        }

        # Add to appropriate pool
        if proxy.proxy_type == "residential":
            self.residential_proxies.append(proxy)
        elif proxy.proxy_type == "mobile":
            self.mobile_proxies.append(proxy)
        else:
            self.datacenter_proxies.append(proxy)

        logger.debug(f"Added {proxy.proxy_type} proxy: {proxy.host}:{proxy.port}")

    async def get_proxy(
        self,
        proxy_type: str = "datacenter",
        country: Optional[str] = None
    ) -> Optional[ProxyConfig]:
        """
        Get next available proxy from pool

        Args:
            proxy_type: Type of proxy (datacenter, residential, mobile)
            country: Optional country filter

        Returns:
            ProxyConfig or None if no proxies available
        """
        # Select appropriate pool
        if proxy_type == "residential":
            pool = self.residential_proxies
        elif proxy_type == "mobile":
            pool = self.mobile_proxies
        else:
            pool = self.datacenter_proxies

        if not pool:
            logger.warning(f"No {proxy_type} proxies available")
            return None

        # Rotate proxy
        proxy = pool[0]
        pool.rotate(1)

        # Check if proxy is healthy
        if not self.is_proxy_healthy(proxy):
            # Try next proxy
            return await self.get_proxy(proxy_type, country)

        # Update last used
        self.proxy_health[proxy.url]["last_used"] = datetime.utcnow()

        return proxy

    def is_proxy_healthy(self, proxy: ProxyConfig) -> bool:
        """Check if proxy is healthy"""
        proxy_key = proxy.url
        health = self.proxy_health.get(proxy_key, {})

        # Mark unhealthy if too many consecutive failures
        if health.get("consecutive_failures", 0) >= 3:
            return False

        # Mark unhealthy if overall failure rate is too high
        total = health.get("success_count", 0) + health.get("failure_count", 0)
        if total >= 10:
            failure_rate = health.get("failure_count", 0) / total
            if failure_rate > 0.5:
                return False

        return health.get("is_healthy", True)

    async def report_success(self, proxy: ProxyConfig):
        """Report successful proxy use"""
        proxy_key = proxy.url
        if proxy_key in self.proxy_health:
            health = self.proxy_health[proxy_key]
            health["success_count"] += 1
            health["last_success"] = datetime.utcnow()
            health["consecutive_failures"] = 0
            health["is_healthy"] = True

            logger.debug(f"Proxy success: {proxy.host}:{proxy.port}")

    async def report_failure(self, proxy: ProxyConfig, reason: str = ""):
        """Report proxy failure"""
        proxy_key = proxy.url
        if proxy_key in self.proxy_health:
            health = self.proxy_health[proxy_key]
            health["failure_count"] += 1
            health["last_failure"] = datetime.utcnow()
            health["consecutive_failures"] += 1

            # Mark unhealthy if too many failures
            if health["consecutive_failures"] >= 3:
                health["is_healthy"] = False
                logger.warning(
                    f"Proxy marked unhealthy: {proxy.host}:{proxy.port} - {reason}"
                )

            logger.debug(f"Proxy failure: {proxy.host}:{proxy.port} - {reason}")

    async def health_check(self):
        """
        Perform health check on all proxies
        Run this periodically (e.g., every 5 minutes)
        """
        logger.info("Running proxy health check...")

        all_proxies = list(self.datacenter_proxies) + \
                      list(self.residential_proxies) + \
                      list(self.mobile_proxies)

        for proxy in all_proxies:
            try:
                # Simple HTTP check
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "http://httpbin.org/ip",
                        proxy=proxy.url,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            await self.report_success(proxy)
                        else:
                            await self.report_failure(proxy, f"Status: {response.status}")

            except Exception as e:
                await self.report_failure(proxy, str(e))

        logger.info("Proxy health check completed")

    def get_stats(self) -> Dict:
        """Get proxy pool statistics"""
        total_proxies = len(self.datacenter_proxies) + \
                       len(self.residential_proxies) + \
                       len(self.mobile_proxies)

        healthy_proxies = sum(
            1 for health in self.proxy_health.values()
            if health.get("is_healthy", True)
        )

        return {
            "total_proxies": total_proxies,
            "healthy_proxies": healthy_proxies,
            "datacenter_proxies": len(self.datacenter_proxies),
            "residential_proxies": len(self.residential_proxies),
            "mobile_proxies": len(self.mobile_proxies),
            "proxy_health": self.proxy_health
        }


# Global proxy pool instance
proxy_pool = ProxyPool()
