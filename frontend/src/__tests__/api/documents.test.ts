import { describe, it, expect, vi, beforeEach } from "vitest";

const BACKEND_URL = "http://localhost:8000";

// ---------------------------------------------------------------------------
// uploadDocument — mocked fetch
// ---------------------------------------------------------------------------

async function uploadDocument(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${BACKEND_URL}/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(`Upload failed (${res.status})`);
  }

  return res.json();
}

describe("uploadDocument", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("sends a POST with FormData and returns parsed JSON", async () => {
    const mockResponse = { document_id: "abc-123", status: "pending" };
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(mockResponse), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      })
    );

    const file = new File(["hello"], "test.md", { type: "text/markdown" });
    const result = await uploadDocument(file);

    expect(fetchSpy).toHaveBeenCalledOnce();
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe(`${BACKEND_URL}/documents/upload`);
    expect((init as RequestInit).method).toBe("POST");
    expect((init as RequestInit).body).toBeInstanceOf(FormData);
    expect(result).toEqual(mockResponse);
  });

  it("throws when the server returns an error status", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("Too Large", { status: 413 })
    );

    const file = new File(["x"], "big.pdf", { type: "application/pdf" });
    await expect(uploadDocument(file)).rejects.toThrow("Upload failed (413)");
  });
});
