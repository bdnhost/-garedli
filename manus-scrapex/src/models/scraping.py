"""
Scraping-related models
"""
from typing import Dict, Optional, Any, List
from pydantic import BaseModel, Field, HttpUrl, field_validator
from .base import TimestampMixin, TaskStatus, ScrapingEngine, BlockType


class FieldDefinition(BaseModel):
    """Field definition for data extraction schema"""
    type: str = Field(..., description="Data type (string, int, float, bool, etc.)")
    description: str = Field(..., description="Human-readable description of the field")
    required: bool = Field(default=False, description="Whether the field is required")
    pattern: Optional[str] = Field(None, description="Regex pattern for validation")
    range: Optional[List[float]] = Field(None, description="Min/max range for numeric fields")
    default: Optional[Any] = Field(None, description="Default value if missing")


class ScrapeRequest(BaseModel):
    """Request model for scraping"""
    url: HttpUrl = Field(..., description="URL to scrape")
    schema: Dict[str, FieldDefinition] = Field(..., description="Data extraction schema")
    priority: int = Field(default=1, ge=1, le=10, description="Task priority (1-10)")
    retry_count: int = Field(default=0, description="Current retry count")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")
    options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Scraping options (timeout, headers, etc.)"
    )

    @field_validator('schema')
    @classmethod
    def validate_schema(cls, v: Dict[str, FieldDefinition]) -> Dict[str, FieldDefinition]:
        """Validate schema has at least one field"""
        if not v:
            raise ValueError("Schema must contain at least one field")
        return v


class ProxyConfig(BaseModel):
    """Proxy configuration"""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = Field(default="http", pattern="^(http|https|socks5)$")
    country: Optional[str] = None
    proxy_type: str = Field(default="datacenter")  # datacenter, residential, mobile

    @property
    def url(self) -> str:
        """Get full proxy URL"""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"


class ScrapingStrategy(BaseModel):
    """Strategy for scraping"""
    engine: ScrapingEngine
    proxy: Optional[ProxyConfig] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    wait_time: float = Field(default=0.0, ge=0.0)
    javascript_enabled: bool = Field(default=False)
    screenshot: bool = Field(default=False)
    estimated_difficulty: float = Field(default=0.5, ge=0.0, le=1.0)
    timeout: int = Field(default=30, ge=1)


class URLAnalysis(BaseModel):
    """URL analysis result"""
    status_code: int
    headers: Dict[str, str]
    has_javascript: bool
    antibot_detected: bool
    estimated_load_time: float
    detected_frameworks: List[str] = Field(default_factory=list)
    is_spa: bool = False


class ScrapeResult(BaseModel, TimestampMixin):
    """Result of scraping operation"""
    url: str
    status: TaskStatus
    data: Optional[Dict[str, Any]] = None
    html: Optional[str] = None
    screenshot_path: Optional[str] = None
    error: Optional[str] = None
    strategy_used: Optional[ScrapingStrategy] = None
    execution_time: float = 0.0
    retry_count: int = 0


class ValidationError(BaseModel):
    """Validation error detail"""
    field: str
    error_type: str
    message: str
    value: Optional[Any] = None


class ValidationResult(BaseModel):
    """Result of data validation"""
    valid: bool
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    overall_confidence: float = 0.0
    field_validations: Optional[Dict[str, Any]] = None
    suggestions: List[str] = Field(default_factory=list)


class BlockAnalysis(BaseModel):
    """Analysis of bot detection/blocking"""
    is_blocked: bool
    block_type: BlockType
    confidence: float = Field(ge=0.0, le=1.0)
    indicators: List[str] = Field(default_factory=list)
    suggested_tactics: List[Dict[str, Any]] = Field(default_factory=list)


class EvasionResult(BaseModel):
    """Result of evasion attempt"""
    success: bool
    html: Optional[str] = None
    cookies: Optional[Dict[str, str]] = None
    captcha_solution: Optional[str] = None
    message: str = ""


class RetryStrategy(BaseModel):
    """Strategy for retry"""
    action: str  # "retry", "switch_engine", "switch_extraction_method", "re_extract"
    reason: str
    new_engine: Optional[ScrapingEngine] = None
    new_method: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None
