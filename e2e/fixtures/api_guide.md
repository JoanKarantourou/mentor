# API Reference Guide

## Endpoints

### POST /chat

Start or continue a chat conversation.

**Request body:**
```json
{
  "message": "string",
  "conversation_id": "uuid | null",
  "model_tier": "default | strong",
  "enable_web_search": false
}
```

**Response:** Server-Sent Events stream with event types:
- `retrieval` — chunk IDs and similarity scores
- `confidence` — whether corpus match was sufficient
- `token` — streaming text tokens
- `sources` — cited chunks (and web sources if search used)
- `message_persisted` — conversation and message IDs
- `done` — stream end signal

### GET /conversations/{id}

Fetch a full conversation with all messages.

**Returns:** conversation detail with messages, metadata, and citation IDs.

### DELETE /conversations/{id}

Delete a conversation and all its messages.

## Authentication

Currently no authentication is required (single-user development mode).
