import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { DuplicateResolutionModal } from "@/components/documents/DuplicateResolutionModal";

vi.mock("@/lib/api/curation", () => ({
  getDuplicates: vi.fn(),
  resolveDuplicate: vi.fn(),
}));

import { getDuplicates, resolveDuplicate } from "@/lib/api/curation";

const mockGet = getDuplicates as ReturnType<typeof vi.fn>;
const mockResolve = resolveDuplicate as ReturnType<typeof vi.fn>;

const MATCH = {
  existing_document_id: "doc-old-1",
  existing_filename: "old-doc.md",
  similarity: 0.93,
  match_type: "near_duplicate" as const,
  matching_chunks: 4,
};

describe("DuplicateResolutionModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue([MATCH]);
    mockResolve.mockResolvedValue(undefined);
  });

  it("renders match list with similarity percentage", async () => {
    render(
      <DuplicateResolutionModal
        documentId="doc-new"
        filename="new-doc.md"
        open={true}
        onClose={() => {}}
        onResolved={() => {}}
      />
    );
    await waitFor(() => expect(screen.getByText("old-doc.md")).toBeDefined());
    expect(screen.getByText("93% similar")).toBeDefined();
  });

  it("calls resolveDuplicate with keep_both action", async () => {
    const onResolved = vi.fn();
    render(
      <DuplicateResolutionModal
        documentId="doc-new"
        filename="new-doc.md"
        open={true}
        onClose={() => {}}
        onResolved={onResolved}
      />
    );
    await waitFor(() => screen.getByRole("button", { name: /keep both/i }));
    fireEvent.click(screen.getByRole("button", { name: /keep both/i }));
    await waitFor(() => expect(mockResolve).toHaveBeenCalledWith("doc-new", "keep_both", undefined));
    expect(onResolved).toHaveBeenCalledWith("keep_both");
  });

  it("calls resolveDuplicate with skip action", async () => {
    const onResolved = vi.fn();
    render(
      <DuplicateResolutionModal
        documentId="doc-new"
        filename="new-doc.md"
        open={true}
        onClose={() => {}}
        onResolved={onResolved}
      />
    );
    await waitFor(() => screen.getByRole("button", { name: /skip this upload/i }));
    fireEvent.click(screen.getByRole("button", { name: /skip this upload/i }));
    await waitFor(() => expect(mockResolve).toHaveBeenCalledWith("doc-new", "skip", undefined));
    expect(onResolved).toHaveBeenCalledWith("skip");
  });

  it("calls resolveDuplicate with replace action and target id", async () => {
    const onResolved = vi.fn();
    render(
      <DuplicateResolutionModal
        documentId="doc-new"
        filename="new-doc.md"
        open={true}
        onClose={() => {}}
        onResolved={onResolved}
      />
    );
    await waitFor(() => screen.getByRole("button", { name: /replace/i }));
    fireEvent.click(screen.getByRole("button", { name: /replace/i }));
    await waitFor(() =>
      expect(mockResolve).toHaveBeenCalledWith("doc-new", "replace", "doc-old-1")
    );
    expect(onResolved).toHaveBeenCalledWith("replace");
  });

  it("shows error message on API failure", async () => {
    mockGet.mockRejectedValue(new Error("Server error"));
    render(
      <DuplicateResolutionModal
        documentId="doc-new"
        filename="new-doc.md"
        open={true}
        onClose={() => {}}
        onResolved={() => {}}
      />
    );
    await waitFor(() => expect(screen.getByText("Server error")).toBeDefined());
  });
});
