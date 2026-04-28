import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MessageSources } from "@/components/chat/MessageSources";
import type { SourceChunk, WebSource } from "@/lib/api/types";

vi.mock("highlight.js/styles/github-dark.css", () => ({}));

function makeChunk(overrides: Partial<SourceChunk> = {}): SourceChunk {
  return {
    chunk_id: "chunk-1",
    document_id: "doc-1",
    filename: "test.md",
    text_preview: "Some chunk text",
    score: 0.85,
    ...overrides,
  };
}

function makeWebSource(overrides: Partial<WebSource> = {}): WebSource {
  return {
    rank: 0,
    title: "Web Article",
    url: "https://example.com/article",
    snippet: "Some web snippet",
    published_date: "2026-01-15",
    source_domain: "example.com",
    ...overrides,
  };
}

describe("MessageSources", () => {
  it("renders nothing when no sources", () => {
    const { container } = render(<MessageSources sources={[]} webSources={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing with empty arrays", () => {
    const { container } = render(<MessageSources sources={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows source count for corpus-only", () => {
    const sources = [makeChunk(), makeChunk({ chunk_id: "chunk-2" })];
    render(<MessageSources sources={sources} />);
    expect(screen.getByText(/2 sources/)).toBeInTheDocument();
  });

  it("shows source count for web-only", () => {
    render(<MessageSources sources={[]} webSources={[makeWebSource()]} />);
    expect(screen.getByText(/1 source/)).toBeInTheDocument();
  });

  it("shows combined count for mixed sources", () => {
    render(
      <MessageSources
        sources={[makeChunk()]}
        webSources={[makeWebSource(), makeWebSource({ rank: 1 })]}
      />
    );
    expect(screen.getByText(/3 sources/)).toBeInTheDocument();
  });

  it("expands to show section headers when opened", () => {
    render(
      <MessageSources
        sources={[makeChunk()]}
        webSources={[makeWebSource()]}
        defaultOpen
      />
    );
    expect(screen.getByText(/From your documents/)).toBeInTheDocument();
    expect(screen.getByText(/From the web/)).toBeInTheDocument();
  });

  it("shows only corpus section when no web sources", () => {
    render(<MessageSources sources={[makeChunk()]} defaultOpen />);
    expect(screen.getByText(/From your documents/)).toBeInTheDocument();
    expect(screen.queryByText(/From the web/)).toBeNull();
  });

  it("shows only web section when no corpus sources", () => {
    render(<MessageSources sources={[]} webSources={[makeWebSource()]} defaultOpen />);
    expect(screen.queryByText(/From your documents/)).toBeNull();
    expect(screen.getByText(/From the web/)).toBeInTheDocument();
  });

  it("toggles open/closed on button click", () => {
    render(<MessageSources sources={[makeChunk()]} defaultOpen={false} />);
    expect(screen.queryByText(/From your documents/)).toBeNull();

    const toggle = screen.getByRole("button");
    fireEvent.click(toggle);
    expect(screen.getByText(/From your documents/)).toBeInTheDocument();
  });
});
