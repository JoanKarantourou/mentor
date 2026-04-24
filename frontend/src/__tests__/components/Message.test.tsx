import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Message } from "@/components/chat/Message";
import type { LocalMessage } from "@/lib/api/types";

// react-markdown needs some mocking in jsdom
vi.mock("highlight.js/styles/github-dark.css", () => ({}));

function makeMsg(overrides: Partial<LocalMessage> = {}): LocalMessage {
  return {
    localId: "local-1",
    role: "assistant",
    content: "Hello world",
    isStreaming: false,
    isLowConfidence: false,
    sources: [],
    retrievedChunkIds: [],
    createdAt: new Date().toISOString(),
    ...overrides,
  };
}

describe("Message — user", () => {
  it("renders user message text", () => {
    const msg = makeMsg({ role: "user", content: "My question" });
    render(
      <Message
        message={msg}
        isLatest={false}
        isStreaming={false}
        onRegenerate={vi.fn()}
      />
    );
    expect(screen.getByText("My question")).toBeInTheDocument();
  });
});

describe("Message — assistant", () => {
  it("renders markdown content", () => {
    const msg = makeMsg({ content: "**Bold** and _italic_" });
    render(
      <Message
        message={msg}
        isLatest={true}
        isStreaming={false}
        onRegenerate={vi.fn()}
      />
    );
    expect(screen.getByText(/Bold/)).toBeInTheDocument();
  });

  it("shows streaming indicator when streaming and content is empty", () => {
    const msg = makeMsg({ isStreaming: true, content: "" });
    const { container } = render(
      <Message
        message={msg}
        isLatest={true}
        isStreaming={true}
        onRegenerate={vi.fn()}
      />
    );
    // Three animated dots
    const dots = container.querySelectorAll("span.rounded-full");
    expect(dots.length).toBeGreaterThanOrEqual(3);
  });

  it("renders low confidence notice when flagged", () => {
    const msg = makeMsg({ isLowConfidence: true });
    render(
      <Message
        message={msg}
        isLatest={false}
        isStreaming={false}
        onRegenerate={vi.fn()}
      />
    );
    expect(screen.getByText(/low confidence/i)).toBeInTheDocument();
  });

  it("does not show low confidence notice when not flagged", () => {
    const msg = makeMsg({ isLowConfidence: false });
    render(
      <Message
        message={msg}
        isLatest={false}
        isStreaming={false}
        onRegenerate={vi.fn()}
      />
    );
    expect(screen.queryByText(/low confidence/i)).toBeNull();
  });
});
