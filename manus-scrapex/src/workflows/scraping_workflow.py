"""
Scraping Workflow - Orchestrates all agents and engines
"""
import logging
from typing import Dict, Any

from ..models.scraping import ScrapeRequest, ScrapeResult, FieldDefinition
from ..models.base import TaskStatus, ScrapingEngine, BlockType
from ..agents.dispatcher import dispatcher_agent
from ..agents.antibot import antibot_agent
from ..agents.extractor import extractor_agent
from ..agents.validator import validator_agent
from ..engines.scrapy_engine import scrapy_engine
from ..engines.playwright_engine import playwright_engine
from ..config.settings import settings

logger = logging.getLogger(__name__)


class ScrapingWorkflow:
    """
    Main workflow that orchestrates the entire scraping process
    """

    def __init__(self):
        self.max_retries = settings.max_retries

    async def execute(self, request: ScrapeRequest) -> ScrapeResult:
        """
        Execute complete scraping workflow

        Workflow:
        1. Dispatch - Analyze URL and select strategy
        2. Scrape - Execute scraping with selected engine
        3. Anti-Bot Check - Detect and handle blocks
        4. Extract - Extract data using LLM
        5. Validate - Validate extracted data
        6. Retry - If needed, retry with adjusted strategy

        Args:
            request: Scrape request

        Returns:
            ScrapeResult: Final scraping result
        """
        logger.info(f"=== Starting workflow for {request.url} ===")

        retry_count = 0

        while retry_count <= self.max_retries:
            try:
                # Step 1: Dispatch - Select strategy
                logger.info(f"[1/5] Dispatching (attempt {retry_count + 1}/{self.max_retries + 1})")
                strategy = await dispatcher_agent.dispatch(request)

                # Step 2: Scrape - Execute scraping
                logger.info(f"[2/5] Scraping with {strategy.engine.value}")
                scrape_result = await self._execute_scraping(request.url, strategy)

                if scrape_result.status == TaskStatus.FAILED:
                    logger.error(f"Scraping failed: {scrape_result.error}")
                    if retry_count < self.max_retries:
                        retry_count += 1
                        continue
                    return scrape_result

                # Step 3: Anti-Bot Check
                logger.info("[3/5] Checking for anti-bot blocks")
                block_analysis = await antibot_agent.analyze(
                    html=scrape_result.html or "",
                    status_code=200,  # Would get this from scrape_result
                    headers=strategy.headers
                )

                if block_analysis.is_blocked:
                    logger.warning(
                        f"Block detected: {block_analysis.block_type.value} "
                        f"(confidence: {block_analysis.confidence:.2f})"
                    )

                    # Try evasion
                    if block_analysis.suggested_tactics:
                        tactic = block_analysis.suggested_tactics[0]
                        logger.info(f"Attempting evasion tactic: {tactic.get('tactic')}")

                        evasion_result = await antibot_agent.evade(
                            url=request.url,
                            block_type=block_analysis.block_type,
                            current_strategy=strategy,
                            tactic=tactic
                        )

                        if evasion_result.success and evasion_result.html:
                            # Update scrape result with evaded content
                            scrape_result.html = evasion_result.html
                            logger.info("Evasion successful!")
                        else:
                            logger.error(f"Evasion failed: {evasion_result.message}")
                            if retry_count < self.max_retries:
                                retry_count += 1
                                continue
                            return ScrapeResult(
                                url=request.url,
                                status=TaskStatus.FAILED,
                                error=f"Blocked and evasion failed: {evasion_result.message}",
                                retry_count=retry_count
                            )

                # Step 4: Extract - Extract data
                logger.info("[4/5] Extracting data")
                extracted_data = await extractor_agent.extract(
                    html=scrape_result.html or "",
                    schema=request.schema
                )

                scrape_result.data = extracted_data

                # Step 5: Validate - Validate extracted data
                logger.info("[5/5] Validating data")
                validation_result = await validator_agent.validate(
                    data=extracted_data,
                    schema=request.schema,
                    html=scrape_result.html
                )

                logger.info(
                    f"Validation: valid={validation_result.valid}, "
                    f"confidence={validation_result.overall_confidence:.2f}, "
                    f"errors={len(validation_result.errors)}, "
                    f"warnings={len(validation_result.warnings)}"
                )

                # Check if we should retry
                if not validation_result.valid or validation_result.overall_confidence < 0.6:
                    if retry_count < self.max_retries:
                        # Get retry strategy
                        retry_strategy = await validator_agent.suggest_retry_strategy(
                            validation_result=validation_result,
                            current_strategy=strategy
                        )

                        if retry_strategy:
                            logger.info(
                                f"Retrying with strategy: {retry_strategy.action} "
                                f"(reason: {retry_strategy.reason})"
                            )
                            retry_count += 1

                            # Apply modifications to request if needed
                            if retry_strategy.action == "switch_engine":
                                # Force different engine on next iteration
                                # (Dispatcher will be called again)
                                pass

                            continue
                        else:
                            # No retry strategy, accept result
                            logger.warning("Validation issues but no retry strategy available")
                            break
                    else:
                        logger.warning("Max retries reached, accepting current result")
                        break
                else:
                    # Success!
                    logger.info("✓ Workflow completed successfully!")
                    break

            except Exception as e:
                logger.error(f"Workflow error: {e}", exc_info=True)
                if retry_count < self.max_retries:
                    retry_count += 1
                    continue
                else:
                    return ScrapeResult(
                        url=request.url,
                        status=TaskStatus.FAILED,
                        error=f"Workflow exception: {str(e)}",
                        retry_count=retry_count
                    )

        # Update final status
        scrape_result.status = TaskStatus.COMPLETED
        scrape_result.retry_count = retry_count

        logger.info(
            f"=== Workflow finished for {request.url} "
            f"(status: {scrape_result.status.value}, retries: {retry_count}) ==="
        )

        return scrape_result

    async def _execute_scraping(self, url: str, strategy) -> ScrapeResult:
        """Execute scraping with selected engine"""
        if strategy.engine == ScrapingEngine.PLAYWRIGHT:
            return await playwright_engine.scrape(url, strategy)
        else:
            return await scrapy_engine.scrape(url, strategy)


# Global workflow instance
scraping_workflow = ScrapingWorkflow()
