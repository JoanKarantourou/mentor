import { describe, it, expect, vi } from "vitest";
import { parseSseStream } from "@/lib/api/chat";

// ---------------------------------------------------------------------------
// SSE parser helpers
// ---------------------------------------------------------------------------

interface RawSseEvent {
  eventType: string;
  data: string;
}

function makeStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

async function collect(
  stream: AsyncGenerator<RawSseEvent>
): Promise<RawSseEvent[]> {
  const events: RawSseEvent[] = [];
  for await (const e of stream) {
    events.push(e);
  }
  return events;
}

// ---------------------------------------------------------------------------
// Standard SSE parsing
// ---------------------------------------------------------------------------

describe("SSE parser", () => {
  it("parses a complete multi-event stream", async () => {
    const body = makeStream([
      'event: confidence\ndata: {"sufficient":true}\n\n',
      'event: token\ndata: "hello"\n\n',
      "event: done\ndata:\n\n",
    ]);

    const events = await collect(parseSseStream(body));
    expect(events).toHaveLength(3);
    expect(events[0]).toEqual({ eventType: "confidence", data: '{"sufficient":true}' });
    expect(events[1]).toEqual({ eventType: "token", data: '"hello"' });
    expect(events[2]).toEqual({ eventType: "done", data: "" });
  });

  it("buffers partial events split across chunks", async () => {
    const body = makeStream([
      "event: token\n",
      'data: "world"\n\n',
    ]);

    const events = await collect(parseSseStream(body));
    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ eventType: "token", data: '"world"' });
  });

  it("handles multiple events in a single chunk", async () => {
    const body = makeStream([
      'event: token\ndata: "a"\n\nevent: token\ndata: "b"\n\n',
    ]);

    const events = await collect(parseSseStream(body));
    expect(events).toHaveLength(2);
    expect(events[0].data).toBe('"a"');
    expect(events[1].data).toBe('"b"');
  });

  it("skips blank separator lines", async () => {
    const body = makeStream([
      '\n\nevent: token\ndata: "ok"\n\n',
    ]);

    const events = await collect(parseSseStream(body));
    expect(events).toHaveLength(1);
  });

  it("returns default message type when no event line", async () => {
    const body = makeStream(['data: {"foo":"bar"}\n\n']);

    const events = await collect(parseSseStream(body));
    expect(events[0].eventType).toBe("message");
    expect(events[0].data).toBe('{"foo":"bar"}');
  });

  it("handles event split across many small chunks", async () => {
    const full = 'event: confidence\ndata: {"sufficient":false}\n\n';
    const chunks = full.split("").map((c) => c);
    const body = makeStream(chunks);

    const events = await collect(parseSseStream(body));
    expect(events).toHaveLength(1);
    expect(events[0].eventType).toBe("confidence");
    expect(events[0].data).toBe('{"sufficient":false}');
  });

  // Web search event parsing
  it("parses web_search_started event", async () => {
    const body = makeStream([
      "event: web_search_started\ndata: {}\n\n",
    ]);

    const events = await collect(parseSseStream(body));
    expect(events).toHaveLength(1);
    expect(events[0].eventType).toBe("web_search_started");
  });

  it("parses web_search_results event", async () => {
    const results = JSON.stringify([
      { rank: 0, title: "Test", url: "https://example.com", snippet: "snippet", published_date: null, source_domain: "example.com" },
    ]);
    const body = makeStream([
      `event: web_search_results\ndata: ${results}\n\n`,
    ]);

    const events = await collect(parseSseStream(body));
    expect(events).toHaveLength(1);
    expect(events[0].eventType).toBe("web_search_results");
    const parsed = JSON.parse(events[0].data);
    expect(parsed).toHaveLength(1);
    expect(parsed[0].rank).toBe(0);
  });

  it("handles mixed event types including web search", async () => {
    const body = makeStream([
      'event: retrieval\ndata: {"chunk_ids":[],"top_similarity":0.1,"avg_similarity":0.1}\n\n',
      'event: confidence\ndata: {"sufficient":false,"reason":"low"}\n\n',
      "event: web_search_started\ndata: {}\n\n",
      'event: web_search_results\ndata: []\n\n',
      'event: token\ndata: "answer"\n\n',
      "event: done\ndata:\n\n",
    ]);

    const events = await collect(parseSseStream(body));
    expect(events).toHaveLength(6);
    const types = events.map((e) => e.eventType);
    expect(types).toContain("web_search_started");
    expect(types).toContain("web_search_results");
  });

  it("handles stream ending abruptly mid-event", async () => {
    // Stream ends without the closing \n\n
    const body = makeStream([
      'event: token\ndata: "partial"',
    ]);

    // Should not throw — partial event is buffered and lost, but no crash
    const events = await collect(parseSseStream(body));
    // The partial event isn't emitted (no \n\n terminator)
    expect(events).toHaveLength(0);
  });

  it("handles empty stream", async () => {
    const body = makeStream([]);
    const events = await collect(parseSseStream(body));
    expect(events).toHaveLength(0);
  });
});
