import os
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

import structlog
from app.ai.prompts.registry import PromptRegistry
from app.ai.prompts.renderer import PromptRenderer
from app.ai.prompts.validator import PromptValidator
from app.ai.cache.prompt_cache import PromptCache
from app.ai.metrics import ai_metrics
from app.ai.config import (
    PROMPT_CACHE_ENABLED,
    PROMPT_CACHE_TTL,
    PROMPT_TEMPLATE_PATH,
    AI_RETRY_COUNT
)
from app.ai.providers.base import BaseAIProvider
from app.ai.schemas.ai import AIRequest
from app.ai.schemas.ai_response import AIStructuredResponse, TokenUsage
from app.ai.parsers.text_parser import parse_text
from app.ai.parsers.json_parser import parse_json
from app.ai.parsers.markdown_parser import extract_code_block, parse_json_from_markdown
from app.ai.exceptions import (
    AIRequestTimeout,
    AIProviderUnavailable,
    ResponseParsingError
)

logger = structlog.get_logger()

# Process-wide cached registry to load templates only once.
_global_registry = PromptRegistry()
_global_registry_loaded = False
_registry_lock = threading_lock = asyncio.Lock()  # Lock for concurrent initialization if needed

class AIService:
    """Core AI Service Layer orchestrating validation, rendering, retries, caching, and parsing."""

    def __init__(self, provider: BaseAIProvider, registry: Optional[PromptRegistry] = None):
        """Initialize the AI Service.

        Args:
            provider: The concrete active AI provider (e.g. OllamaProvider).
            registry: Optional custom registry override. Defaults to process-wide global registry.
        """
        self.provider = provider
        self.renderer = PromptRenderer()
        self.validator = PromptValidator()
        self.cache = PromptCache()
        self.registry = registry or _global_registry

        # Initialize the global registry if it has not been loaded yet
        global _global_registry_loaded
        if not _global_registry_loaded and registry is None:
            template_path = PROMPT_TEMPLATE_PATH
            # Resolve relative template path against backend root if not absolute
            if not os.path.isabs(template_path):
                base_dir = os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.dirname(os.path.abspath(__file__))
                        )
                    )
                )
                template_path = os.path.join(base_dir, template_path)

            logger.info("loading_prompts_from_directory", path=template_path)
            try:
                self.registry.load_from_directory(template_path)
                _global_registry_loaded = True
            except Exception as e:
                logger.error("failed_to_initialize_prompts", path=template_path, error=str(e))
                # Do not block execution entirely, but log the error
                pass

    async def execute(
        self,
        category: str,
        name: str,
        variables: Dict[str, Any],
        parser_type: str = "text",
        version: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> AIStructuredResponse:
        """Render, validate, call provider with retries, cache, and parse the LLM response.

        Args:
            category: The prompt template category.
            name: The prompt template name.
            variables: Context variables to render in the prompt.
            parser_type: Parse strategy to use ('text', 'json', 'markdown', 'markdown_json').
            version: Target version of the prompt. If None, uses latest.
            system_prompt: Optional override for the LLM system prompt instructions.
            temperature: Sampling temperature (0.0 to 1.0).
            top_p: Nucleus sampling probability.
            max_tokens: Maximum tokens to generate.
            options: Additional provider-specific configurations.

        Returns:
            The structured AI response schema.

        Raises:
            InvalidPrompt: If variables do not match template parameters or render is empty.
            ResponseParsingError: If LLM response fails validation or format parser.
            AIError: For failures originating from providers or retry exhausts.
        """
        # 1. Retrieve prompt template
        template = self.registry.get_prompt(category, name, version)

        # 2. Validate input variables
        self.validator.validate_variables(template.template_body, variables)

        # Get active model name
        model_name = "unknown"
        if hasattr(self.provider, "client") and hasattr(self.provider.client, "model"):
            model_name = self.provider.client.model

        # 3. Check Cache (if enabled)
        if PROMPT_CACHE_ENABLED:
            cached_res = self.cache.get(
                provider=self.provider.provider_name,
                model=model_name,
                prompt_version=template.metadata.version,
                variables=variables
            )
            if cached_res:
                ai_metrics.record_cache_hit(
                    provider=self.provider.provider_name,
                    model=model_name,
                    prompt_version=template.metadata.version
                )
                return cached_res
            else:
                ai_metrics.record_cache_miss(
                    provider=self.provider.provider_name,
                    model=model_name,
                    prompt_version=template.metadata.version
                )

        # 4. Render template
        rendered_prompt = self.renderer.render(template.template_body, variables)

        # 5. Validate rendered template output
        self.validator.validate_rendered_content(rendered_prompt)

        # Get shared system prompt if registered
        base_system_prompt = ""
        try:
            sys_template = self.registry.get_prompt("shared", "system_prompt")
            base_system_prompt = sys_template.template_body
        except Exception:
            pass

        # Combine with custom system prompt if provided
        final_system_prompt = base_system_prompt
        if system_prompt:
            if final_system_prompt:
                final_system_prompt = f"{final_system_prompt}\n\n{system_prompt}"
            else:
                final_system_prompt = system_prompt
        else:
            final_system_prompt = final_system_prompt or None

        # 6. Call Provider with Transient Retries (Exponential Backoff)
        retries = AI_RETRY_COUNT
        delay = 1.0
        backoff_factor = 2.0
        start_time = time.perf_counter()
        provider_response = None

        for attempt in range(retries + 1):
            try:
                req = AIRequest(
                    prompt=rendered_prompt,
                    system_prompt=final_system_prompt,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    options=options
                )
                provider_response = await self.provider.generate(req)
                break
            except (AIRequestTimeout, AIProviderUnavailable) as e:
                if attempt < retries:
                    ai_metrics.record_retry(
                        provider=self.provider.provider_name,
                        model=model_name,
                        prompt_version=template.metadata.version,
                        attempt=attempt + 1,
                        error=str(e)
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
                else:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    ai_metrics.record_failure(
                        provider=self.provider.provider_name,
                        model=model_name,
                        prompt_version=template.metadata.version,
                        duration_ms=duration_ms,
                        error=str(e)
                    )
                    raise
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                ai_metrics.record_failure(
                    provider=self.provider.provider_name,
                    model=model_name,
                    prompt_version=template.metadata.version,
                    duration_ms=duration_ms,
                    error=str(e)
                )
                raise

        duration_ms = (time.perf_counter() - start_time) * 1000

        # 7. Parse response
        try:
            if parser_type == "json":
                parsed = parse_json(provider_response.text)
            elif parser_type == "markdown_json":
                parsed = parse_json_from_markdown(provider_response.text)
            elif parser_type == "markdown":
                parsed = extract_code_block(provider_response.text)
            else:
                parsed = parse_text(provider_response.text)
        except ResponseParsingError as e:
            ai_metrics.record_failure(
                provider=self.provider.provider_name,
                model=model_name,
                prompt_version=template.metadata.version,
                duration_ms=duration_ms,
                error=str(e)
            )
            raise

        # 8. Record success metric
        ai_metrics.record_success(
            provider=self.provider.provider_name,
            model=model_name,
            prompt_version=template.metadata.version,
            duration_ms=duration_ms
        )

        # 9. Structure final response
        usage_dict = provider_response.usage or {}
        usage = TokenUsage(
            prompt_tokens=usage_dict.get("prompt_tokens", 0),
            completion_tokens=usage_dict.get("completion_tokens", 0),
            total_tokens=usage_dict.get("total_tokens", 0)
        )

        structured_response = AIStructuredResponse(
            provider=provider_response.provider,
            model=provider_response.model,
            latency_ms=duration_ms,
            prompt_version=template.metadata.version,
            created_at=datetime.utcnow(),
            raw_response=provider_response.raw_response,
            parsed_response=parsed,
            usage=usage,
            token_fields={}
        )

        # 10. Write to cache
        if PROMPT_CACHE_ENABLED:
            self.cache.set(
                provider=self.provider.provider_name,
                model=model_name,
                prompt_version=template.metadata.version,
                variables=variables,
                response=structured_response,
                ttl=PROMPT_CACHE_TTL
            )

        return structured_response
