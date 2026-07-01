import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError
import httpx

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.core.config import Settings
from app.ai.clients.ollama_client import OllamaClient
from app.ai.providers.factory import AIProviderFactory
from app.ai.providers.ollama import OllamaProvider
from app.ai.schemas.ai import AIRequest
from app.ai.exceptions import (
    AIError,
    AIProviderUnavailable,
    ModelNotFound,
    AIRequestTimeout
)
from fastapi.testclient import TestClient


class TestAIFoundationConfig(unittest.TestCase):
    """Test configuration validation for AI settings."""

    def test_configuration_validation(self):
        # Valid settings instantiation should pass
        s = Settings(
            DATABASE_URL="sqlite://",
            JWT_SECRET_KEY="test_secret",
            AI_PROVIDER="ollama",
            OLLAMA_HOST="http://localhost:11434",
            OLLAMA_MODEL="qwen2.5:3b",
            AI_TEMPERATURE=0.3,
            AI_TOP_P=0.9,
            AI_MAX_TOKENS=2048,
            AI_TIMEOUT=60,
            AI_RETRY_COUNT=3
        )
        self.assertEqual(s.AI_PROVIDER, "ollama")

        # Test invalid provider name
        with self.assertRaises(ValidationError):
            Settings(
                DATABASE_URL="sqlite://",
                JWT_SECRET_KEY="test_secret",
                AI_PROVIDER="invalid_provider"
            )

        # Test invalid temperatures
        with self.assertRaises(ValidationError):
            Settings(
                DATABASE_URL="sqlite://",
                JWT_SECRET_KEY="test_secret",
                AI_TEMPERATURE=1.5
            )
        with self.assertRaises(ValidationError):
            Settings(
                DATABASE_URL="sqlite://",
                JWT_SECRET_KEY="test_secret",
                AI_TEMPERATURE=-0.1
            )

        # Test invalid top_p
        with self.assertRaises(ValidationError):
            Settings(
                DATABASE_URL="sqlite://",
                JWT_SECRET_KEY="test_secret",
                AI_TOP_P=2.0
            )

        # Test negative max_tokens
        with self.assertRaises(ValidationError):
            Settings(
                DATABASE_URL="sqlite://",
                JWT_SECRET_KEY="test_secret",
                AI_MAX_TOKENS=-1
            )

        # Test invalid timeout
        with self.assertRaises(ValidationError):
            Settings(
                DATABASE_URL="sqlite://",
                JWT_SECRET_KEY="test_secret",
                AI_TIMEOUT=0
            )

        # Test negative retry count
        with self.assertRaises(ValidationError):
            Settings(
                DATABASE_URL="sqlite://",
                JWT_SECRET_KEY="test_secret",
                AI_RETRY_COUNT=-1
            )


class TestAIProviderFactory(unittest.TestCase):
    """Test AIProviderFactory behavior."""

    def test_factory_resolves_ollama(self):
        provider = AIProviderFactory.get_provider("ollama")
        self.assertIsInstance(provider, OllamaProvider)
        self.assertEqual(provider.provider_name, "ollama")

    def test_factory_unsupported_provider(self):
        with self.assertRaises(AIError):
            AIProviderFactory.get_provider("unsupported_provider")


class TestAIFoundationAsync(unittest.IsolatedAsyncioTestCase):
    """Asynchronous tests for Ollama client and provider."""

    async def test_ollama_client_generate_success(self):
        client = OllamaClient(host="http://localhost:11434", model="qwen2.5:3b")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Hello world",
            "prompt_eval_count": 10,
            "eval_count": 20
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            res = await client.generate(prompt="Hello")
            self.assertEqual(res["response"], "Hello world")
            mock_post.assert_called_once()

    async def test_ollama_client_chat_success(self):
        client = OllamaClient(host="http://localhost:11434", model="qwen2.5:3b")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Chat reply"},
            "prompt_eval_count": 5,
            "eval_count": 15
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            res = await client.chat(messages=[{"role": "user", "content": "Hi"}])
            self.assertEqual(res["message"]["content"], "Chat reply")

    async def test_ollama_client_timeout(self):
        client = OllamaClient(host="http://localhost:11434", model="qwen2.5:3b")
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timeout")):
            with self.assertRaises(AIRequestTimeout):
                await client.generate(prompt="Hello")

    async def test_ollama_client_unavailable(self):
        client = OllamaClient(host="http://localhost:11434", model="qwen2.5:3b")
        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("connection error")):
            with self.assertRaises(AIProviderUnavailable):
                await client.generate(prompt="Hello")

    async def test_ollama_client_model_not_found(self):
        client = OllamaClient(host="http://localhost:11434", model="qwen2.5:3b")
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "model not found"

        with patch("httpx.AsyncClient.post", side_effect=httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)):
            with self.assertRaises(ModelNotFound):
                await client.generate(prompt="Hello")

    async def test_ollama_provider_generate_success(self):
        provider = OllamaProvider(host="http://localhost:11434", model="qwen2.5:3b")

        mock_res = {
            "response": "Generated reply",
            "prompt_eval_count": 12,
            "eval_count": 18
        }
        with patch.object(OllamaClient, "generate", return_value=mock_res) as mock_gen:
            req = AIRequest(prompt="Write a resume summary", system_prompt="Be professional", temperature=0.5)
            response = await provider.generate(req)
            self.assertEqual(response.text, "Generated reply")
            self.assertEqual(response.usage["prompt_tokens"], 12)
            self.assertEqual(response.usage["completion_tokens"], 18)
            self.assertEqual(response.usage["total_tokens"], 30)
            self.assertEqual(response.provider, "ollama")
            mock_gen.assert_called_once()

    async def test_ollama_provider_health_check_healthy(self):
        provider = OllamaProvider(host="http://localhost:11434", model="qwen2.5:3b")

        mock_health = {
            "status": "healthy",
            "message": "Ollama is active",
            "model": "qwen2.5:3b"
        }
        with patch.object(OllamaClient, "health_check", return_value=mock_health):
            res = await provider.health_check()
            self.assertEqual(res["status"], "healthy")

    async def test_ollama_provider_health_check_unhealthy(self):
        provider = OllamaProvider(host="http://localhost:11434", model="qwen2.5:3b")

        mock_health = {
            "status": "unhealthy",
            "error": "Model not found"
        }
        with patch.object(OllamaClient, "health_check", return_value=mock_health):
            res = await provider.health_check()
            self.assertEqual(res["status"], "unhealthy")


class TestAIHealthCheckEndpoint(unittest.TestCase):
    """Test health endpoint with mocked provider health status."""

    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint_healthy(self):
        mock_health = {
            "status": "healthy",
            "provider": "ollama",
            "model": "qwen2.5:3b",
            "response_time_ms": 10.0
        }

        async def mock_health_check(*args, **kwargs):
            return mock_health

        with patch("app.ai.providers.ollama.OllamaProvider.health_check", new=mock_health_check):
            response = self.client.get("/health")
            self.assertEqual(response.status_code, 200, f"Health endpoint failed: {response.text}")
            data = response.json()
            self.assertEqual(data["status"], "healthy")
            self.assertEqual(data["database"], "healthy")
            self.assertEqual(data["ai"]["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
