import { describe, it, expect, vi } from "vitest";

// ---------------------------------------------------------------------------
// SSE parser — extracted for testing
// ---------------------------------------------------------------------------

interface RawSseEvent {
  eventType: string;
  data: string;
}

async function* parseSseStream(
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
    const chunks = full.split("").map((c) => c); // one byte per chunk
    const body = makeStream(chunks);

    const events = await collect(parseSseStream(body));
    expect(events).toHaveLength(1);
    expect(events[0].eventType).toBe("confidence");
    expect(events[0].data).toBe('{"sufficient":false}');
  });
});
