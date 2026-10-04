import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram

from app.api.routes import chat_service, router
from app.core.config import get_settings
from app.core.database import engine
from app.core.redis import close_redis

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "path"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=get_settings().log_level)
    yield
    await chat_service.aclose()
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="AI-QA Platform",
    version="0.1.0",
    description="Authenticated, observable AI question-answering API",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in get_settings().cors_origins.split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.include_router(router)


@app.middleware("http")
async def observability(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    path = (
        request.url.path
        if request.url.path
        in {"/chat", "/auth/login", "/health", "/health/live", "/health/ready", "/metrics", "/me"}
        else "other"
    )
    REQUESTS.labels(request.method, path, str(response.status_code)).inc()
    LATENCY.labels(request.method, path).observe(elapsed)
    response.headers["X-Request-ID"] = request_id
    return response
