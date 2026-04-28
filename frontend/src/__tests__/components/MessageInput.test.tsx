import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MessageInput } from "@/components/chat/MessageInput";

describe("MessageInput", () => {
  it("renders textarea and send button", () => {
    render(<MessageInput onSend={vi.fn()} disabled={false} />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
  });

  it("send button is disabled when textarea is empty", () => {
    render(<MessageInput onSend={vi.fn()} disabled={false} />);
    const btn = screen.getByRole("button", { name: /send/i });
    expect(btn).toBeDisabled();
  });

  it("send button is disabled while streaming", () => {
    render(<MessageInput onSend={vi.fn()} disabled={true} />);
    const btn = screen.getByRole("button", { name: /send/i });
    expect(btn).toBeDisabled();
  });

  it("enables send button when text is entered", () => {
    render(<MessageInput onSend={vi.fn()} disabled={false} />);
    const ta = screen.getByRole("textbox");
    fireEvent.change(ta, { target: { value: "hello" } });
    const btn = screen.getByRole("button", { name: /send/i });
    expect(btn).not.toBeDisabled();
  });

  it("calls onSend with message, tier, and web search flag on click", () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} disabled={false} />);
    const ta = screen.getByRole("textbox");
    fireEvent.change(ta, { target: { value: "my question" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    expect(onSend).toHaveBeenCalledWith("my question", "default", false);
  });

  it("resets web search toggle to off after send", () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} disabled={false} />);

    // Enable web search
    const toggle = screen.getByTestId("web-search-toggle");
    fireEvent.click(toggle);
    expect(toggle.textContent).toContain("on");

    // Send message
    const ta = screen.getByRole("textbox");
    fireEvent.change(ta, { target: { value: "test" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    // Web search should be back to off
    expect(toggle.textContent).toContain("off");
  });

  it("passes web search=true when toggle is on", () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} disabled={false} />);

    const toggle = screen.getByTestId("web-search-toggle");
    fireEvent.click(toggle);

    const ta = screen.getByRole("textbox");
    fireEvent.change(ta, { target: { value: "search this" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(onSend).toHaveBeenCalledWith("search this", "default", true);
  });

  it("model tier toggle switches between haiku and sonnet", () => {
    render(<MessageInput onSend={vi.fn()} disabled={false} />);
    const sonnetBtn = screen.getByText(/Sonnet/);
    fireEvent.click(sonnetBtn);

    const ta = screen.getByRole("textbox");
    fireEvent.change(ta, { target: { value: "strong question" } });

    const onSend = vi.fn();
    // Need fresh render with spy
    const { unmount } = render(<MessageInput onSend={onSend} disabled={false} />);
    const sonnet = screen.getAllByText(/Sonnet/)[1];
    fireEvent.click(sonnet);
    const ta2 = screen.getAllByRole("textbox")[1];
    fireEvent.change(ta2, { target: { value: "question" } });
    fireEvent.click(screen.getAllByRole("button", { name: /send/i })[1]);
    expect(onSend).toHaveBeenCalledWith("question", "strong", false);
    unmount();
  });
});
