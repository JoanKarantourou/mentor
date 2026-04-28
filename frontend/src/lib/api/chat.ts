import { BACKEND_URL, apiFetch } from "./client";
import type {
  ChatEvent,
  ChatRequest,
  Conversation,
  ConversationDetail,
} from "./types";

// ---------------------------------------------------------------------------
// SSE parser
// ---------------------------------------------------------------------------

interface RawSseEvent {
  eventType: string;
  data: string;
}

export async function* parseSseStream(
  body: ReadableStream<Uint8Array>
): AsyncGenerator<RawSseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      if (!part.trim()) continue;

      let eventType = "message";
      let data = "";

      for (const line of part.split("\n")) {
        if (line.startsWith("event:")) {
          eventType = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          data = line.slice(5).trim();
        }
      }

      yield { eventType, data };
    }
  }
}

// ---------------------------------------------------------------------------
// sendMessage — async generator of typed ChatEvents
// ---------------------------------------------------------------------------

export async function* sendMessage(
  request: ChatRequest
): AsyncGenerator<ChatEvent> {
  const response = await fetch(`${BACKEND_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  if (!response.body) throw new Error("No response body");

  for await (const { eventType, data } of parseSseStream(response.body)) {
    switch (eventType) {
      case "retrieval": {
        const parsed = JSON.parse(data);
        yield { type: "retrieval", ...parsed };
        break;
      }
      case "confidence": {
        const parsed = JSON.parse(data);
        yield { type: "confidence", ...parsed };
        break;
      }
      case "web_search_started": {
        yield { type: "web_search_started" };
        break;
      }
      case "web_search_results": {
        const results = JSON.parse(data);
        yield { type: "web_search_results", results };
        break;
      }
      case "token": {
        const text = JSON.parse(data) as string;
        yield { type: "token", text };
        break;
      }
      case "sources": {
        const parsed = JSON.parse(data);
        yield {
          type: "sources",
          sources: parsed.sources ?? parsed,
          web_sources: parsed.web_sources ?? [],
        };
        break;
      }
      case "message_persisted": {
        const parsed = JSON.parse(data);
        yield { type: "message_persisted", ...parsed };
        break;
      }
      case "gap_analysis": {
        const parsed = JSON.parse(data);
        yield { type: "gap_analysis", ...parsed };
        break;
      }
      case "memory_suggestion": {
        const parsed = JSON.parse(data);
        yield { type: "memory_suggestion", ...parsed };
        break;
      }
      case "error": {
        const parsed = JSON.parse(data);
        yield { type: "error", message: parsed.message };
        break;
      }
      case "done": {
        yield { type: "done" };
        break;
      }
    }
  }
}

// ---------------------------------------------------------------------------
// regenerate — SSE stream from POST /chat/{id}/regenerate
// ---------------------------------------------------------------------------

export async function* regenerateMessage(
  messageId: string
): AsyncGenerator<ChatEvent> {
  const response = await fetch(
    `${BACKEND_URL}/chat/${messageId}/regenerate`,
    { method: "POST" }
  );

  if (!response.ok) {
    throw new Error(`Regenerate request failed: ${response.status}`);
  }

  if (!response.body) throw new Error("No response body");

  for await (const { eventType, data } of parseSseStream(response.body)) {
    switch (eventType) {
      case "retrieval": {
        const parsed = JSON.parse(data);
        yield { type: "retrieval", ...parsed };
        break;
      }
      case "confidence": {
        const parsed = JSON.parse(data);
        yield { type: "confidence", ...parsed };
        break;
      }
      case "web_search_started": {
        yield { type: "web_search_started" };
        break;
      }
      case "web_search_results": {
        const results = JSON.parse(data);
        yield { type: "web_search_results", results };
        break;
      }
      case "token": {
        const text = JSON.parse(data) as string;
        yield { type: "token", text };
        break;
      }
      case "sources": {
        const parsed = JSON.parse(data);
        yield {
          type: "sources",
          sources: parsed.sources ?? parsed,
          web_sources: parsed.web_sources ?? [],
        };
        break;
      }
      case "message_persisted": {
        const parsed = JSON.parse(data);
        yield { type: "message_persisted", ...parsed };
        break;
      }
      case "gap_analysis": {
        const parsed = JSON.parse(data);
        yield { type: "gap_analysis", ...parsed };
        break;
      }
      case "memory_suggestion": {
        const parsed = JSON.parse(data);
        yield { type: "memory_suggestion", ...parsed };
        break;
      }
      case "error": {
        const parsed = JSON.parse(data);
        yield { type: "error", message: parsed.message };
        break;
      }
      case "done": {
        yield { type: "done" };
        break;
      }
    }
  }
}

// ---------------------------------------------------------------------------
// REST endpoints
// ---------------------------------------------------------------------------

export function listConversations(): Promise<Conversation[]> {
  return apiFetch<Conversation[]>("/conversations");
}

export function getConversation(id: string): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/conversations/${id}`);
}

export function deleteConversation(id: string): Promise<void> {
  return apiFetch<void>(`/conversations/${id}`, { method: "DELETE" });
}
