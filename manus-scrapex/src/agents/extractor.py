"""
Extractor Agent - Semantic data extraction using LLM
"""
import json
import logging
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup, Comment

from ..models.scraping import FieldDefinition
from ..services.llm_service import llm_service, LLMProvider
from ..config.settings import settings

logger = logging.getLogger(__name__)


class ExtractorAgent:
    """
    Agent responsible for:
    - Semantic data extraction using LLM
    - Adaptive schema matching
    - Fallback to traditional selectors
    """

    def __init__(self):
        self.cache = {}  # Simple in-memory cache

    async def extract(
        self,
        html: str,
        schema: Dict[str, FieldDefinition]
    ) -> Dict[str, Any]:
        """
        Extract data from HTML based on schema

        Args:
            html: HTML content
            schema: Data extraction schema

        Returns:
            Dict: Extracted data
        """
        logger.info(f"Extracting {len(schema)} fields from HTML")

        # Clean HTML first
        cleaned_html = self._clean_html(html)

        # Try LLM extraction (primary method)
        try:
            result = await self._extract_with_llm(cleaned_html, schema)

            # Validate result has expected fields
            if self._validate_basic_structure(result, schema):
                logger.info("LLM extraction successful")
                return result
            else:
                logger.warning("LLM extraction incomplete, retrying...")

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")

        # Fallback: Try with stricter prompt
        try:
            result = await self._extract_with_llm_strict(cleaned_html, schema)
            if self._validate_basic_structure(result, schema):
                logger.info("Strict LLM extraction successful")
                return result
        except Exception as e:
            logger.error(f"Strict LLM extraction failed: {e}")

        # Last resort: Return empty/null values
        logger.warning("All extraction methods failed, returning empty result")
        return {field: None for field in schema.keys()}

    def _clean_html(self, html: str) -> str:
        """
        Clean HTML to reduce token count and improve extraction

        Args:
            html: Raw HTML

        Returns:
            str: Cleaned HTML
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Remove script and style tags
            for tag in soup(['script', 'style', 'meta', 'link', 'noscript']):
                tag.decompose()

            # Remove comments
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()

            # Remove empty tags
            for tag in soup.find_all():
                if not tag.get_text(strip=True) and not tag.find_all():
                    tag.decompose()

            # Get simplified HTML
            cleaned = str(soup)

            # Limit length to avoid token limits (keep most relevant part)
            max_length = 10000
            if len(cleaned) > max_length:
                # Try to keep the main content area
                body = soup.find('body')
                if body:
                    cleaned = str(body)[:max_length]
                else:
                    cleaned = cleaned[:max_length]

            logger.debug(f"HTML cleaned: {len(html)} -> {len(cleaned)} chars")
            return cleaned

        except Exception as e:
            logger.error(f"HTML cleaning failed: {e}")
            return html[:10000]  # Return truncated original

    async def _extract_with_llm(
        self,
        html: str,
        schema: Dict[str, FieldDefinition]
    ) -> Dict[str, Any]:
        """
        Extract data using LLM (DeepSeek)

        Args:
            html: Cleaned HTML
            schema: Extraction schema

        Returns:
            Dict: Extracted data
        """
        # Build prompt
        prompt = self._build_extraction_prompt(html, schema)

        # Call LLM
        model = LLMProvider.DEEPSEEK_V3
        if settings.feature_deepseek_primary:
            model = LLMProvider.DEEPSEEK_V3
        else:
            model = LLMProvider.GPT4

        response = await llm_service.complete(
            prompt=prompt,
            model=model,
            temperature=0,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )

        # Parse response
        try:
            data = json.loads(response)
            return data
        except json.JSONDecodeError:
            # Try to extract JSON from response
            return self._extract_json_from_text(response)

    async def _extract_with_llm_strict(
        self,
        html: str,
        schema: Dict[str, FieldDefinition]
    ) -> Dict[str, Any]:
        """
        Extract with stricter prompt and validation

        Args:
            html: Cleaned HTML
            schema: Extraction schema

        Returns:
            Dict: Extracted data
        """
        prompt = self._build_strict_extraction_prompt(html, schema)

        response = await llm_service.complete(
            prompt=prompt,
            model=LLMProvider.DEEPSEEK_V3,
            temperature=0,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )

        return json.loads(response)

    def _build_extraction_prompt(
        self,
        html: str,
        schema: Dict[str, FieldDefinition]
    ) -> str:
        """Build extraction prompt for LLM"""
        # Format schema
        schema_lines = []
        for field, defn in schema.items():
            line = f"- `{field}`: {defn.description}"
            if defn.type:
                line += f" (type: {defn.type})"
            if defn.required:
                line += " **[REQUIRED]**"
            schema_lines.append(line)

        schema_text = "\n".join(schema_lines)

        prompt = f"""You are a precise data extraction assistant. Extract the following fields from the HTML below.

**Schema:**
{schema_text}

**Instructions:**
1. Return ONLY valid JSON (no explanations, no markdown)
2. Use `null` for missing fields
3. Follow the exact field names specified
4. Convert values to correct types:
   - Prices: Remove currency symbols, convert to float (e.g., "$29.99" → 29.99)
   - Numbers: Convert to int or float as appropriate
   - Booleans: true/false
   - Dates: Keep as strings in consistent format
