# Engineering trade-offs

| Decision | Current choice | When an alternative fits |
|---|---|---|
| PostgreSQL vs NoSQL | PostgreSQL for identities, ownership, and queryable request metadata | NoSQL may fit highly variable documents or extreme key/value access patterns; it adds consistency/query trade-offs for relational data. |
| Redis cache vs database cache | Redis for low-latency TTL cache and shared counters | A DB cache is simpler at low volume but competes with durable writes and is less suitable for high-rate counters. |
| Synchronous API vs queue | Synchronous answer for the simple interactive contract | Queue workers fit long jobs, burst absorption, retries across process restarts, and client polling/webhooks; they add eventual consistency and API complexity. |
| Kubernetes vs ECS | Kubernetes manifests illustrate HPA and portable orchestration | ECS is often lower operational burden for AWS-only teams; Kubernetes fits teams needing its ecosystem and control. |
| One LLM provider vs multi-provider | Provider protocol, primary Groq free tier, optional configured fallback | A single provider reduces operational and evaluation burden. Multi-provider increases resilience but needs quality, privacy, cost, and quota routing policy. Free-tier capacity suits demos, not a production quota commitment. |
| Retry vs timeout | Retry only transient failures with bounded attempts and jitter | Retries help brief network/provider faults but multiply latency/load during outages; aggressive deadlines may be better for interactive UX. |
| Cache consistency | Short TTL, normalized question key for public context-free answers | User context, changing knowledge, or personalized prompts need identity/version in the key or no cache. |
| Redis fail-open vs fail-closed | Configurable; local default open | Open preserves availability but temporarily removes enforcement; closed protects spend/abuse but makes Redis outage an application outage. |
| CPU HPA vs app metrics | CPU plus concurrency/latency recommended | CPU alone is simple but misses blocked I/O. Custom metrics improve scaling but need trustworthy telemetry and careful stabilization. |
| Managed vs self-hosted | Managed PostgreSQL/Redis recommended for production | Self-hosting gives control and can reduce cost at scale, but transfers patching, failover, backup, and on-call burden to the team. |

These choices depend on provider quotas, privacy classification, latency objectives, team skills, and budget. The deployment should be validated with realistic load and failure tests before setting replica or pool counts.
