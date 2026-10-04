# Architecture and migration design

## Request path

```mermaid
sequenceDiagram
  participant C as Client
  participant I as Ingress/API gateway
  participant A as FastAPI
  participant R as Redis
  participant P as PostgreSQL
  participant L as LLM gateway/provider
  C->>I: HTTPS request + JWT
  I->>A: Route to healthy replica
  A->>A: Validate JWT, role, schema, request ID
  A->>R: Per-user quota; optional cache lookup
  alt cache hit
    R-->>A: Cached public answer
  else cache miss
    A->>L: Bounded call with retry policy
    L-->>A: Answer + token usage
  end
  A->>P: Persist request metadata and outcome
  A-->>C: Answer, usage, latency, request ID
```

## Scaling 100–500 requests/second

The service is stateless and can scale horizontally behind a load balancer. Set minimum replicas for baseline traffic, use readiness/liveness probes, and scale on CPU plus request concurrency/latency. HPA based only on CPU can miss an I/O-bound LLM bottleneck; custom metrics (in-flight calls, queue depth, p95 latency) improve decisions. Size workers and SQL pools together to avoid exhausting PostgreSQL connections. Redis rate limits are shared across replicas. Cache only context-independent public responses. A managed PostgreSQL service with backups, connection pooling, and read replicas helps separate reporting reads from writes. Groq's current free quota is small relative to 100–500 RPS; API replica scaling alone cannot reach that throughput without provider capacity and admission controls.

At 100 RPS, synchronous calls may already saturate provider RPM/TPM or concurrent request quotas. Apply admission control and tenant quotas before calling the provider; use bounded concurrency and short client timeouts. At bursts to 500 RPS, queue long-running work using a durable queue (SQS, RabbitMQ, or Kafka according to delivery needs), return `202` and a job ID, and process with independent workers. This keeps API threads available but changes the API contract and makes completion asynchronous. Retries are bounded and jittered to avoid retry storms. A circuit breaker and explicit degraded response should prevent cascading overload. Use fallbacks only when the alternate model has capacity and suitable quality/cost.

## Migration from one EC2 instance to 10,000 users

1. **Measure and stabilize:** add request IDs, latency/error metrics, DB backups, health checks, timeouts, and a deployable container. Remove in-memory session/rate-limit state.
2. **Externalize state:** move PostgreSQL to a managed service and Redis to managed HA Redis; migrate data with checksums and a tested rollback path. Put secrets in a cloud secret manager and rotate keys.
3. **Introduce the load balancer:** deploy at least two API instances in separate zones, route a small canary percentage, compare error/latency/token-cost dashboards, then progressively shift traffic.
4. **Scale deliberately:** configure autoscaling and connection pooling, provider quotas, per-user usage limits, and circuit breakers. Add a durable worker queue for requests that exceed synchronous latency objectives.
5. **Identity:** move login to OIDC/SSO, validate JWT issuer/audience/JWKS and map IdP groups to application roles.
6. **Recoverability:** exercise database restore, Redis loss, provider outage, zone loss, and rollback before removing the old instance. Keep it as a short-lived fallback only until confidence is established.

Kubernetes and ECS are both reasonable. Kubernetes offers portability and a rich HPA ecosystem but has meaningful operational overhead; ECS is simpler for teams standardized on AWS. The included manifests are illustrative and need ingress, secrets, TLS, resource limits, policies, monitoring, and a managed database/cache before production.

## Failure behavior

| Failure | Behavior |
|---|---|
| Invalid credentials/request | No retry; provider configuration error surfaced as upstream failure |
| LLM timeout | Bounded retries for transient failures; then 504 |
| LLM 429 / selected 5xx | Jittered limited retry; rate-limit or 502 response after exhaustion |
| Redis down | Open mode preserves availability with weakened limit/cache; closed mode returns 503 |
| Database unavailable | Readiness fails; request cannot be durably completed |
| Cache entry stale | TTL limits staleness; disable or add version/context to key where correctness requires |
| Primary LLM unavailable | Call configured real fallback if enabled; otherwise 502/504; never fabricate an answer |

## Security boundaries

Use TLS at the edge, short JWT lifetimes, secret-manager injection, role checks, strong password hashing for local auth, request size limits, strict CORS, and least-privilege DB/Redis identities. Avoid logging tokens and provider payloads. Define retention and deletion for chat content; encrypt backups and restrict metrics endpoints. Production SSO should replace local password login.
