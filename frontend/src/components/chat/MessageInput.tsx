"use client";

import { useEffect, useRef, useState } from "react";
import { Globe, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ModelTier } from "@/lib/api/types";

interface MessageInputProps {
  onSend: (text: string, tier: ModelTier, enableWebSearch: boolean) => void;
  disabled: boolean;
}

export function MessageInput({ onSend, disabled }: MessageInputProps) {
  const [text, setText] = useState("");
  const [tier, setTier] = useState<ModelTier>("default");
  const [webSearch, setWebSearch] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  // Ctrl/Cmd+K → focus input
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
    onSend(trimmed, tier, webSearch);
    setText("");
    setWebSearch(false); // reset after every send — opt-in per question
  }

  return (
    <div className="border-t border-zinc-800 bg-zinc-950 px-4 py-3">
      <div className="max-w-2xl mx-auto">
        {/* Controls row */}
        <div className="flex items-center gap-2 mb-2 flex-wrap">
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

          <span className="text-zinc-700 mx-1">·</span>

          <button
            onClick={() => setWebSearch((v) => !v)}
            title="Allow Mentor to search the web for this question. Off by default."
            data-testid="web-search-toggle"
            className={`flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full transition-colors ${
              webSearch
                ? "bg-emerald-900 text-emerald-200"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <Globe className="h-3 w-3" />
            Web search: {webSearch ? "on" : "off"}
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
            aria-label="Send"
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
