"use client";

import { useEffect, useState } from "react";
import { MessageList } from "@/components/chat/MessageList";
import { MessageInput } from "@/components/chat/MessageInput";
import { MemorySuggestionBanner } from "@/components/chat/MemorySuggestionBanner";
import { MemoryPreviewDialog } from "@/components/chat/MemoryPreviewDialog";
import { useChat } from "@/hooks/useChat";
import { toast } from "@/components/ui/toaster";
import type { ModelTier } from "@/lib/api/types";

export default function ConversationPage({
  params,
}: {
  params: { id: string };
}) {
  const { id } = params;
  const {
    messages,
    isStreaming,
    loading,
    error,
    sendMessage,
    sendWithWebSearch,
    regenerate,
    memorySuggestion,
    dismissMemorySuggestion,
  } = useChat(id);

  const [previewOpen, setPreviewOpen] = useState(false);

  useEffect(() => {
    if (error) {
      toast.error("Chat error", error);
    }
  }, [error]);

  async function handleSend(text: string, tier: ModelTier, enableWebSearch: boolean) {
    if (enableWebSearch) {
      await sendWithWebSearch(text, tier);
    } else {
      await sendMessage(text, tier);
    }
  }

  async function handleTryWithWebSearch(text: string, tier: ModelTier) {
    await sendWithWebSearch(text, tier);
  }

  function handleMemorySaved(documentId: string) {
    toast.success("Notes saved", "Conversation notes added to your knowledge base.");
    dismissMemorySuggestion();
  }

  return (
    <>
      <MessageList
        messages={messages}
        loading={loading}
        isStreaming={isStreaming}
        onRegenerate={regenerate}
        onTryWithWebSearch={handleTryWithWebSearch}
        memorySuggestion={memorySuggestion}
        conversationId={id}
        onDismissMemorySuggestion={dismissMemorySuggestion}
        onPreviewMemory={() => setPreviewOpen(true)}
      />
      <MessageInput onSend={handleSend} disabled={isStreaming} />
      <MemoryPreviewDialog
        open={previewOpen}
        conversationId={id}
        onClose={() => setPreviewOpen(false)}
        onSaved={handleMemorySaved}
      />
    </>
  );
}
