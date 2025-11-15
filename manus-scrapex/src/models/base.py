"""
Base models for the application
"""
from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields"""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BaseResponse(BaseModel):
    """Base response model"""
    success: bool
    message: str = ""
    data: Optional[dict] = None
    error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LLMProvider(str, Enum):
    """LLM Provider options"""
    DEEPSEEK_V3 = "deepseek-chat"
    DEEPSEEK_CODER = "deepseek-coder"
    GPT4 = "gpt-4-turbo"
    GPT4_VISION = "gpt-4-vision-preview"
    CLAUDE = "claude-3-5-sonnet"


class TaskStatus(str, Enum):
    """Task status options"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class ScrapingEngine(str, Enum):
    """Scraping engine options"""
    SCRAPY = "scrapy"
    PLAYWRIGHT = "playwright"
    REQUESTS = "requests"


class BlockType(str, Enum):
    """Anti-bot block types"""
    NONE = "none"
    IP_BLOCK = "ip_block"
    RATE_LIMIT = "rate_limit"
    CLOUDFLARE = "cloudflare"
    DATADOME = "datadome"
    PERIMETER_X = "perimeterx"
    RECAPTCHA = "recaptcha"
    HCAPTCHA = "hcaptcha"
    FUNCAPTCHA = "funcaptcha"
    CAPTCHA_UNKNOWN = "captcha_unknown"
