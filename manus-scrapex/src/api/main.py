"""
FastAPI Main Application
"""
import logging
from typing import Dict
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

from ..config.settings import settings
from ..models.scraping import ScrapeRequest, FieldDefinition
from ..models.base import BaseResponse
from ..workflows.scraping_workflow import scraping_workflow
from ..engines.scrapy_engine import scrapy_engine
from ..engines.playwright_engine import playwright_engine

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    'scrape_requests_total',
    'Total scrape requests',
    ['status']
)
REQUEST_DURATION = Histogram(
    'scrape_request_duration_seconds',
    'Scrape request duration'
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await scrapy_engine.close()
    await playwright_engine.close()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-Powered Autonomous Web Scraper",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "environment": settings.environment,
        "docs": "/docs",
        "health": "/health"
    }


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment
    }


# Metrics endpoint (Prometheus)
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# Main scraping endpoint
@app.post("/api/v1/scrape", response_model=BaseResponse)
async def scrape_endpoint(request: ScrapeRequest):
    """
    Scrape a URL and extract structured data

    Args:
        request: Scrape request with URL and schema

    Returns:
        BaseResponse: Scraping result
    """
    import time
    start_time = time.time()

    logger.info(f"Received scrape request for: {request.url}")

    try:
        # Execute workflow
        with REQUEST_DURATION.time():
            result = await scraping_workflow.execute(request)

        # Record metrics
        if result.status.value == "completed":
            REQUEST_COUNT.labels(status='success').inc()
        else:
            REQUEST_COUNT.labels(status='failure').inc()

        # Prepare response
        if result.status.value == "completed":
            return BaseResponse(
                success=True,
                message="Scraping completed successfully",
                data={
                    "url": result.url,
                    "data": result.data,
                    "execution_time": result.execution_time,
                    "retry_count": result.retry_count,
                    "screenshot": result.screenshot_path
                }
            )
        else:
            REQUEST_COUNT.labels(status='error').inc()
            return BaseResponse(
                success=False,
                message="Scraping failed",
                error=result.error,
                data={
                    "url": result.url,
                    "retry_count": result.retry_count
                }
            )

    except Exception as e:
        logger.error(f"Scraping error: {e}", exc_info=True)
        REQUEST_COUNT.labels(status='error').inc()

        return BaseResponse(
            success=False,
            message="Internal server error",
            error=str(e)
        )


# Batch scraping endpoint
@app.post("/api/v1/scrape/batch")
async def batch_scrape_endpoint(requests: list[ScrapeRequest]):
    """
    Scrape multiple URLs in batch

    Args:
        requests: List of scrape requests

    Returns:
        List of results
    """
    logger.info(f"Received batch scrape request for {len(requests)} URLs")

    try:
        import asyncio

        # Execute all requests concurrently
        tasks = [scraping_workflow.execute(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Prepare responses
        responses = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                responses.append({
                    "success": False,
                    "url": str(requests[i].url),
                    "error": str(result)
                })
            else:
                responses.append({
                    "success": result.status.value == "completed",
                    "url": result.url,
                    "data": result.data,
                    "execution_time": result.execution_time,
                    "error": result.error
                })

        return {
            "success": True,
            "total": len(requests),
            "completed": sum(1 for r in responses if r["success"]),
            "failed": sum(1 for r in responses if not r["success"]),
            "results": responses
        }

    except Exception as e:
        logger.error(f"Batch scraping error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Schema validation endpoint
@app.post("/api/v1/validate-schema")
async def validate_schema(schema: Dict[str, FieldDefinition]):
    """
    Validate a scraping schema

    Args:
        schema: Schema to validate

    Returns:
        Validation result
    """
    try:
        # Basic validation
        if not schema:
            return {
                "valid": False,
                "errors": ["Schema cannot be empty"]
            }

        errors = []
        for field, defn in schema.items():
            # Check field name
            if not field:
                errors.append("Field name cannot be empty")

            # Check type
            valid_types = ["string", "int", "float", "bool", "list", "dict"]
            if defn.type not in valid_types:
                errors.append(f"Invalid type for field '{field}': {defn.type}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "field_count": len(schema)
        }

    except Exception as e:
        return {
            "valid": False,
            "errors": [str(e)]
        }


# Status endpoint
@app.get("/api/v1/status")
async def get_status():
    """
    Get system status and statistics

    Returns:
        System status
    """
    from ..services.llm_service import llm_service
    from ..services.proxy_service import proxy_pool

    try:
        # Get LLM metrics
        llm_metrics = llm_service.metrics.get_summary()

        # Get proxy stats
        proxy_stats = proxy_pool.get_stats()

        return {
            "status": "operational",
            "version": settings.app_version,
            "environment": settings.environment,
            "llm_metrics": llm_metrics,
            "proxy_stats": proxy_stats,
            "features": {
                "deepseek_primary": settings.feature_deepseek_primary,
                "gpt4_fallback": settings.feature_gpt4_fallback,
                "vision_extraction": settings.feature_vision_extraction,
                "self_healing": settings.feature_self_healing,
                "batch_processing": settings.feature_batch_processing
            }
        }

    except Exception as e:
        logger.error(f"Status error: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
