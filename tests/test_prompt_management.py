import os
import sys
import unittest
import time
import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.ai.exceptions import (
    InvalidPrompt,
    ResponseParsingError,
    AIRequestTimeout,
    AIProviderUnavailable
)
from app.ai.schemas.prompt_metadata import PromptMetadata, PromptTemplate
from app.ai.schemas.ai_response import AIStructuredResponse, TokenUsage
from app.ai.schemas.ai import AIRequest, AIResponse
from app.ai.prompts.loader import load_prompt_file, parse_prompt_content
from app.ai.prompts.registry import PromptRegistry
from app.ai.prompts.renderer import PromptRenderer
from app.ai.prompts.validator import PromptValidator
from app.ai.parsers.text_parser import parse_text
from app.ai.parsers.json_parser import parse_json
from app.ai.parsers.markdown_parser import extract_code_block, parse_json_from_markdown
from app.ai.cache.prompt_cache import PromptCache
from app.ai.metrics import ai_metrics
from app.ai.services.ai_service import AIService
from app.ai.providers.base import BaseAIProvider


class TestParsers(unittest.TestCase):
    """Test text, JSON, and markdown parser helpers."""

    def test_text_parser(self):
        self.assertEqual(parse_text("  hello  "), "hello")
        self.assertEqual(parse_text("\nhello\nworld\n"), "hello\nworld")

    def test_json_parser_success(self):
        res = parse_json('{"key": "value", "list": [1, 2]}')
        self.assertEqual(res["key"], "value")
        self.assertEqual(res["list"], [1, 2])

    def test_json_parser_failure(self):
        with self.assertRaises(ResponseParsingError):
            parse_json('{"key": "value"')  # malformed

    def test_markdown_parser_extract_any(self):
        text = "Some text\n```\ninner code\n```\nother text"
        self.assertEqual(extract_code_block(text), "inner code")

    def test_markdown_parser_extract_json(self):
        text = "Hello\n```json\n{\"foo\": \"bar\"}\n```\nGoodbye"
        self.assertEqual(extract_code_block(text, "json"), '{"foo": "bar"}')

        # No match should fallback to original stripped content
        text_no_block = "plain content"
        self.assertEqual(extract_code_block(text_no_block, "json"), "plain content")

    def test_parse_json_from_markdown_success(self):
        text = "Markdown\n```json\n{\"score\": 95}\n```\nFooter"
        obj = parse_json_from_markdown(text)
        self.assertEqual(obj["score"], 95)

    def test_parse_json_from_markdown_failure(self):
        text = "Markdown\n```json\n{\"score\": 95\n```"
        with self.assertRaises(ResponseParsingError):
            parse_json_from_markdown(text)


class TestPromptCache(unittest.TestCase):
    """Test the in-memory prompt TTL caching implementation."""

    def setUp(self):
        self.cache = PromptCache()
        self.response = AIStructuredResponse(
            provider="ollama",
            model="qwen2.5:3b",
            latency_ms=100.0,
            prompt_version="1.0.0",
            created_at=datetime.utcnow(),
            raw_response={},
            parsed_response="parsed text",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=15, total_tokens=25),
            token_fields={}
        )

    def test_cache_set_and_get(self):
        variables = {"user": "Alice", "id": 123}
        self.cache.set("ollama", "qwen2.5:3b", "1.0.0", variables, self.response, ttl=60)
        
        cached = self.cache.get("ollama", "qwen2.5:3b", "1.0.0", variables)
        self.assertIsNotNone(cached)
        self.assertEqual(cached.parsed_response, "parsed text")

    def test_cache_miss_due_to_variables(self):
        variables1 = {"user": "Alice"}
        variables2 = {"user": "Bob"}
        self.cache.set("ollama", "qwen2.5:3b", "1.0.0", variables1, self.response, ttl=60)
        
        self.assertIsNone(self.cache.get("ollama", "qwen2.5:3b", "1.0.0", variables2))

    def test_cache_ttl_expiration(self):
        variables = {"key": "val"}
        # Set with expiry in the past
        with patch("time.time", return_value=1000.0):
            self.cache.set("ollama", "qwen2.5:3b", "1.0.0", variables, self.response, ttl=10)
        
        # Access at time = 1005 (valid)
        with patch("time.time", return_value=1005.0):
            self.assertIsNotNone(self.cache.get("ollama", "qwen2.5:3b", "1.0.0", variables))
            
        # Access at time = 1015 (expired)
        with patch("time.time", return_value=1015.0):
            self.assertIsNone(self.cache.get("ollama", "qwen2.5:3b", "1.0.0", variables))


