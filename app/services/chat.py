import hashlib
import time
import uuid

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import redis_client
from app.models.chat_request import ChatRequest
from app.models.user import User
from app.services.llm import (
    LLMProvider,
    LLMResult,
    _fallback_eligible,
    build_fallback_provider,
)


class ChatFailure(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class ChatService:
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.fallback_provider = build_fallback_provider()
        self.settings = get_settings()

    async def aclose(self) -> None:
        for provider in (self.provider, self.fallback_provider):
            close = getattr(provider, "aclose", None)
            if close is not None:
                await close()

    async def _cached(self, question: str) -> LLMResult | None:
        if not self.settings.cache_enabled:
            return None
        digest = hashlib.sha256(" ".join(question.lower().split()).encode()).hexdigest()
        cache_model = (
            self.settings.groq_model
            if self.settings.llm_provider == "groq"
            else self.settings.openai_model
        )
        try:
            value = await redis_client.get(
                f"llm-cache:v1:{self.settings.llm_provider}:{cache_model}:{digest}"
            )
            if value:
                import json

                try:
                    cached = LLMResult(**json.loads(value))
                    return LLMResult(
                        answer=cached.answer,
                        model=cached.model,
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                    )
                except (ValueError, TypeError):
                    return None
        except (RedisError, OSError) as exc:
            if self.settings.redis_fail_mode == "closed":
                raise ChatFailure(503, "Cache service unavailable") from exc
        return None

    async def _save_cache(self, question: str, result: LLMResult) -> None:
        if not self.settings.cache_enabled:
            return
        digest = hashlib.sha256(" ".join(question.lower().split()).encode()).hexdigest()
        cache_model = (
            self.settings.groq_model
            if self.settings.llm_provider == "groq"
            else self.settings.openai_model
        )
        try:
            import json

            await redis_client.setex(
                f"llm-cache:v1:{self.settings.llm_provider}:{cache_model}:{digest}",
                self.settings.cache_ttl_seconds,
                json.dumps(result.__dict__),
            )
        except (RedisError, OSError) as exc:
            if self.settings.redis_fail_mode == "closed":
                raise ChatFailure(503, "Cache service unavailable") from exc

    async def _limit(self, user_id: int) -> None:
        key = f"rate-limit:v1:{user_id}"
        try:
            async with redis_client.pipeline(transaction=True) as pipe:
                await pipe.incr(key)
                (count,) = await pipe.execute()
                if count == 1:
                    await redis_client.expire(key, self.settings.rate_limit_window_seconds)
            if count > self.settings.rate_limit_requests:
                raise ChatFailure(429, "Rate limit exceeded; try again later")
        except ChatFailure:
            raise
        except (RedisError, OSError) as exc:
            if self.settings.redis_fail_mode == "closed":
                raise ChatFailure(503, "Rate limiting service unavailable") from exc

    async def execute(
        self, question: str, user: User, db: AsyncSession, request_id: str | None = None
    ):
        request_id = request_id or str(uuid.uuid4())
        await self._limit(user.id)
        started = time.perf_counter()
        status, error_type = "success", None
        result = None
        try:
            result = await self._cached(question)
            if result is None:
                try:
                    result = await self.provider.answer(question)
                except Exception as exc:
                    if self.fallback_provider is None or not _fallback_eligible(exc):
                        raise
                    result = await self.fallback_provider.answer(question)
                await self._save_cache(question, result)
        except ChatFailure as exc:
            status, error_type = "error", type(exc).__name__
            await self._persist(db, request_id, user, question, result, started, status, error_type)
            raise
        except (APITimeoutError, TimeoutError) as exc:
            status, error_type = "error", type(exc).__name__
            await self._persist(db, request_id, user, question, result, started, status, error_type)
            raise ChatFailure(504, "LLM request timed out") from exc
        except RateLimitError as exc:
            status, error_type = "error", type(exc).__name__
            await self._persist(db, request_id, user, question, result, started, status, error_type)
            raise ChatFailure(429, "LLM provider rate limit reached") from exc
        except (AuthenticationError, BadRequestError) as exc:
            status, error_type = "error", type(exc).__name__
            await self._persist(db, request_id, user, question, result, started, status, error_type)
            raise ChatFailure(502, "LLM provider rejected the configured request") from exc
        except (APIConnectionError, APIStatusError) as exc:
            status, error_type = "error", type(exc).__name__
            await self._persist(db, request_id, user, question, result, started, status, error_type)
            raise ChatFailure(502, "LLM provider is unavailable") from exc
        except Exception as exc:
            status, error_type = "error", type(exc).__name__
            await self._persist(db, request_id, user, question, result, started, status, error_type)
            raise ChatFailure(500, "Unexpected chat service error") from exc
        latency = int((time.perf_counter() - started) * 1000)
        await self._persist(db, request_id, user, question, result, started, status, error_type)
        return result, latency, request_id

    async def _persist(self, db, request_id, user, question, result, started, status, error_type):
        latency = int((time.perf_counter() - started) * 1000)
        db.add(
            ChatRequest(
                request_id=request_id,
                user_id=user.id,
                question=question,
                answer=result.answer if result else None,
                model=result.model if result else None,
                prompt_tokens=result.prompt_tokens if result else None,
                completion_tokens=result.completion_tokens if result else None,
                total_tokens=result.total_tokens if result else None,
                latency_ms=latency,
                status=status,
                error_type=error_type,
            )
        )
        await db.commit()
