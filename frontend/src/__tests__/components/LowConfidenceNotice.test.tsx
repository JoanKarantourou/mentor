import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LowConfidenceNotice, WebSearchUsedNotice } from "@/components/chat/LowConfidenceNotice";

describe("LowConfidenceNotice", () => {
  it("renders without crashing", () => {
    render(<LowConfidenceNotice />);
  });

  it("shows a warning about low confidence", () => {
    render(<LowConfidenceNotice />);
    expect(screen.getByText(/low confidence/i)).toBeInTheDocument();
  });

  it("renders an icon (AlertTriangle svg)", () => {
    const { container } = render(<LowConfidenceNotice />);
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("has amber styling", () => {
    const { container } = render(<LowConfidenceNotice />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toMatch(/amber/);
  });

  it("renders 'Try with web search' button when callback provided", () => {
    render(<LowConfidenceNotice onTryWithWebSearch={vi.fn()} />);
    expect(screen.getByText(/Try with web search/)).toBeInTheDocument();
  });

  it("does not render 'Try with web search' when no callback", () => {
    render(<LowConfidenceNotice />);
    expect(screen.queryByText(/Try with web search/)).toBeNull();
  });

  it("calls onTryWithWebSearch when button clicked", () => {
    const callback = vi.fn();
    render(<LowConfidenceNotice onTryWithWebSearch={callback} />);
    fireEvent.click(screen.getByText(/Try with web search/));
    expect(callback).toHaveBeenCalledOnce();
  });
});

describe("WebSearchUsedNotice", () => {
  it("renders without crashing", () => {
    render(<WebSearchUsedNotice resultCount={3} />);
  });

  it("shows web search used text", () => {
    render(<WebSearchUsedNotice resultCount={3} />);
    expect(screen.getByText(/searched the web/i)).toBeInTheDocument();
  });

  it("shows result count", () => {
    render(<WebSearchUsedNotice resultCount={5} />);
    expect(screen.getByText(/5 results/)).toBeInTheDocument();
  });

  it("has emerald styling", () => {
    const { container } = render(<WebSearchUsedNotice resultCount={1} />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toMatch(/emerald/);
  });
});