class TestPromptLoaderAndRegistry(unittest.TestCase):
    """Test loader front matter parsing and registry version resolution."""

    def test_parse_prompt_content_valid(self):
        content = """---
name: resume_review
version: 2.1.0
description: A test description
author: Test Author
last_updated: 2026-07-01
metadata:
  category: resume
  priority: high
---
Hello {{ name }}!
"""
        meta, body = parse_prompt_content(content)
        self.assertEqual(meta.name, "resume_review")
        self.assertEqual(meta.version, "2.1.0")
        self.assertEqual(meta.metadata["priority"], "high")
        self.assertEqual(body.strip(), "Hello {{ name }}!")

    def test_parse_prompt_content_invalid_front_matter(self):
        # Missing metadata section starter
        content_no_header = "Hello world without header"
        with self.assertRaises(InvalidPrompt):
            parse_prompt_content(content_no_header)

        # Missing required field version
        content_missing_field = """---
name: resume_review
description: Missing version
last_updated: 2026-07-01
---
Hello
"""
        with self.assertRaises(InvalidPrompt):
            parse_prompt_content(content_missing_field)

    def test_registry_registration_and_version_resolution(self):
        registry = PromptRegistry()
        
        # Register v1.0.0
        meta1 = PromptMetadata(
            name="review", version="1.0.0", description="V1", last_updated="2026-01-01"
        )
        t1 = PromptTemplate(metadata=meta1, template_body="Body V1")
        registry.register_prompt("resume", t1)

        # Register v1.2.0
        meta2 = PromptMetadata(
            name="review", version="1.2.0", description="V1.2", last_updated="2026-02-01"
        )
        t2 = PromptTemplate(metadata=meta2, template_body="Body V1.2")
        registry.register_prompt("resume", t2)

        # Register v2.0.0
        meta3 = PromptMetadata(
            name="review", version="2.0.0", description="V2", last_updated="2026-03-01"
        )
        t3 = PromptTemplate(metadata=meta3, template_body="Body V2")
        registry.register_prompt("resume", t3)

        # Fetch specific version
        self.assertEqual(registry.get_prompt("resume", "review", "1.2.0").template_body, "Body V1.2")

        # Fetch latest version (should resolve to 2.0.0)
        latest = registry.get_prompt("resume", "review")
        self.assertEqual(latest.metadata.version, "2.0.0")
        self.assertEqual(latest.template_body, "Body V2")

    def test_registry_missing_prompt(self):
        registry = PromptRegistry()
        with self.assertRaises(InvalidPrompt):
            registry.get_prompt("resume", "non_existent")


class TestPromptRendererAndValidator(unittest.TestCase):
    """Test renderer rendering syntax and validator exceptions."""

    def setUp(self):
        self.renderer = PromptRenderer()
        self.validator = PromptValidator()

    def test_rendering_success(self):
        template_body = "User: {{ name }}, Role: {{ role }}"
        res = self.renderer.render(template_body, {"name": "Bob", "role": "admin"})
        self.assertEqual(res, "User: Bob, Role: admin")

    def test_validation_syntax_error(self):
        invalid_template = "Hello {{ name" # unclosed brackets
        with self.assertRaises(InvalidPrompt):
            self.validator.validate_template(invalid_template)

    def test_validation_missing_variables(self):
        template = "Hello {{ name }} from {{ company }}!"
        # Missing 'company'
        with self.assertRaises(InvalidPrompt):
            self.validator.validate_variables(template, {"name": "Alice"})

    def test_validation_unknown_variables(self):
        template = "Hello {{ name }}!"
        # Extra 'age'
        with self.assertRaises(InvalidPrompt):
            self.validator.validate_variables(template, {"name": "Alice", "age": 30})

    def test_empty_rendered_prompt(self):
        # Render yields spaces only
        with self.assertRaises(InvalidPrompt):
            self.validator.validate_rendered_content("   \n  ")


