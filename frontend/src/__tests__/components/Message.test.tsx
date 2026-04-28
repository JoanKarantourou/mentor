import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Message } from "@/components/chat/Message";
import type { LocalMessage, ModelTier } from "@/lib/api/types";

vi.mock("highlight.js/styles/github-dark.css", () => ({}));

function makeMsg(overrides: Partial<LocalMessage> = {}): LocalMessage {
  return {
    localId: "local-1",
    role: "assistant",
    content: "Hello world",
    isStreaming: false,
    isLowConfidence: false,
    webSearchUsed: false,
    webSearchPending: false,
    webSearchResultCount: 0,
    sources: [],
    webSources: [],
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

describe("Message — assistant normal", () => {
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

describe("Message — web search states", () => {
  it("shows 'Searching the web...' when web search is pending", () => {
    const msg = makeMsg({ webSearchPending: true, isStreaming: true });
    render(
      <Message
        message={msg}
        isLatest={true}
        isStreaming={true}
        onRegenerate={vi.fn()}
      />
    );
    expect(screen.getByText(/Searching the web/)).toBeInTheDocument();
  });

  it("shows web search badge when web search was used", () => {
    const msg = makeMsg({ webSearchUsed: true, content: "Answer from web", webSearchResultCount: 3 });
    const { container } = render(
      <Message
        message={msg}
        isLatest={true}
        isStreaming={false}
        onRegenerate={vi.fn()}
      />
    );
    // Globe icon should be present in the badge
    const svgs = container.querySelectorAll("svg");
    expect(svgs.length).toBeGreaterThan(0);
  });

  it("does not show low confidence notice when web search was used", () => {
    // When web search bridges the gap, low confidence is false
    const msg = makeMsg({ webSearchUsed: true, isLowConfidence: false });
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

  it("shows 'Try with web search' button on low confidence when callback provided", () => {
    const msg = makeMsg({ isLowConfidence: true, webSearchUsed: false });
    render(
      <Message
        message={msg}
        isLatest={false}
        isStreaming={false}
        onRegenerate={vi.fn()}
        onTryWithWebSearch={vi.fn()}
      />
    );
    expect(screen.getByText(/Try with web search/)).toBeInTheDocument();
  });

  it("shows web search result count in streaming state", () => {
    const msg = makeMsg({
      webSearchUsed: true,
      webSearchResultCount: 4,
      isStreaming: true,
      webSearchPending: false,
    });
    render(
      <Message
        message={msg}
        isLatest={true}
        isStreaming={true}
        onRegenerate={vi.fn()}
      />
    );
    expect(screen.getByText(/Found 4 web results/)).toBeInTheDocument();
  });
});
