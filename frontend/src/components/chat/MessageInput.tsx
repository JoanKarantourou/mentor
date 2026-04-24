"use client";

import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ModelTier } from "@/lib/api/types";

interface MessageInputProps {
  onSend: (text: string, tier: ModelTier) => void;
  disabled: boolean;
}

export function MessageInput({ onSend, disabled }: MessageInputProps) {
  const [text, setText] = useState("");
  const [tier, setTier] = useState<ModelTier>("default");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  // Ctrl/Cmd+K → focus input (new chat shortcut handled at page level)
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        textareaRef.current?.focus();
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, tier);
    setText("");
  }

  return (
    <div className="border-t border-zinc-800 bg-zinc-950 px-4 py-3">
      <div className="max-w-2xl mx-auto">
        {/* Model tier toggle */}
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-zinc-600">Model:</span>
          <button
            onClick={() => setTier("default")}
            className={`text-xs px-2 py-0.5 rounded-full transition-colors ${
              tier === "default"
                ? "bg-zinc-700 text-zinc-200"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            Haiku · fast
          </button>
          <button
            onClick={() => setTier("strong")}
            className={`text-xs px-2 py-0.5 rounded-full transition-colors ${
              tier === "strong"
                ? "bg-blue-900 text-blue-200"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            Sonnet · stronger
          </button>
        </div>

        {/* Input row */}
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your documents…"
            disabled={disabled}
            rows={1}
            className="flex-1 resize-none rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 max-h-[200px] overflow-y-auto"
          />
          <Button
            onClick={submit}
            disabled={disabled || !text.trim()}
            size="icon"
            className="h-10 w-10 flex-shrink-0 rounded-xl"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
        <p className="mt-1.5 text-xs text-zinc-600">
          Enter to send · Shift+Enter for newline
        </p>
      </div>
    </div>
  );
}