class TestAIService(unittest.IsolatedAsyncioTestCase):
    """Isolated asyncio tests for AIService execution, retries, caching, metrics."""

    def setUp(self):
        # Create a mock provider
        self.mock_provider = MagicMock(spec=BaseAIProvider)
        self.mock_provider.provider_name = "mock_provider"
        self.mock_provider.client = MagicMock()
        self.mock_provider.client.model = "mock-model"

        # Create a clean registry and register a test template
        self.registry = PromptRegistry()
        meta = PromptMetadata(
            name="test_service",
            version="1.0.0",
            description="Testing AI Service",
            last_updated="2026-07-01"
        )
        self.template = PromptTemplate(
            metadata=meta,
            template_body="Evaluate student: {{ student_name }} in {{ subject }}."
        )
        self.registry.register_prompt("career", self.template)

        # Initialize the AI service
        self.service = AIService(provider=self.mock_provider, registry=self.registry)
        ai_metrics.reset()

    async def test_successful_execution_and_metrics(self):
        # Prepare mock provider response
        provider_res = AIResponse(
            text="Student passed",
            model="mock-model",
            provider="mock_provider",
            usage={"prompt_tokens": 15, "completion_tokens": 5, "total_tokens": 20},
            raw_response={"status": "ok"},
            duration_ms=45.0
        )
        self.mock_provider.generate = AsyncMock(return_value=provider_res)

        variables = {"student_name": "Alice", "subject": "Math"}
        
        response = await self.service.execute(
            category="career",
            name="test_service",
            variables=variables,
            parser_type="text"
        )

        # Check response details
        self.assertEqual(response.parsed_response, "Student passed")
        self.assertEqual(response.provider, "mock_provider")
        self.assertEqual(response.usage.total_tokens, 20)
        self.assertEqual(response.prompt_version, "1.0.0")

        # Verify metrics updated
        metrics = ai_metrics.get_metrics()
        self.assertEqual(metrics["successes"], 1)
        self.assertEqual(metrics["failures"], 0)
        self.assertEqual(metrics["cache_misses"], 1)

    async def test_cache_hit_orchestration(self):
        provider_res = AIResponse(
            text="Student passed",
            model="mock-model",
            provider="mock_provider",
            usage={},
            raw_response={},
            duration_ms=10.0
        )
        self.mock_provider.generate = AsyncMock(return_value=provider_res)
        variables = {"student_name": "Bob", "subject": "Science"}

        # First run (miss)
        res1 = await self.service.execute(
            category="career",
            name="test_service",
            variables=variables,
            parser_type="text"
        )
        # Second run (hit)
        res2 = await self.service.execute(
            category="career",
            name="test_service",
            variables=variables,
            parser_type="text"
        )

        self.assertEqual(res1.parsed_response, res2.parsed_response)
        # Provider should have been generated only once
        self.mock_provider.generate.assert_called_once()

        metrics = ai_metrics.get_metrics()
        self.assertEqual(metrics["cache_hits"], 1)
        self.assertEqual(metrics["cache_misses"], 1)

    async def test_transient_retry_success(self):
        # First call fails due to timeout, second call succeeds
        provider_res = AIResponse(
            text="Success after retry",
            model="mock-model",
            provider="mock_provider",
            usage={},
            raw_response={},
            duration_ms=12.0
        )
        
        # AsyncMock side_effect sequence
        self.mock_provider.generate = AsyncMock()
        self.mock_provider.generate.side_effect = [
            AIRequestTimeout("Request timed out"),
            provider_res
        ]

        variables = {"student_name": "Charlie", "subject": "History"}
        
        # Mock asyncio.sleep to avoid waiting during test execution
        with patch("asyncio.sleep", return_value=None) as mock_sleep:
            response = await self.service.execute(
                category="career",
                name="test_service",
                variables=variables,
                parser_type="text"
            )
            
            self.assertEqual(response.parsed_response, "Success after retry")
            self.assertEqual(self.mock_provider.generate.call_count, 2)
            mock_sleep.assert_called_once_with(1.0) # initial retry delay

            # Verify metrics recorded retry and success
            metrics = ai_metrics.get_metrics()
            self.assertEqual(metrics["successes"], 1)
            self.assertEqual(metrics["retries"], 1)
            self.assertEqual(metrics["failures"], 0)

    async def test_transient_retry_exhaust_failure(self):
        # Provider keeps raising timeout
        self.mock_provider.generate = AsyncMock(
            side_effect=AIRequestTimeout("Timeout error always")
        )
        variables = {"student_name": "Dana", "subject": "Art"}

        with patch("asyncio.sleep", return_value=None) as mock_sleep:
            with self.assertRaises(AIRequestTimeout):
                await self.service.execute(
                    category="career",
                    name="test_service",
                    variables=variables
                )
            
            # 1 initial attempt + 3 retries (since settings.AI_RETRY_COUNT = 3) = 4 calls total
            self.assertEqual(self.mock_provider.generate.call_count, 4)
            self.assertEqual(mock_sleep.call_count, 3)

            # Verify failure metrics
            metrics = ai_metrics.get_metrics()
            self.assertEqual(metrics["failures"], 1)
            self.assertEqual(metrics["retries"], 3)
            self.assertEqual(metrics["successes"], 0)

    async def test_non_transient_failure_no_retry(self):
        # ValueError is not transient, so it shouldn't trigger retry
        self.mock_provider.generate = AsyncMock(
            side_effect=ValueError("A fatal local validation error")
        )
        variables = {"student_name": "Dana", "subject": "Art"}

        with patch("asyncio.sleep", return_value=None) as mock_sleep:
            with self.assertRaises(ValueError):
                await self.service.execute(
                    category="career",
                    name="test_service",
                    variables=variables
                )
            
            # Immediately raised, so call_count is 1 and retries is 0
            self.assertEqual(self.mock_provider.generate.call_count, 1)
            mock_sleep.assert_not_called()

            # Verify metrics
            metrics = ai_metrics.get_metrics()
            self.assertEqual(metrics["failures"], 1)
            self.assertEqual(metrics["retries"], 0)


if __name__ == "__main__":
    unittest.main()
