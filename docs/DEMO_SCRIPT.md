# Five-minute demo script

## 0:00–0:30 — Overview and architecture

“This is AI-QA Platform: an authenticated FastAPI question-answering service. Requests pass through JWT and role checks, Redis rate limiting, a provider abstraction, and PostgreSQL metadata persistence. The LLM adapter can be swapped without changing the chat route.”

## 0:30–1:15 — Compose and services

“I’ll start the stack with `docker compose up --build`. Compose runs the API, PostgreSQL, and Redis, waits for health checks, and applies the Alembic migration. The API is non-root in its container. Swagger is available at `/docs`; readiness checks database and Redis status.”

## 1:15–2:00 — Login and JWT

“In a second terminal I seed local-only demo accounts, then call `/auth/login`. This returns a short-lived JWT with subject, role, issued-at, and expiry claims. Passwords are Argon2 hashes. Authorization is centralized, with USER and ADMIN able to chat and ADMIN alone able to read metrics.”

## 2:00–3:00 — Authenticated chat

“I send a question to `/chat` using the bearer token. The service applies a per-user Redis limit, checks the optional cache, and calls the Groq adapter on a miss. The response includes a correlation ID, latency, and token usage; PostgreSQL records useful metadata. The project uses a personal Groq free-tier key from the environment.”

## 3:00–3:30 — Redis and rate limit

“Redis holds shared counters so limits work across replicas, and can hold short-lived cache entries keyed by normalized question. Fail mode is configurable: open favors availability; closed favors strict enforcement. Cache should stay disabled or gain tenant context for private or personalized answers.”

## 3:30–4:00 — Metrics and health

“The liveness route shows the process is running. Readiness checks dependencies. As ADMIN, `/metrics` exposes Prometheus request counts and latency histograms. Request IDs are returned in a header for log correlation.”

## 4:00–4:40 — Tests and error behavior

“The tests use a mock provider and never need a real API key. Transient provider failures get a small jittered retry budget; invalid requests are not blindly retried. Timeouts, quota errors, and upstream failures map to explicit HTTP status codes. A real fallback only runs when configured.”

## 4:40–5:00 — Scale and engineering choices

“For 100 to 500 requests per second, I’d scale stateless API replicas behind a load balancer, use Redis quotas, watch provider RPM and TPM, and move long-running work to a durable queue. I’d use managed PostgreSQL and Redis, OIDC for enterprise identity, and autoscale on concurrency and latency as well as CPU. The main constraint is usually provider capacity, so scaling the API alone is not enough.”
