import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SourceCard, WebSourceCard } from "@/components/chat/SourceCard";
import type { SourceChunk, WebSource } from "@/lib/api/types";

function makeChunk(): SourceChunk {
  return {
    chunk_id: "chunk-1",
    document_id: "doc-1",
    filename: "ingestion.py",
    text_preview: "class IngestionPipeline: ...",
    score: 0.82,
  };
}

function makeWebSource(): WebSource {
  return {
    rank: 0,
    title: "RAG Architecture Guide",
    url: "https://docs.example.com/rag",
    snippet: "RAG combines retrieval with generation for accurate answers.",
    published_date: "2026-02-10",
    source_domain: "docs.example.com",
  };
}

describe("SourceCard (corpus)", () => {
  it("renders filename", () => {
    render(<SourceCard source={makeChunk()} onClick={vi.fn()} />);
    expect(screen.getByText("ingestion.py")).toBeInTheDocument();
  });

  it("renders score as percentage", () => {
    render(<SourceCard source={makeChunk()} onClick={vi.fn()} />);
    expect(screen.getByText("82%")).toBeInTheDocument();
  });

  it("renders text preview", () => {
    render(<SourceCard source={makeChunk()} onClick={vi.fn()} />);
    expect(screen.getByText(/IngestionPipeline/)).toBeInTheDocument();
  });

  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<SourceCard source={makeChunk()} onClick={onClick} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledWith(makeChunk());
  });

  it("truncates long previews", () => {
    const source = makeChunk();
    source.text_preview = "x".repeat(300);
    render(<SourceCard source={source} onClick={vi.fn()} />);
    expect(screen.getByText(/…/)).toBeInTheDocument();
  });
});

describe("WebSourceCard", () => {
  it("renders title", () => {
    render(<WebSourceCard source={makeWebSource()} />);
    expect(screen.getByText("RAG Architecture Guide")).toBeInTheDocument();
  });

  it("renders source domain", () => {
    render(<WebSourceCard source={makeWebSource()} />);
    expect(screen.getByText("docs.example.com")).toBeInTheDocument();
  });

  it("renders snippet", () => {
    render(<WebSourceCard source={makeWebSource()} />);
    expect(screen.getByText(/RAG combines/)).toBeInTheDocument();
  });

  it("renders published date", () => {
    render(<WebSourceCard source={makeWebSource()} />);
    expect(screen.getByText("2026-02-10")).toBeInTheDocument();
  });

  it("is a link to the URL", () => {
    render(<WebSourceCard source={makeWebSource()} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "https://docs.example.com/rag");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("shows no date when null", () => {
    const source = { ...makeWebSource(), published_date: null };
    const { container } = render(<WebSourceCard source={source} />);
    expect(container.textContent).not.toMatch(/2026/);
  });
});
