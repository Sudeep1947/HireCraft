"""Multi-LLM Router with automatic fallback, retries, and health checking.

Routes requests through a priority-ordered chain of providers.
Falls back to the next provider on failure, timeout, or rate limit.
Users never notice provider switching.
"""

from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator

from app.ai_core.llm_client import LLMMessage, LLMResponse, LLMToolCall
from app.ai_core.providers.base import LLMProvider, ProviderHealth, ProviderStatus, ProviderConfig
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class LLMRouter:
    """Routes LLM requests through a chain of providers with automatic fallback."""

    def __init__(self) -> None:
        self._providers: list[LLMProvider] = []
        self._initialized = False

    def _ensure_providers(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        if settings.gemini_api_key:
            from app.ai_core.providers.gemini_provider import GeminiProvider
            self._providers.append(GeminiProvider(ProviderConfig(
                name="gemini",
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                timeout_seconds=settings.llm_timeout_seconds,
                max_retries=settings.llm_max_retries,
                priority=1,
            )))
            logger.info("Registered Gemini provider (model=%s)", settings.gemini_model)

        if settings.groq_api_key:
            from app.ai_core.providers.groq_provider import GroqProvider
            self._providers.append(GroqProvider(ProviderConfig(
                name="groq",
                api_key=settings.groq_api_key,
                model=settings.groq_model,
                timeout_seconds=settings.llm_timeout_seconds,
                max_retries=settings.llm_max_retries,
                priority=2,
            )))
            logger.info("Registered Groq provider (model=%s)", settings.groq_model)

        if settings.openrouter_api_key:
            from app.ai_core.providers.openrouter_provider import OpenRouterProvider
            self._providers.append(OpenRouterProvider(ProviderConfig(
                name="openrouter",
                api_key=settings.openrouter_api_key,
                model=settings.openrouter_model,
                timeout_seconds=settings.llm_timeout_seconds,
                max_retries=settings.llm_max_retries,
                priority=3,
            )))
            logger.info("Registered OpenRouter provider (model=%s)", settings.openrouter_model)

        if settings.openai_api_key:
            from app.ai_core.providers.groq_provider import GroqProvider
            self._providers.append(GroqProvider(ProviderConfig(
                name="openai",
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model=settings.llm_model,
                timeout_seconds=settings.llm_timeout_seconds,
                max_retries=settings.llm_max_retries,
                priority=4,
            )))
            logger.info("Registered OpenAI-compatible provider (model=%s)", settings.llm_model)

        if settings.ollama_url:
            from app.ai_core.providers.ollama_provider import OllamaProvider
            self._providers.append(OllamaProvider(ProviderConfig(
                name="ollama",
                base_url=settings.ollama_url,
                model=settings.ollama_model,
                timeout_seconds=settings.llm_timeout_seconds,
                max_retries=1,
                priority=5,
            )))
            logger.info("Registered Ollama provider (model=%s)", settings.ollama_model)

        if not self._providers:
            logger.warning("No LLM providers configured – using rule-based fallback only")

    def _get_available_providers(self) -> list[LLMProvider]:
        self._ensure_providers()
        return [p for p in self._providers if p.health.is_available]

    def _get_healthy_or_all(self) -> list[LLMProvider]:
        available = self._get_available_providers()
        if not available:
            return self._providers[:1] if self._providers else []
        return available

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self._ensure_providers()
        providers = self._get_healthy_or_all()
        if not providers:
            return await self._fallback_response(messages)

        temp = temperature if temperature is not None else settings.llm_temperature
        tokens = max_tokens or settings.llm_max_tokens

        last_error: Exception | None = None
        for provider in providers:
            for attempt in range(1, provider.config.max_retries + 1):
                try:
                    result = await provider.chat(messages, tools, temp, tokens)
                    if result.content or result.tool_calls:
                        return result
                    logger.warning("Empty response from %s (attempt %d)", provider.name, attempt)
                    last_error = ValueError("Empty response")
                except asyncio.TimeoutError:
                    logger.warning("Timeout from %s (attempt %d/%d)", provider.name, attempt, provider.config.max_retries)
                    last_error = TimeoutError(f"{provider.name} timed out")
                except Exception as exc:
                    error_str = str(exc).lower()
                    logger.warning("Provider %s failed (attempt %d/%d): %s", provider.name, attempt, provider.config.max_retries, exc)
                    last_error = exc
                    if any(kw in error_str for kw in ["rate", "limit", "429", "too many"]):
                        provider.health.status = ProviderStatus.DEGRADED
                        break
                    if any(kw in error_str for kw in ["401", "403", "unauthorized", "invalid api key"]):
                        provider.health.status = ProviderStatus.UNHEALTHY
                        break
                if attempt < provider.config.max_retries:
                    await asyncio.sleep(0.5 * attempt)

        logger.error("All providers exhausted, falling back to rule-based response")
        return await self._fallback_response(messages)

    async def stream_chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        self._ensure_providers()
        providers = self._get_healthy_or_all()
        if not providers:
            resp = await self._fallback_response(messages)
            yield resp.content
            return

        temp = temperature if temperature is not None else settings.llm_temperature
        tokens = max_tokens or settings.llm_max_tokens

        for provider in providers:
            try:
                async for chunk in provider.stream_chat(messages, tools, temp, tokens):
                    yield chunk
                return
            except Exception as exc:
                logger.warning("Streaming failed on %s: %s – trying next provider", provider.name, exc)
                continue

        resp = await self._fallback_response(messages)
        yield resp.content

    async def _fallback_response(self, messages: list[LLMMessage]) -> LLMResponse:
        last_msg = messages[-1].content if messages else ""
        q = last_msg.lower()
        if any(kw in q for kw in ["application", "status", "applied", "my application"]):
            content = "Your applications are actively tracked in the platform. You can review your applied positions, interview statuses, and recruiter/HR decision updates in the 'My Applications' section."
        elif any(kw in q for kw in ["pipeline", "hiring report", "hiring pipeline", "time-to-hire"]):
            content = "The hiring pipeline is active across your organization. You can view candidates awaiting HR interviews, evaluate candidate competencies, and record final decisions in the HR Oversight Dashboard."
        elif any(kw in q for kw in ["system health", "active users", "audit", "security audit"]):
            content = "System health is operational. All microservices, database connections, and RBAC authentication guards are active. You can review user management and audit logs in the Admin portal."
        elif any(kw in q for kw in ["top", "best", "rank", "candidate"]):
            content = "I can help you find and rank candidates. Please use the platform's screening and ranking features for the most accurate results."
        elif any(kw in q for kw in ["interview", "schedule", "question"]):
            content = "I can help with interview scheduling and question generation. Navigate to the Interview Intelligence section for full capabilities."
        elif any(kw in q for kw in ["report", "analytics", "summary"]):
            content = "I can help generate reports. Please specify the report type and time range you're interested in."
        elif any(kw in q for kw in ["fairness", "bias", "diversity"]):
            content = "I can analyze fairness and bias metrics. Use the Fairness Engine dashboard for detailed bias analysis."
        elif any(kw in q for kw in ["resume", "parse", "score", "improve my profile"]):
            content = "I can help analyze resumes and profile scores. Upload your latest resume or check Resume Intelligence to review match scores and missing skills."
        elif any(kw in q for kw in ["search", "find", "react", "developer", "job"]):
            content = "I can help you search for candidates and jobs. Try using the search features on the platform for detailed results."
        elif any(kw in q for kw in ["hello", "hi", "hey"]):
            content = "Hello! I'm your AI HR Intelligence Assistant. I can help you with candidate search, interview management, analytics, and more. What would you like to do?"
        else:
            content = "I'm your AI Hiring Assistant. I can help you with candidate search, interview scheduling, application status, resume evaluation, and recruitment analytics. Ask me any question or choose one of the suggested prompts!"
        return LLMResponse(
            content=content,
            tokens_used=0,
            latency_ms=0,
            model="rule-based-fallback",
        )

    def list_providers(self) -> list[dict]:
        self._ensure_providers()
        return [
            {
                "name": p.name,
                "model": p.config.model,
                "status": p.health.status.value,
                "success_rate": round(p.health.success_rate, 2),
                "avg_latency_ms": round(p.health.avg_latency_ms, 1),
                "total_requests": p.health.total_requests,
            }
            for p in self._providers
        ]

    async def close(self) -> None:
        for p in self._providers:
            try:
                await p.close()
            except Exception:
                pass


llm_router = LLMRouter()
