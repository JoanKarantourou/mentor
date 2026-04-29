/**
 * Platform API client.
 *
 * Handles authentication, retries on transient errors, and typed responses.
 * Designed for use in Node.js services. Not intended for browser use (API keys
 * must not be exposed client-side).
 */

export interface PlatformEvent {
  eventId: string;
  eventType: string;
  payload: Record<string, unknown>;
  timestamp?: string;
}

export interface IngestResult {
  eventId: string;
  status: "queued" | "duplicate";
}

export interface BatchIngestResult {
  accepted: number;
  rejected: number;
  results: IngestResult[];
}

export interface Delivery {
  deliveryId: string;
  endpointUrl: string;
  status: "pending" | "delivered" | "failed" | "dead";
  attempt: number;
  lastError?: string;
  nextRetryAt?: string;
}

export class PlatformApiError extends Error {
  constructor(
    public readonly statusCode: number,
    public readonly errorCode: string,
    message: string
  ) {
    super(message);
    this.name = "PlatformApiError";
  }
}

export class PlatformClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly maxRetries: number;

  constructor(options: {
    baseUrl?: string;
    apiKey: string;
    maxRetries?: number;
  }) {
    this.baseUrl = options.baseUrl ?? "https://api.platform.example.com/v1";
    this.apiKey = options.apiKey;
    this.maxRetries = options.maxRetries ?? 3;
  }

  /** Ingest a single event. Returns the event ID and queue status. */
  async ingest(event: PlatformEvent): Promise<IngestResult> {
    return this.request<IngestResult>("POST", "/events", event);
  }

  /** Ingest up to 100 events in a single request. */
  async ingestBatch(events: PlatformEvent[]): Promise<BatchIngestResult> {
    if (events.length === 0) {
      return { accepted: 0, rejected: 0, results: [] };
    }
    if (events.length > 100) {
      throw new Error("Batch size cannot exceed 100 events");
    }
    return this.request<BatchIngestResult>("POST", "/events/batch", { events });
  }

  /** Retrieve delivery attempts for a specific event. */
  async getDeliveries(eventId: string): Promise<Delivery[]> {
    const response = await this.request<{ deliveries: Delivery[] }>(
      "GET",
      `/events/${encodeURIComponent(eventId)}/deliveries`
    );
    return response.deliveries;
  }

  /** Re-enqueue a dead delivery for replay. */
  async replayDelivery(deliveryId: string): Promise<void> {
    await this.request("POST", `/deliveries/${encodeURIComponent(deliveryId)}/replay`);
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown
  ): Promise<T> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      if (attempt > 0) {
        // Exponential backoff: 500ms, 1s, 2s
        const delayMs = Math.min(500 * 2 ** (attempt - 1), 10_000);
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }

      try {
        const response = await fetch(`${this.baseUrl}${path}`, {
          method,
          headers: {
            "Authorization": `Bearer ${this.apiKey}`,
            "Content-Type": "application/json",
          },
          body: body !== undefined ? JSON.stringify(body) : undefined,
        });

        if (response.ok) {
          if (response.status === 204) return undefined as T;
          return response.json() as Promise<T>;
        }

        // 429 and 5xx are retryable; 4xx (except 429) are not
        const errorBody = await response.json().catch(() => ({}));
        const error = new PlatformApiError(
          response.status,
          errorBody?.error?.code ?? "unknown_error",
          errorBody?.error?.message ?? `HTTP ${response.status}`
        );

        if (response.status === 429 || response.status >= 500) {
          lastError = error;
          continue; // retry
        }

        throw error;
      } catch (err) {
        if (err instanceof PlatformApiError) throw err;
        // Network error — retryable
        lastError = err instanceof Error ? err : new Error(String(err));
      }
    }

    throw lastError ?? new Error("Request failed after retries");
  }
}
