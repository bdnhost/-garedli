"""
LLM Service - DeepSeek integration with fallback to GPT-4/Claude
"""
import json
import time
import logging
from typing import Optional, Dict, Any, List
from enum import Enum
import openai
from tenacity import retry, stop_after_attempt, wait_exponential

from ..models.base import LLMProvider
from ..config.settings import settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    Unified LLM service supporting multiple providers
    """

    def __init__(self):
        # DeepSeek client
        if settings.deepseek_api_key:
            self.deepseek_client = openai.AsyncOpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url
            )
        else:
            self.deepseek_client = None
            logger.warning("DeepSeek API key not configured")

        # OpenAI client (fallback)
        if settings.openai_api_key:
            self.openai_client = openai.AsyncOpenAI(
                api_key=settings.openai_api_key
            )
        else:
            self.openai_client = None
            logger.warning("OpenAI API key not configured")

        # Metrics tracking
        self.metrics = LLMMetrics()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def complete(
        self,
        prompt: str,
        model: LLMProvider = LLMProvider.DEEPSEEK_V3,
        temperature: float = 0,
        max_tokens: int = 2000,
        response_format: Optional[Dict] = None,
        system_message: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Call LLM with retry logic and metrics

        Args:
            prompt: The user prompt
            model: LLM provider to use
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            response_format: Response format (e.g., {"type": "json_object"})
            system_message: Optional system message
            **kwargs: Additional arguments

        Returns:
            str: Generated text response
        """
        start_time = time.time()

        try:
            # Route to appropriate provider
            if model in [LLMProvider.DEEPSEEK_V3, LLMProvider.DEEPSEEK_CODER]:
                if not self.deepseek_client:
                    raise ValueError("DeepSeek client not configured")

                response = await self._call_deepseek(
                    prompt=prompt,
                    model=model.value,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    system_message=system_message,
                    **kwargs
                )

            elif model in [LLMProvider.GPT4, LLMProvider.GPT4_VISION]:
                if not self.openai_client:
                    raise ValueError("OpenAI client not configured")

                response = await self._call_openai(
                    prompt=prompt,
                    model=model.value,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    system_message=system_message,
                    **kwargs
                )

            else:
                raise ValueError(f"Unsupported model: {model}")

            # Extract content
            content = response.choices[0].message.content

            # Record metrics
            latency = time.time() - start_time
            await self.metrics.record(
                model=model,
                latency=latency,
                tokens_used=response.usage.total_tokens if hasattr(response, 'usage') else 0,
                success=True
            )

            logger.info(
                f"LLM call successful - model: {model.value}, "
                f"latency: {latency:.2f}s, "
                f"tokens: {response.usage.total_tokens if hasattr(response, 'usage') else 'N/A'}"
            )

            return content

        except Exception as e:
            latency = time.time() - start_time
            await self.metrics.record(
                model=model,
                latency=latency,
                success=False
            )
            logger.error(f"LLM call failed - model: {model.value}, error: {e}")
            raise

    async def _call_deepseek(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict] = None,
        system_message: Optional[str] = None,
        **kwargs
    ):
        """Call DeepSeek API"""
        messages = []

        # Add system message if provided
        if system_message:
            messages.append({"role": "system", "content": system_message})

        # Add user prompt
        messages.append({"role": "user", "content": prompt})

        # Build completion kwargs
        completion_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # DeepSeek supports JSON mode
        if response_format and response_format.get("type") == "json_object":
            completion_kwargs["response_format"] = {"type": "json_object"}

        return await self.deepseek_client.chat.completions.create(**completion_kwargs)

    async def _call_openai(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict] = None,
        system_message: Optional[str] = None,
        **kwargs
    ):
        """Call OpenAI API"""
        messages = []

        # Add system message if provided
        if system_message:
            messages.append({"role": "system", "content": system_message})

        # Add user prompt
        messages.append({"role": "user", "content": prompt})

        # Build completion kwargs
        completion_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # OpenAI also supports JSON mode
        if response_format and response_format.get("type") == "json_object":
            completion_kwargs["response_format"] = {"type": "json_object"}

        return await self.openai_client.chat.completions.create(**completion_kwargs)

    async def batch_complete(
        self,
        prompts: List[str],
        model: LLMProvider = LLMProvider.DEEPSEEK_V3,
        **kwargs
    ) -> List[str]:
        """
        Batch processing for multiple prompts

        Args:
            prompts: List of prompts
            model: LLM provider
            **kwargs: Additional arguments

        Returns:
            List[str]: List of responses
        """
        import asyncio

        tasks = [
            self.complete(prompt, model=model, **kwargs)
            for prompt in prompts
        ]

        return await asyncio.gather(*tasks)

    async def complete_with_fallback(
        self,
        prompt: str,
        primary_model: LLMProvider = LLMProvider.DEEPSEEK_V3,
        fallback_model: LLMProvider = LLMProvider.GPT4,
        **kwargs
    ) -> str:
        """
        Try primary model, fallback to secondary if fails

        Args:
            prompt: The prompt
            primary_model: Primary LLM to try
            fallback_model: Fallback LLM if primary fails
            **kwargs: Additional arguments

        Returns:
            str: Generated response
        """
        try:
            return await self.complete(prompt, model=primary_model, **kwargs)
        except Exception as e:
            logger.warning(
                f"Primary model {primary_model.value} failed: {e}. "
                f"Falling back to {fallback_model.value}"
            )
            return await self.complete(prompt, model=fallback_model, **kwargs)


