"use client";

import { useCallback, useEffect, useRef } from "react";
import { Message } from "./Message";
import { MemorySuggestionBanner } from "./MemorySuggestionBanner";
import { Skeleton } from "@/components/ui/skeleton";
import type { LocalMessage, MemorySuggestion, ModelTier } from "@/lib/api/types";

interface MessageListProps {
  messages: LocalMessage[];
  loading: boolean;
  isStreaming: boolean;
  onRegenerate: (serverId: string, localId: string) => void;
  onTryWithWebSearch?: (text: string, tier: ModelTier) => void;
  memorySuggestion?: MemorySuggestion | null;
  conversationId?: string;
  onDismissMemorySuggestion?: () => void;
  onPreviewMemory?: () => void;
}

export function MessageList({
  messages,
  loading,
  isStreaming,
  onRegenerate,
  onTryWithWebSearch,
  memorySuggestion,
  conversationId,
  onDismissMemorySuggestion,
  onPreviewMemory,
}: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const shouldAutoScroll = useRef(true);

  const scrollToBottom = useCallback(() => {
    if (shouldAutoScroll.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  function handleScroll() {
    const el = containerRef.current;
    if (!el) return;
    const isNearBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight < 150;
    shouldAutoScroll.current = isNearBottom;
  }

  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-4 w-1/4 ml-auto" />
            <Skeleton className="h-16 w-3/4" />
          </div>
        ))}
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-600 text-sm">
        Send a message to start the conversation.
      </div>
    );
  }

  const assistantMessages = messages.filter((m) => m.role === "assistant");
  const lastAssistantId =
    assistantMessages[assistantMessages.length - 1]?.localId;

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto px-4 py-6"
    >
      <div className="max-w-2xl mx-auto space-y-6">
        {messages.map((msg) => (
          <Message
            key={msg.localId}
            message={msg}
            isLatest={msg.localId === lastAssistantId}
            onRegenerate={onRegenerate}
            onTryWithWebSearch={onTryWithWebSearch}
            isStreaming={isStreaming}
          />
        ))}
        {memorySuggestion && conversationId && onDismissMemorySuggestion && onPreviewMemory && (
          <MemorySuggestionBanner
            suggestion={memorySuggestion}
            conversationId={conversationId}
            onDismiss={onDismissMemorySuggestion}
            onPreview={onPreviewMemory}
          />
        )}
      </div>
      <div ref={bottomRef} />
    </div>
  );
}
