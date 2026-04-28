import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MemorySuggestionBanner } from "@/components/chat/MemorySuggestionBanner";
import type { MemorySuggestion } from "@/lib/api/types";

const suggestion: MemorySuggestion = {
  should_suggest: true,
  reason: "long_conversation",
  preview_count: 5,
};

describe("MemorySuggestionBanner", () => {
  it("renders with preview count", () => {
    render(
      <MemorySuggestionBanner
        suggestion={suggestion}
        conversationId="conv-1"
        onDismiss={() => {}}
        onPreview={() => {}}
      />
    );
    expect(screen.getByText(/~5 key facts/i)).toBeDefined();
  });

  it("calls onPreview when Preview is clicked", () => {
    const onPreview = vi.fn();
    render(
      <MemorySuggestionBanner
        suggestion={suggestion}
        conversationId="conv-1"
        onDismiss={() => {}}
        onPreview={onPreview}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /preview/i }));
    expect(onPreview).toHaveBeenCalledOnce();
  });

  it("calls onDismiss when Not now is clicked", () => {
    const onDismiss = vi.fn();
    render(
      <MemorySuggestionBanner
        suggestion={suggestion}
        conversationId="conv-1"
        onDismiss={onDismiss}
        onPreview={() => {}}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /not now/i }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("calls onDismiss when X button is clicked", () => {
    const onDismiss = vi.fn();
    render(
      <MemorySuggestionBanner
        suggestion={suggestion}
        conversationId="conv-1"
        onDismiss={onDismiss}
        onPreview={() => {}}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
