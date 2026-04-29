# API Reference

Base URL: `https://api.platform.example.com/v1`

All requests must include an `Authorization: Bearer {api_key}` header. API keys are issued per tenant and scoped to specific event types.

Rate limits are applied per API key. The default limit is 1000 requests per minute. The response includes `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers.

---

## Events

### Ingest an event

```
POST /events
```

Validates and enqueues a single event. Returns immediately — delivery is asynchronous.

**Request body:**

```json
{
  "event_id": "string (required, unique per producer per 24 hours)",
  "event_type": "string (required, must match a registered schema)",
  "payload": "object (required, validated against schema)",
  "timestamp": "ISO 8601 string (optional, defaults to server receive time)"
}
```

**Response `202 Accepted`:**

```json
{
  "event_id": "evt_01HX...",
  "status": "queued"
}
```

**Error responses:**

| Status | Meaning |
|--------|---------|
| 400 | Malformed request body |
| 401 | Missing or invalid API key |
| 409 | Duplicate `event_id` (event acknowledged but not re-queued) |
| 422 | Payload failed schema validation |
| 429 | Rate limit exceeded |

### Ingest a batch

```
POST /events/batch
```

Ingest up to 100 events in a single request. Validation and deduplication apply per event. Returns a summary with per-event status.

**Request body:**

```json
{
  "events": [/* array of event objects, same schema as POST /events */]
}
```

**Response `207 Multi-Status`:**

```json
{
  "accepted": 98,
  "rejected": 2,
  "results": [
    {"event_id": "evt_01HX...", "status": "queued"},
    {"event_id": "evt_02HY...", "status": "duplicate"}
  ]
}
```

### Retrieve an event

```
GET /events/{event_id}
```

Retrieve an event from the audit log.

**Response `200 OK`:**

```json
{
  "event_id": "evt_01HX...",
  "event_type": "order.created",
  "payload": { "...": "..." },
  "timestamp": "2024-03-15T10:23:45Z",
  "received_at": "2024-03-15T10:23:45.123Z",
  "status": "delivered"
}
```

---

## Deliveries

### List deliveries for an event

```
GET /events/{event_id}/deliveries
```

Returns the delivery attempt history for an event. Useful for debugging failed deliveries.

**Response `200 OK`:**

```json
{
  "deliveries": [
    {
      "delivery_id": "del_01HX...",
      "endpoint_url": "https://your-app.example.com/webhook",
      "status": "failed",
      "attempt": 3,
      "last_error": "Connection refused",
      "next_retry_at": "2024-03-15T11:30:00Z"
    }
  ]
}
```

### Replay a dead delivery

```
POST /deliveries/{delivery_id}/replay
```

Re-enqueues a delivery that has exhausted all retries. The event is re-delivered from the audit log.

---

## Webhook endpoints

### Register a webhook endpoint

```
POST /webhooks
```

**Request body:**

```json
{
  "url": "https://your-app.example.com/webhook",
  "event_types": ["order.created", "order.updated"],
  "secret": "string (optional, used to sign payloads)"
}
```

Webhook payloads are signed with HMAC-SHA256 if a secret is provided. The signature is in the `X-Platform-Signature` header.

Verify in Python:

```python
import hmac, hashlib

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

### List webhook endpoints

```
GET /webhooks
```

### Delete a webhook endpoint

```
DELETE /webhooks/{webhook_id}
```

---

## Pagination

List endpoints return paginated results using cursor-based pagination:

```
GET /events?limit=50&cursor=<cursor_from_previous_response>
```

Response includes `next_cursor` (null when no more results).

---

## Errors

All errors return JSON with a consistent shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "payload.amount must be a positive number",
    "details": { "field": "payload.amount", "constraint": "minimum: 0" }
  }
}
```

Common error codes: `authentication_failed`, `rate_limit_exceeded`, `validation_error`, `duplicate_event`, `not_found`, `internal_error`.