class LLMMetrics:
    """Metrics tracking for LLM calls"""

    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_latency = 0.0
        self.total_tokens = 0
        self.total_cost = 0.0

        # Per-model metrics
        self.model_stats: Dict[str, Dict[str, Any]] = {}

    async def record(
        self,
        model: LLMProvider,
        latency: float,
        tokens_used: int = 0,
        success: bool = True
    ):
        """Record metrics for an LLM call"""
        self.total_requests += 1

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        self.total_latency += latency
        self.total_tokens += tokens_used

        # Estimate cost
        cost = self._estimate_cost(model, tokens_used)
        self.total_cost += cost

        # Per-model stats
        model_key = model.value
        if model_key not in self.model_stats:
            self.model_stats[model_key] = {
                "requests": 0,
                "successes": 0,
                "failures": 0,
                "total_latency": 0.0,
                "total_tokens": 0,
                "total_cost": 0.0
            }

        stats = self.model_stats[model_key]
        stats["requests"] += 1
        stats["successes"] += 1 if success else 0
        stats["failures"] += 0 if success else 1
        stats["total_latency"] += latency
        stats["total_tokens"] += tokens_used
        stats["total_cost"] += cost

    def _estimate_cost(self, model: LLMProvider, tokens: int) -> float:
        """
        Estimate cost based on model and tokens

        Pricing (as of 2025):
        - DeepSeek-V3: $0.14/M input, $0.28/M output
        - GPT-4 Turbo: $10/M input, $30/M output
        - Claude 3.5: $3/M input, $15/M output
        """
        # Assume 60/40 split input/output
        input_tokens = tokens * 0.6
        output_tokens = tokens * 0.4

        pricing = {
            LLMProvider.DEEPSEEK_V3: (0.14, 0.28),
            LLMProvider.DEEPSEEK_CODER: (0.14, 0.28),
            LLMProvider.GPT4: (10.0, 30.0),
            LLMProvider.GPT4_VISION: (10.0, 30.0),
            LLMProvider.CLAUDE: (3.0, 15.0),
        }

        if model in pricing:
            input_price, output_price = pricing[model]
            return (input_tokens / 1_000_000 * input_price) + \
                   (output_tokens / 1_000_000 * output_price)

        return 0.0

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics"""
        avg_latency = self.total_latency / self.total_requests if self.total_requests > 0 else 0

        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.successful_requests / self.total_requests if self.total_requests > 0 else 0,
            "average_latency": avg_latency,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost,
            "model_stats": self.model_stats
        }


# Global instance
llm_service = LLMService()