5. Extract clean, trimmed values without extra whitespace
6. If multiple matches exist, use the most prominent/relevant one

**HTML:**
```html
{html}
```

**JSON Output (only JSON, nothing else):**
"""
        return prompt

    def _build_strict_extraction_prompt(
        self,
        html: str,
        schema: Dict[str, FieldDefinition]
    ) -> str:
        """Build stricter prompt with examples"""
        # Format schema with examples
        schema_lines = []
        for field, defn in schema.items():
            line = f"- `{field}`: {defn.description} (type: {defn.type})"
            if defn.required:
                line += " **[REQUIRED]**"

            # Add example based on type
            if defn.type == "float" and "price" in field.lower():
                line += "\n  Example: If HTML has \"$29.99\", extract 29.99"
            elif defn.type == "int" and "rating" in field.lower():
                line += "\n  Example: If HTML has \"4.5 stars\", extract 4.5"

            schema_lines.append(line)

        schema_text = "\n".join(schema_lines)

        prompt = f"""You are a precise data extraction system. Your task is to extract structured data from HTML.

**CRITICAL RULES:**
1. Output MUST be valid JSON only
2. Use exact field names from schema
3. Convert types correctly
4. Use null for missing data
5. No explanations, no markdown formatting

**Schema to extract:**
{schema_text}

**HTML Content:**
```html
{html}
```

**Your JSON output (start with {{ immediately):**
"""
        return prompt

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """Extract JSON from text that might have extra content"""
        try:
            # Try to find JSON in text
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

            # If that fails, try to parse the whole thing
            return json.loads(text)

        except Exception as e:
            logger.error(f"Failed to extract JSON from text: {e}")
            return {}

    def _validate_basic_structure(
        self,
        result: Dict[str, Any],
        schema: Dict[str, FieldDefinition]
    ) -> bool:
        """
        Validate that result has basic structure

        Args:
            result: Extraction result
            schema: Expected schema

        Returns:
            bool: True if valid structure
        """
        if not isinstance(result, dict):
            return False

        # Check that all required fields are present
        for field, defn in schema.items():
            if defn.required and field not in result:
                logger.warning(f"Required field missing: {field}")
                return False

        # Check that at least some fields have non-null values
        non_null_count = sum(1 for v in result.values() if v is not None)
        if non_null_count == 0:
            logger.warning("All extracted values are null")
            return False

        return True

    async def extract_with_selectors(
        self,
        html: str,
        selectors: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Extract data using traditional CSS/XPath selectors

        Args:
            html: HTML content
            selectors: Dict of field -> selector

        Returns:
            Dict: Extracted data
        """
        logger.info(f"Extracting with selectors: {len(selectors)} fields")

        soup = BeautifulSoup(html, 'lxml')
        result = {}

        for field, selector in selectors.items():
            try:
                # Try CSS selector first
                element = soup.select_one(selector)

                if element:
                    # Extract text content
                    text = element.get_text(strip=True)

                    # Try to infer type and convert
                    result[field] = self._infer_and_convert(text)
                else:
                    result[field] = None

            except Exception as e:
                logger.error(f"Selector extraction failed for {field}: {e}")
                result[field] = None

        return result

    def _infer_and_convert(self, value: str) -> Any:
        """Infer type and convert value"""
        if not value:
            return None

        value = value.strip()

        # Try int
        try:
            return int(value)
        except ValueError:
            pass

        # Try float (including prices)
        try:
            # Remove currency symbols and commas
            cleaned = value.replace('$', '').replace('€', '').replace(',', '')
            return float(cleaned)
        except ValueError:
            pass

        # Try boolean
        if value.lower() in ['true', 'yes', 'on']:
            return True
        if value.lower() in ['false', 'no', 'off']:
            return False

        # Return as string
        return value

    async def generate_selectors(
        self,
        html: str,
        schema: Dict[str, FieldDefinition]
    ) -> Dict[str, str]:
        """
        Generate CSS selectors for schema using DeepSeek-Coder

        Args:
            html: HTML content
            schema: Extraction schema

        Returns:
            Dict: field -> CSS selector
        """
        logger.info("Generating CSS selectors with DeepSeek-Coder")

        # Build prompt for selector generation
        schema_json = {
            field: defn.description
            for field, defn in schema.items()
        }

        prompt = f"""You are an expert at analyzing HTML and generating CSS selectors.

**Task:** Generate CSS selectors for each field in the schema below.

**Schema:**
```json
{json.dumps(schema_json, indent=2)}
```

**HTML:**
```html
{html[:5000]}
```

**Instructions:**
- For each field, provide a CSS selector that uniquely identifies the element
- Prefer class/id selectors over complex paths
- Ensure selectors are robust to minor HTML changes

**Output Format (JSON only):**
{{
  "field_name": "css-selector"
}}
"""

        try:
            response = await llm_service.complete(
                prompt=prompt,
                model=LLMProvider.DEEPSEEK_CODER,
                temperature=0,
                response_format={"type": "json_object"}
            )

            selectors = json.loads(response)
            logger.info(f"Generated {len(selectors)} selectors")
            return selectors

        except Exception as e:
            logger.error(f"Selector generation failed: {e}")
            return {}


# Global instance
extractor_agent = ExtractorAgent()
