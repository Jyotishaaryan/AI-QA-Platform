from dataclasses import dataclass
from typing import Protocol

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_random_exponential

from app.core.config import get_settings


@dataclass
class LLMResult:
    answer: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class LLMProvider(Protocol):
    async def answer(self, question: str) -> LLMResult: ...


def _transient(exc: BaseException) -> bool:
    return isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError)) or (
        isinstance(exc, APIStatusError) and exc.status_code >= 500
    )


def _fallback_eligible(exc: BaseException) -> bool:
    return _transient(exc)


class OpenAICompatibleProvider:
    def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
        settings = get_settings()
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key or "missing",
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
            base_url=base_url,
        )
        self.attempts = max(1, settings.llm_max_retries + 1)

    async def aclose(self) -> None:
        await self.client.close()

    async def answer(self, question: str) -> LLMResult:
        @retry(
            retry=retry_if_exception(_transient),
            stop=stop_after_attempt(self.attempts),
            wait=wait_random_exponential(multiplier=0.5, max=4),
            reraise=True,
        )
        async def call():
            return await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": question}],
            )

        response = await call()
        content = response.choices[0].message.content or ""
        usage = response.usage
        return LLMResult(
            answer=content,
            model=response.model,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
        )


class OpenAIProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        super().__init__(api_key or settings.openai_api_key, model or settings.openai_model)


class GroqProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        super().__init__(
            api_key or settings.groq_api_key,
            model or settings.groq_model,
            base_url="https://api.groq.com/openai/v1",
        )


def build_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "groq":
        return GroqProvider()
    if settings.llm_provider == "openai":
        return OpenAIProvider()
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


def build_fallback_provider() -> LLMProvider | None:
    settings = get_settings()
    if (
        not settings.llm_fallback_enabled
        or not settings.fallback_provider
        or not settings.fallback_api_key
    ):
        return None
    if settings.fallback_provider == "groq":
        return GroqProvider(api_key=settings.fallback_api_key, model=settings.fallback_model)
    if settings.fallback_provider == "openai":
        return OpenAIProvider(api_key=settings.fallback_api_key, model=settings.fallback_model)
    raise RuntimeError(f"Unsupported FALLBACK_PROVIDER: {settings.fallback_provider}")
