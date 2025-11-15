"""
Validator Agent - Data quality validation and verification
"""
import json
import logging
import re
from typing import Dict, Any, List, Optional

from ..models.scraping import (
    FieldDefinition, ValidationResult, ValidationError, RetryStrategy, ScrapingStrategy
)
from ..models.base import ScrapingEngine
from ..services.llm_service import llm_service, LLMProvider
from ..config.settings import settings

logger = logging.getLogger(__name__)


class ValidatorAgent:
    """
    Agent responsible for:
    - Data quality validation
    - Type and format checking
    - Consistency verification
    - Suggesting retry strategies
    """

    def __init__(self):
        pass

    async def validate(
        self,
        data: Dict[str, Any],
        schema: Dict[str, FieldDefinition],
        html: Optional[str] = None
    ) -> ValidationResult:
        """
        Comprehensive validation of extracted data

        Args:
            data: Extracted data
            schema: Expected schema
            html: Original HTML (optional, for consistency checking)

        Returns:
            ValidationResult: Validation results
        """
        logger.info(f"Validating {len(data)} fields")

        errors = []
        warnings = []
        confidence_scores = {}

        # 1. Schema validation
        schema_errors, schema_warnings = self._validate_schema(data, schema)
        errors.extend(schema_errors)
        warnings.extend(schema_warnings)

        # 2. Business logic validation
        logic_errors, logic_warnings = self._validate_business_logic(data, schema)
        errors.extend(logic_errors)
        warnings.extend(logic_warnings)

        # 3. Consistency check with LLM (if HTML provided)
        if html and settings.feature_deepseek_primary:
            try:
                llm_result = await self._validate_with_llm(data, html, schema)
                confidence_scores = llm_result.get("confidence_scores", {})

                # Add any issues found by LLM
                for field, result in llm_result.get("fields", {}).items():
                    if not result.get("appears_in_html", True):
                        errors.append(ValidationError(
                            field=field,
                            error_type="consistency",
                            message=f"Value not found in HTML: {data.get(field)}",
                            value=data.get(field)
                        ))

                    for issue in result.get("issues", []):
                        warnings.append(f"{field}: {issue}")

            except Exception as e:
                logger.error(f"LLM validation failed: {e}")
                # Assign default confidence
                confidence_scores = {field: 0.5 for field in data.keys()}
        else:
            # Assign default confidence if no LLM check
            confidence_scores = {field: 0.7 for field in data.keys() if data.get(field) is not None}

        # Calculate overall confidence
        if confidence_scores:
            overall_confidence = sum(confidence_scores.values()) / len(confidence_scores)
        else:
            overall_confidence = 0.0

        # Determine if valid
        is_valid = len(errors) == 0

        return ValidationResult(
            valid=is_valid,
            errors=errors,
            warnings=warnings,
            confidence_scores=confidence_scores,
            overall_confidence=overall_confidence
        )

    def _validate_schema(
        self,
        data: Dict[str, Any],
        schema: Dict[str, FieldDefinition]
    ) -> tuple[List[ValidationError], List[str]]:
        """
        Validate data against schema

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        # Check all schema fields
        for field, defn in schema.items():
            # Required field check
            if defn.required and field not in data:
                errors.append(ValidationError(
                    field=field,
                    error_type="missing_required",
                    message=f"Required field '{field}' is missing",
                    value=None
                ))
                continue

            # Field not in data
            if field not in data:
                continue

            value = data[field]

            # Null check for required fields
            if defn.required and value is None:
                errors.append(ValidationError(
                    field=field,
                    error_type="required_null",
                    message=f"Required field '{field}' is null",
                    value=None
                ))
                continue

            # Skip further validation for null optional fields
            if value is None:
                continue

            # Type validation
            if not self._validate_type(value, defn.type):
                errors.append(ValidationError(
                    field=field,
                    error_type="type_mismatch",
                    message=f"Expected type {defn.type}, got {type(value).__name__}",
                    value=value
                ))

            # Range validation (for numeric fields)
            if defn.range and isinstance(value, (int, float)):
                min_val, max_val = defn.range
                if not (min_val <= value <= max_val):
                    warnings.append(
                        f"{field}: Value {value} out of range [{min_val}, {max_val}]"
                    )

            # Pattern validation (for strings)
            if defn.pattern and isinstance(value, str):
                if not re.match(defn.pattern, value):
                    warnings.append(
                        f"{field}: Value doesn't match pattern {defn.pattern}"
                    )

        return errors, warnings

    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type"""
        type_map = {
            "string": str,
            "str": str,
            "int": int,
            "integer": int,
            "float": (int, float),  # Allow int for float
            "number": (int, float),
            "bool": bool,
            "boolean": bool,
            "list": list,
            "array": list,
            "dict": dict,
            "object": dict,
        }

        expected = type_map.get(expected_type.lower())
        if expected is None:
            # Unknown type, skip validation
            return True

        return isinstance(value, expected)

    def _validate_business_logic(
        self,
        data: Dict[str, Any],
        schema: Dict[str, FieldDefinition]
    ) -> tuple[List[ValidationError], List[str]]:
        """
        Validate business logic rules

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        # Price validation
        if "price" in data and data["price"] is not None:
            price = data["price"]
            if isinstance(price, (int, float)):
                if price <= 0:
                    errors.append(ValidationError(
                        field="price",
                        error_type="invalid_value",
                        message=f"Price must be positive, got {price}",
                        value=price
                    ))
                elif price > 1000000:
                    warnings.append(f"Unusually high price: {price}")

        # Discount price vs regular price
        if "price" in data and "discount_price" in data:
            price = data.get("price")
            discount_price = data.get("discount_price")

            if price and discount_price:
                if isinstance(price, (int, float)) and isinstance(discount_price, (int, float)):
                    if discount_price >= price:
                        warnings.append(
                            f"Discount price ({discount_price}) should be less than "
                            f"regular price ({price})"
                        )

        # Rating validation
        if "rating" in data and data["rating"] is not None:
            rating = data["rating"]
            if isinstance(rating, (int, float)):
                if not (0 <= rating <= 5):
                    warnings.append(f"Rating out of typical range [0-5]: {rating}")

        # URL validation
        for field in data:
            if "url" in field.lower() and data[field]:
                url = data[field]
                if isinstance(url, str):
                    if not (url.startswith("http://") or url.startswith("https://")):
                        warnings.append(f"{field}: URL doesn't start with http(s): {url}")

        # Email validation (basic)
        for field in data:
            if "email" in field.lower() and data[field]:
                email = data[field]
                if isinstance(email, str):
                    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                        warnings.append(f"{field}: Invalid email format: {email}")

        return errors, warnings

    async def _validate_with_llm(
        self,
        data: Dict[str, Any],
        html: str,
        schema: Dict[str, FieldDefinition]
    ) -> Dict[str, Any]:
        """
        Use LLM to validate data consistency with HTML

        Args:
            data: Extracted data
            html: Original HTML
            schema: Schema

        Returns:
            Dict: Validation results from LLM
        """
        # Clean HTML
        from bs4 import BeautifulSoup
        try:
            soup = BeautifulSoup(html, 'lxml')
            # Remove scripts and styles
            for tag in soup(['script', 'style']):
                tag.decompose()
            html_cleaned = str(soup)[:3000]  # Limit for tokens
        except:
            html_cleaned = html[:3000]

        prompt = f"""You are a data validation expert.

