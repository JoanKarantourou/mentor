# Architectural Decision Log

---

## ADR-001: PostgreSQL as the system of record

**Date:** 2023-06-10  
**Status:** Accepted

### Context

We needed a primary database for tenant configuration, the event audit log, and delivery tracking. Options considered: PostgreSQL, MySQL, DynamoDB, MongoDB.

### Decision

PostgreSQL 14.

### Rationale

The event audit log has a fixed, well-understood schema. Partitioning by `created_at` gives us manageable table sizes without the operational complexity of a distributed database. We already had PostgreSQL expertise on the team. The relational model is a better fit than document storage for the delivery-attempt tracking queries, which involve joins across tenants, events, and endpoints.

DynamoDB was rejected because the query patterns for the admin UI and analytics require ad-hoc filtering across multiple attributes. DynamoDB's query model would have forced us into over-complicated index designs or full-table scans.

### Consequences

- Monthly partitioning + S3 archival required to keep the events table manageable at scale.
- Connection pooling (PgBouncer) required at high concurrency — direct per-request connections exhaust PostgreSQL's limit quickly.
- Write throughput is bounded by a single primary. At current scale this is not a concern; revisit if ingestion exceeds 5,000 events/second sustained.

---

## ADR-002: Redis Streams for the event queue

**Date:** 2023-06-15  
**Status:** Accepted

### Context

Events need to be buffered between ingestion and processing to decouple the two and absorb traffic spikes. Options: Redis Streams, RabbitMQ, Apache Kafka, Amazon SQS.

### Decision

Redis Streams.

### Rationale

We were already using Redis for auth caching and deduplication, so adding Streams kept the infrastructure surface small. Streams provide consumer groups (the key feature we needed for competing consumers), acknowledgement semantics, and persistence.

Kafka was the runner-up. It handles higher throughput and offers better durability guarantees, but the operational overhead (Zookeeper/KRaft, broker management, partition rebalancing) is disproportionate for our current scale. We expect to revisit this if we exceed 1M events/minute.

RabbitMQ was rejected because it lacks the log-like semantics of Streams, making replay more difficult.

SQS was rejected because it introduces a cloud provider dependency we wanted to avoid for portability.

### Consequences

- Redis persistence must be configured (`appendonly yes`, `appendfsync everysec`) to avoid event loss on restart.
- Stream length management required: we trim streams to 1M entries with `XTRIM MAXLEN ~1000000` on each `XADD` to prevent unbounded growth.
- Consumer group state lives in Redis. If Redis is wiped, workers lose their position and must reprocess from the audit log.

---

## ADR-003: Celery for background workers

**Date:** 2023-07-01  
**Status:** Accepted

### Context

The worker pool needed a task execution framework. Options: Celery, Dramatiq, SAQ, custom Redis Stream consumer.

### Decision

Celery with Redis as the broker.

### Rationale

The team had existing Celery experience and it has the most mature ecosystem for Python (monitoring with Flower, retries, rate limiting, task routing). The Redis broker integration worked well with our existing Redis Streams setup, though Celery uses a separate Redis keyspace from our Streams.

Dramatiq was considered as a simpler alternative but lacks the retry and monitoring tooling we needed.

A custom Redis Stream consumer was prototyped but the maintenance burden of reimplementing consumer groups, visibility timeout, and dead-letter handling was not worth it given the available frameworks.

### Consequences

- Celery workers are separate processes from the API. Separate Docker image (`platform-worker`), separate scaling configuration.
- Task routing is configured to send high-priority tenants to a dedicated queue (`priority` queue, separate worker pool).
- Celery's `CELERY_TASK_ALWAYS_EAGER` is used in tests to run tasks synchronously — tests do not require a running broker.

---

## ADR-004: No GraphQL, REST only

**Date:** 2023-07-20  
**Status:** Accepted

### Context

The frontend team asked about using GraphQL for the admin UI data fetching. We evaluated adding a GraphQL layer alongside the REST API.

### Decision

REST only, no GraphQL.

### Rationale

The API surface for producers is small and fixed — it does not benefit from GraphQL's flexible query model. The admin UI has a handful of well-defined queries; building a GraphQL schema and resolvers would add complexity without clear benefit.

More importantly, our external developers (producers and consumers integrating the event API) are best served by a conventional REST interface. GraphQL adds a learning curve and tooling requirement for a relatively simple integration.

### Consequences

- Frontend uses REST endpoints with SWR for data fetching. Query flexibility is limited to the endpoints we define.
- If the admin UI query patterns become complex, revisit. Adding GraphQL later is feasible without changing the REST API.
