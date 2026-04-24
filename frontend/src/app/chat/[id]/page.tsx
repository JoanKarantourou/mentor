"use client";

import { useEffect } from "react";
import { MessageList } from "@/components/chat/MessageList";
import { MessageInput } from "@/components/chat/MessageInput";
import { useChat } from "@/hooks/useChat";
import { toast } from "@/components/ui/toaster";
import type { ModelTier } from "@/lib/api/types";

export default function ConversationPage({
  params,
}: {
  params: { id: string };
}) {
  const { id } = params;
  const { messages, isStreaming, loading, error, sendMessage, regenerate } =
    useChat(id);

  useEffect(() => {
    if (error) {
      toast.error("Chat error", error);
    }
  }, [error]);

  async function handleSend(text: string, tier: ModelTier) {
    await sendMessage(text, tier);
  }

  return (
    <>
      <MessageList
        messages={messages}
        loading={loading}
        isStreaming={isStreaming}
        onRegenerate={regenerate}
      />
      <MessageInput onSend={handleSend} disabled={isStreaming} />
    </>
  );
}
