import httpx
import json
from typing import Dict, Any, List, Optional, AsyncGenerator
from app.ai.exceptions import (
    AIProviderUnavailable,
    ModelNotFound,
    AIRequestTimeout,
    AIError
)


class OllamaClient:
    """A reusable asynchronous client for communicating with a local Ollama server."""

    def __init__(self, host: str, model: str, timeout: float = 60.0):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def health_check(self) -> Dict[str, Any]:
        """Verify the Ollama server is reachable and the configured model is available.

        Returns:
            Dict containing health status and details.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # 1. Test connection to server root
                try:
                    response = await client.get(self.host)
                    if response.status_code != 200:
                        return {
                            "status": "unhealthy",
                            "error": f"Server responded with status code {response.status_code}"
                        }
                except (httpx.ConnectError, httpx.NetworkError) as e:
                    return {
                        "status": "unhealthy",
                        "error": f"Ollama server is not reachable at {self.host}: {str(e)}"
                    }

                # 2. Check for configured model availability
                try:
                    tags_response = await client.get(f"{self.host}/api/tags")
                    if tags_response.status_code == 200:
                        data = tags_response.json()
                        models = data.get("models", [])

                        available_names = []
                        for m in models:
                            if m.get("name"):
                                available_names.append(m["name"])
                            if m.get("model"):
                                available_names.append(m["model"])

                        # Distinct available names
                        available_names = list(set(available_names))

                        # Perform matching: exact match or tag fallback
                        target = self.model
                        found = False
                        for name in available_names:
                            if (
                                name == target
                                or name == f"{target}:latest"
                                or target == f"{name}:latest"
                            ):
                                found = True
                                break

                        if found:
                            return {
                                "status": "healthy",
                                "message": "Ollama server is active and model is available.",
                                "model": self.model
                            }
                        else:
                            return {
                                "status": "unhealthy",
                                "error": (
                                    f"Model '{self.model}' is not downloaded/available. "
                                    f"Available models: {available_names}"
                                )
                            }
                    else:
                        return {
                            "status": "unhealthy",
                            "error": f"Failed to fetch tags: HTTP {tags_response.status_code}"
                        }
                except Exception as e:
                    return {
                        "status": "unhealthy",
                        "error": f"Failed to verify model: {str(e)}"
                    }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": f"Unexpected health check failure: {str(e)}"
            }

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Perform a direct generation request to Ollama /api/generate.

        Args:
            prompt: Input text prompt.
            system: Optional system instruction.
            options: Optional generation parameters (temperature, top_p, etc.).
            stream: Flag to enable stream mode.

        Returns:
            Parsed response JSON from Ollama.
        """
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream
        }
        if system:
            payload["system"] = system
        if options:
            payload["options"] = options

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException as e:
            raise AIRequestTimeout(f"Ollama request timed out: {str(e)}")
        except (httpx.ConnectError, httpx.NetworkError) as e:
            raise AIProviderUnavailable(f"Ollama server is unreachable: {str(e)}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ModelNotFound(f"Model '{self.model}' not found on Ollama server: {e.response.text}")
            raise AIError(f"Ollama server returned error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise AIError(f"Unexpected error in Ollama client: {str(e)}")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Perform a chat completions request to Ollama /api/chat.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            options: Optional generation parameters.
            stream: Flag to enable stream mode.

        Returns:
            Parsed response JSON from Ollama.
        """
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream
        }
        if options:
            payload["options"] = options

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException as e:
            raise AIRequestTimeout(f"Ollama chat request timed out: {str(e)}")
        except (httpx.ConnectError, httpx.NetworkError) as e:
            raise AIProviderUnavailable(f"Ollama server is unreachable: {str(e)}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ModelNotFound(f"Model '{self.model}' not found on Ollama server: {e.response.text}")
            raise AIError(f"Ollama server returned error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise AIError(f"Unexpected error in Ollama chat client: {str(e)}")

    async def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream chunks from /api/generate.

        Args:
            prompt: Input text prompt.
            system: Optional system instruction.
            options: Optional parameters.

        Yields:
            Decoded JSON chunks from the server stream.
        """
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True
        }
        if system:
            payload["system"] = system
        if options:
            payload["options"] = options

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            yield json.loads(line)

        except httpx.TimeoutException as e:
            raise AIRequestTimeout(f"Ollama stream request timed out: {str(e)}")
        except (httpx.ConnectError, httpx.NetworkError) as e:
            raise AIProviderUnavailable(f"Ollama server is unreachable: {str(e)}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ModelNotFound(f"Model '{self.model}' not found on Ollama server: {e.response.text}")
            raise AIError(f"Ollama server returned error {e.response.status_code} during stream: {e.response.text}")
        except Exception as e:
            raise AIError(f"Unexpected error in Ollama streaming: {str(e)}")

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream chunks from /api/chat.

        Args:
            messages: List of message dicts.
            options: Optional parameters.

        Yields:
            Decoded JSON chunks from the server stream.
        """
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True
        }
        if options:
            payload["options"] = options

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            yield json.loads(line)

        except httpx.TimeoutException as e:
            raise AIRequestTimeout(f"Ollama chat stream timed out: {str(e)}")
        except (httpx.ConnectError, httpx.NetworkError) as e:
            raise AIProviderUnavailable(f"Ollama server is unreachable: {str(e)}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ModelNotFound(f"Model '{self.model}' not found on Ollama server: {e.response.text}")
            raise AIError(f"Ollama server returned error {e.response.status_code} during chat stream: {e.response.text}")
        except Exception as e:
            raise AIError(f"Unexpected error in Ollama chat streaming: {str(e)}")
