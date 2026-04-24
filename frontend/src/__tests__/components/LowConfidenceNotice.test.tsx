import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LowConfidenceNotice } from "@/components/chat/LowConfidenceNotice";

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
});
