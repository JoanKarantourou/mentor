# System Architecture

## Overview

The platform is a multi-tenant API service for processing and delivering data events. It handles ingestion from external producers, transforms and routes events through a configurable pipeline, and delivers them to consumer endpoints via webhook or polling.

At steady state it processes roughly 50,000 events per minute across all tenants with a median end-to-end latency of 120ms.

## Core components

```
Producers
    │
    ▼
┌─────────────────────┐
│  Ingestion API      │  FastAPI — validates, deduplicates, enqueues
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Event queue        │  Redis Streams — durable, per-tenant streams
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Worker pool        │  Celery workers — transform, route, deliver
└────────┬────────────┘
         │
    ┌────┴─────┐
    ▼          ▼
Webhook    Polling API
delivery   (consumers pull)
```

## Ingestion API

The ingestion API is the entry point for all events. Key responsibilities:

- **Authentication.** API key validated on every request via a Redis cache of hashed keys (5-minute TTL). Full database lookup on cache miss.
- **Validation.** Schema validation against the tenant's registered event schema. Invalid events are rejected with 422 before queuing.
- **Deduplication.** Events carry a producer-supplied `event_id`. The API checks a Redis set keyed by `{tenant_id}:{event_id}` with a 24-hour TTL. Duplicate events are acknowledged but not re-queued.
- **Enqueuing.** Accepted events are written to the tenant's Redis Stream (`events:{tenant_id}`) with an `XADD` command.

The API does not write to PostgreSQL on the hot path. Database writes happen in the worker.

## Worker pool

Workers consume from Redis Streams using consumer groups (one group per event type). Each worker:

1. Claims a batch of events (`XREADGROUP`)
2. Applies the tenant's transformation pipeline (field mapping, filtering, enrichment)
3. Attempts delivery (webhook or write to delivery queue)
4. Acknowledges (`XACK`) on success, or re-queues with exponential backoff on failure

Workers are stateless and horizontally scalable. The number of workers per event type is configured in `platform-infra/workers.yaml`.

## Database schema

PostgreSQL 14 is the system of record. Key tables:

- `tenants` — tenant configuration, API keys (hashed), subscription tier
- `event_schemas` — JSON Schema definitions per tenant per event type
- `events` — append-only event log for audit and replay. Partitioned by `created_at` (monthly). Rows older than 90 days are archived to S3.
- `deliveries` — delivery attempt log with status, attempt count, and last error
- `webhook_endpoints` — registered consumer endpoints per tenant

## Caching strategy

Redis is used for three distinct purposes:

| Purpose | Key pattern | TTL |
|---------|-------------|-----|
| API key auth | `auth:{hashed_key}` | 5 min |
| Deduplication | `dedup:{tenant_id}:{event_id}` | 24 h |
| Schema cache | `schema:{tenant_id}:{event_type}` | 30 min |

Schema cache entries are invalidated on tenant schema update.

## Error handling and retries

Failed webhook deliveries are retried with exponential backoff: 30s, 2m, 10m, 1h, 6h, 24h. After 6 failed attempts the delivery is marked `dead` and the tenant is notified by email. Dead deliveries can be replayed via the admin API.

Transient worker errors (Redis unavailable, database timeout) are retried by Celery with the same backoff schedule. The worker's visibility timeout is set to 60 seconds to allow re-claiming of stalled jobs.

## Observability

- **Logs:** structured JSON to stdout, shipped to Datadog. All request logs include `tenant_id`, `event_type`, and `trace_id`.
- **Metrics:** Prometheus metrics scraped by Datadog. Key metrics: `ingestion_events_total`, `delivery_latency_seconds`, `delivery_failure_total`.
- **Traces:** OpenTelemetry auto-instrumentation on the API and workers. Traces visible in Datadog APM.
- **Alerts:** defined in `platform-infra/monitoring/alerts.yaml`. Most critical: `delivery_failure_rate > 5%` for any tenant over 5 minutes.

## Scaling

The ingestion API and workers scale independently:

- API scales horizontally behind an ALB. Target: CPU < 60%. Minimum 2 replicas.
- Workers scale based on Redis Stream lag. If `XLEN events:{tenant_id}` grows beyond 10,000 unprocessed events, an additional worker is spawned. Managed by KEDA in the Kubernetes cluster.

For tenant-level isolation, high-volume tenants can be assigned to dedicated worker groups via the `dedicated_workers` flag on the `tenants` table.
