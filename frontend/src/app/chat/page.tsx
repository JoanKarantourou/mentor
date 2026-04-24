"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { MessageList } from "@/components/chat/MessageList";
import { MessageInput } from "@/components/chat/MessageInput";
import { useChat } from "@/hooks/useChat";
import { toast } from "@/components/ui/toaster";
import type { ModelTier } from "@/lib/api/types";

export default function NewChatPage() {
  const router = useRouter();
  const { messages, isStreaming, conversationId, error, sendMessage, regenerate } =
    useChat(null);

  // Navigate to the conversation page after streaming completes
  useEffect(() => {
    if (conversationId && !isStreaming) {
      router.replace(`/chat/${conversationId}`);
    }
  }, [conversationId, isStreaming, router]);

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
      {messages.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-6 px-4">
          <div className="text-center">
            <h1 className="text-2xl font-semibold text-zinc-100">
              Ask mentor anything
            </h1>
            <p className="mt-2 text-sm text-zinc-500">
              Answers are grounded in your indexed documents.
            </p>
          </div>
          <div className="w-full max-w-2xl">
            <MessageInput onSend={handleSend} disabled={isStreaming} />
          </div>
        </div>
      ) : (
        <>
          <MessageList
            messages={messages}
            loading={false}
            isStreaming={isStreaming}
            onRegenerate={regenerate}
          />
          <MessageInput onSend={handleSend} disabled={isStreaming} />
        </>
      )}
    </>
  );
}
