from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.config import get_settings
from app.core.database import get_db
from app.core.redis import redis_client
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas import ChatInput, ChatOutput, LoginRequest, TokenResponse, Usage, UserOutput
from app.services.chat import ChatFailure, ChatService
from app.services.llm import build_provider

router = APIRouter()
chat_service = ChatService(build_provider())


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    tags=["authentication"],
    description="Exchange development or registered credentials for a short-lived JWT.",
)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.username == payload.username))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            401, "Invalid username or password", headers={"WWW-Authenticate": "Bearer"}
        )
    return TokenResponse(access_token=create_access_token(str(user.id), user.role))


@router.get("/me", response_model=UserOutput, tags=["authentication"])
async def me(user: User = Depends(get_current_user)):
    return user


@router.post(
    "/chat",
    response_model=ChatOutput,
    tags=["chat"],
    description="Submit a question to the configured LLM. Requires USER or ADMIN role.",
)
async def chat(
    payload: ChatInput,
    request: Request,
    user: User = Depends(require_role("USER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    try:
        result, latency, request_id = await chat_service.execute(
            payload.question, user, db, getattr(request.state, "request_id", None)
        )
    except ChatFailure as exc:
        raise HTTPException(
            exc.status_code,
            exc.message,
            headers={"X-Request-ID": getattr(request.state, "request_id", "")},
        ) from exc
    return ChatOutput(
        answer=result.answer,
        request_id=request_id,
        latency_ms=latency,
        usage=Usage(
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
        ),
    )


@router.get("/health/live", tags=["health"])
async def live():
    return {"status": "alive"}


@router.get("/health/ready", tags=["health"])
async def ready(db: AsyncSession = Depends(get_db)):
    checks = {"database": False, "redis": False}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    try:
        checks["redis"] = bool(await redis_client.ping())
    except Exception:
        pass
    settings = get_settings()
    healthy = checks["database"] and (checks["redis"] or settings.redis_fail_mode == "open")
    return JSONResponse(
        {"status": "ready" if healthy else "not_ready", "checks": checks},
        status_code=200 if healthy else 503,
    )


@router.get("/health", tags=["health"])
async def health():
    return await live()


@router.get(
    "/metrics", tags=["observability"], description="Prometheus metrics. Restricted to ADMIN JWTs."
)
async def metrics(user: User = Depends(require_role("ADMIN"))):
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
