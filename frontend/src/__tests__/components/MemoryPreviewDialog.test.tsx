import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryPreviewDialog } from "@/components/chat/MemoryPreviewDialog";

vi.mock("@/lib/api/curation", () => ({
  previewMemoryExtraction: vi.fn(),
  saveMemoryExtraction: vi.fn(),
}));

import { previewMemoryExtraction, saveMemoryExtraction } from "@/lib/api/curation";

const mockPreview = previewMemoryExtraction as ReturnType<typeof vi.fn>;
const mockSave = saveMemoryExtraction as ReturnType<typeof vi.fn>;

describe("MemoryPreviewDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPreview.mockResolvedValue({
      title: "Redis caching decision",
      content: "- We chose Redis for caching.",
      fact_count: 1,
      source_message_count: 2,
    });
    mockSave.mockResolvedValue({ document_id: "doc-123" });
  });

  it("shows loading state then extracted content", async () => {
    render(
      <MemoryPreviewDialog
        open={true}
        conversationId="conv-1"
        onClose={() => {}}
        onSaved={() => {}}
      />
    );
    expect(screen.getByText(/extracting key facts/i)).toBeDefined();
    await waitFor(() => expect(screen.getByDisplayValue("Redis caching decision")).toBeDefined());
    expect(screen.getByDisplayValue("- We chose Redis for caching.")).toBeDefined();
  });

  it("calls onSaved with document id after saving", async () => {
    const onSaved = vi.fn();
    render(
      <MemoryPreviewDialog
        open={true}
        conversationId="conv-1"
        onClose={() => {}}
        onSaved={onSaved}
      />
    );
    await waitFor(() => screen.getByDisplayValue("Redis caching decision"));
    fireEvent.click(screen.getByRole("button", { name: /save to my documents/i }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith("doc-123"));
  });

  it("shows error on failed preview", async () => {
    mockPreview.mockRejectedValue(new Error("Extraction failed"));
    render(
      <MemoryPreviewDialog
        open={true}
        conversationId="conv-1"
        onClose={() => {}}
        onSaved={() => {}}
      />
    );
    await waitFor(() => expect(screen.getByText(/extraction failed/i)).toBeDefined());
  });

  it("regenerate button re-runs extraction", async () => {
    render(
      <MemoryPreviewDialog
        open={true}
        conversationId="conv-1"
        onClose={() => {}}
        onSaved={() => {}}
      />
    );
    await waitFor(() => screen.getByDisplayValue("Redis caching decision"));
    fireEvent.click(screen.getByRole("button", { name: /regenerate/i }));
    await waitFor(() => expect(mockPreview).toHaveBeenCalledTimes(2));
  });

  it("cancel closes the dialog", async () => {
    const onClose = vi.fn();
    render(
      <MemoryPreviewDialog
        open={true}
        conversationId="conv-1"
        onClose={onClose}
        onSaved={() => {}}
      />
    );
    await waitFor(() => screen.getByRole("button", { name: /cancel/i }));
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
