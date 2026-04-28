import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { LowConfidenceNotice } from "@/components/chat/LowConfidenceNotice";
import type { GapAnalysis } from "@/lib/api/types";

const gapAnalysis: GapAnalysis = {
  missing_topic: "payment processing logic",
  related_topics_present: ["authentication", "user accounts"],
  suggested_document_types: ["API reference", "code module documentation"],
  related_document_ids: ["doc-1"],
};

describe("LowConfidenceNotice — gap analysis variant", () => {
  it("renders gap analysis fields when provided", () => {
    render(
      <LowConfidenceNotice
        gapAnalysis={gapAnalysis}
        onTryWithWebSearch={() => {}}
        onUploadDocument={() => {}}
      />
    );
    expect(screen.getByText(/payment processing logic/i)).toBeDefined();
    expect(screen.getByText(/authentication/i)).toBeDefined();
    expect(screen.getByText(/api reference/i)).toBeDefined();
  });

  it("shows web search and upload buttons", () => {
    render(
      <LowConfidenceNotice
        gapAnalysis={gapAnalysis}
        onTryWithWebSearch={() => {}}
        onUploadDocument={() => {}}
      />
    );
    expect(screen.getByRole("button", { name: /try with web search/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /upload a document/i })).toBeDefined();
  });

  it("calls onUploadDocument when button clicked", () => {
    const onUpload = vi.fn();
    render(
      <LowConfidenceNotice
        gapAnalysis={gapAnalysis}
        onUploadDocument={onUpload}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /upload a document/i }));
    expect(onUpload).toHaveBeenCalledOnce();
  });

  it("renders plain fallback when no gap analysis provided", () => {
    render(<LowConfidenceNotice onTryWithWebSearch={() => {}} />);
    expect(screen.getByText(/low confidence/i)).toBeDefined();
    expect(screen.queryByText(/payment processing/i)).toBeNull();
  });
});
