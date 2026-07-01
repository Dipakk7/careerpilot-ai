import time
from typing import Dict, Any, List, Optional
from app.ai.providers.base import BaseAIProvider
from app.ai.clients.ollama_client import OllamaClient
from app.ai.schemas.ai import AIRequest, AIResponse
from app.ai.logging import log_ai_request


class OllamaProvider(BaseAIProvider):
    """An AI provider for local Ollama server integration."""

    def __init__(self, host: str, model: str, timeout: float = 60.0):
        self.client = OllamaClient(host=host, model=model, timeout=timeout)
        self.provider_name = "ollama"

    async def generate(self, request: AIRequest) -> AIResponse:
        """Call Ollama generation endpoint and parse result."""
        start_time = time.perf_counter()
        options = {
            "temperature": request.temperature if request.temperature is not None else 0.3,
            "top_p": request.top_p if request.top_p is not None else 0.9,
            "num_predict": request.max_tokens if request.max_tokens is not None else 2048
        }
        if request.options:
            options.update(request.options)

        success = False
        error_msg = None
        raw_res = {}
        try:
            raw_res = await self.client.generate(
                prompt=request.prompt,
                system=request.system_prompt,
                options=options
            )
            success = True

            prompt_tokens = raw_res.get("prompt_eval_count", 0)
            completion_tokens = raw_res.get("eval_count", 0)
            total_tokens = prompt_tokens + completion_tokens

            duration_ms = (time.perf_counter() - start_time) * 1000

            return AIResponse(
                text=raw_res.get("response", ""),
                model=self.client.model,
                provider=self.provider_name,
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                },
                raw_response=raw_res,
                duration_ms=duration_ms
            )

        except Exception as e:
            error_msg = str(e)
            raise

        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            log_ai_request(
                provider=self.provider_name,
                model=self.client.model,
                duration_ms=duration_ms,
                success=success,
                error=error_msg,
                input_tokens=raw_res.get("prompt_eval_count") if success else None,
                output_tokens=raw_res.get("eval_count") if success else None
            )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        **kwargs
    ) -> AIResponse:
        """Call Ollama chat completions endpoint and parse result."""
        start_time = time.perf_counter()
        options = {
            "temperature": kwargs.get("temperature", 0.3),
            "top_p": kwargs.get("top_p", 0.9),
            "num_predict": kwargs.get("max_tokens", 2048)
        }
        if "options" in kwargs and kwargs["options"]:
            options.update(kwargs["options"])

        chat_messages = list(messages)
        if system:
            chat_messages.insert(0, {"role": "system", "content": system})

        success = False
        error_msg = None
        raw_res = {}
        try:
            raw_res = await self.client.chat(
                messages=chat_messages,
                options=options
            )
            success = True

            prompt_tokens = raw_res.get("prompt_eval_count", 0)
            completion_tokens = raw_res.get("eval_count", 0)
            total_tokens = prompt_tokens + completion_tokens

            duration_ms = (time.perf_counter() - start_time) * 1000
            message_obj = raw_res.get("message", {})

            return AIResponse(
                text=message_obj.get("content", ""),
                model=self.client.model,
                provider=self.provider_name,
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                },
                raw_response=raw_res,
                duration_ms=duration_ms
            )

        except Exception as e:
            error_msg = str(e)
            raise

        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            log_ai_request(
                provider=self.provider_name,
                model=self.client.model,
                duration_ms=duration_ms,
                success=success,
                error=error_msg,
                input_tokens=raw_res.get("prompt_eval_count") if success else None,
                output_tokens=raw_res.get("eval_count") if success else None
            )

    async def health_check(self) -> Dict[str, Any]:
        """Perform health checking of the Ollama server."""
        return await self.client.health_check()