**Extracted Data:**
```json
{json.dumps(data, indent=2)}
```

**HTML Source (truncated):**
```html
{html_cleaned}
```

**Task:**
Validate the extracted data against the HTML:
1. Check if each value appears in the HTML
2. Assign confidence score (0-1) for each field
3. Flag any suspicious or incorrect values

**Output (JSON only):**
{{
  "fields": {{
    "field_name": {{
      "confidence": 0.95,
      "appears_in_html": true,
      "issues": []
    }}
  }}
}}
"""

        try:
            response = await llm_service.complete(
                prompt=prompt,
                model=LLMProvider.DEEPSEEK_V3,
                temperature=0,
                response_format={"type": "json_object"}
            )

            result = json.loads(response)

            # Extract confidence scores
            confidence_scores = {}
            for field, field_result in result.get("fields", {}).items():
                confidence_scores[field] = field_result.get("confidence", 0.5)

            result["confidence_scores"] = confidence_scores

            return result

        except Exception as e:
            logger.error(f"LLM validation failed: {e}")
            return {
                "fields": {},
                "confidence_scores": {field: 0.5 for field in data.keys()}
            }

    async def suggest_retry_strategy(
        self,
        validation_result: ValidationResult,
        current_strategy: ScrapingStrategy
    ) -> Optional[RetryStrategy]:
        """
        Suggest retry strategy based on validation results

        Args:
            validation_result: Validation results
            current_strategy: Current scraping strategy

        Returns:
            RetryStrategy or None if no retry needed
        """
        if validation_result.valid and validation_result.overall_confidence > 0.7:
            # No retry needed
            return None

        # Low confidence → try different extraction method
        if validation_result.overall_confidence < 0.6:
            return RetryStrategy(
                action="switch_extraction_method",
                reason=f"Low confidence ({validation_result.overall_confidence:.2f})",
                modifications={"use_stricter_prompt": True}
            )

        # Missing required fields → try different engine
        missing_required = any(
            e.error_type in ["missing_required", "required_null"]
            for e in validation_result.errors
        )

        if missing_required:
            new_engine = (
                ScrapingEngine.PLAYWRIGHT
                if current_strategy.engine == ScrapingEngine.SCRAPY
                else ScrapingEngine.SCRAPY
            )

            return RetryStrategy(
                action="switch_engine",
                reason="Missing required fields",
                new_engine=new_engine
            )

        # Type errors → re-extract with stricter prompt
        type_errors = any(
            e.error_type == "type_mismatch"
            for e in validation_result.errors
        )

        if type_errors:
            return RetryStrategy(
                action="re_extract",
                reason="Type validation failed",
                modifications={
                    "temperature": 0,
                    "stricter_prompt": True,
                    "add_examples": True
                }
            )

        # Consistency issues → retry with delay
        consistency_errors = any(
            e.error_type == "consistency"
            for e in validation_result.errors
        )

        if consistency_errors:
            return RetryStrategy(
                action="retry",
                reason="Consistency validation failed",
                modifications={"wait_time": 5}
            )

        # General retry
        return RetryStrategy(
            action="retry",
            reason="Validation failed"
        )


# Global instance
validator_agent = ValidatorAgent()
