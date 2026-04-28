"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getConversation,
  regenerateMessage,
  sendMessage,
} from "@/lib/api/chat";
import type {
  ConversationDetail,
  LocalMessage,
  ModelTier,
  SourceChunk,
  WebSource,
} from "@/lib/api/types";

function makeLocalId() {
  return `local-${Math.random().toString(36).slice(2)}`;
}

function nowIso() {
  return new Date().toISOString();
}

function convertApiMessages(detail: ConversationDetail): LocalMessage[] {
  return detail.messages.map((m) => ({
    localId: m.id,
    serverId: m.id,
    role: m.role,
    content: m.content,
    isStreaming: false,
    isLowConfidence: m.low_confidence,
    webSearchUsed: m.web_search_used,
    webSearchPending: false,
    webSearchResultCount: 0,
    sources: [],
    webSources: [],
    retrievedChunkIds: m.retrieved_chunk_ids ?? [],
    modelUsed: m.model_used ?? undefined,
    createdAt: m.created_at,
  }));
}

export function useChat(conversationId: string | null) {
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentConversationId, setCurrentConversationId] = useState<
    string | null
  >(conversationId);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  // Load existing conversation
  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      setCurrentConversationId(null);
      return;
    }

    setLoading(true);
    setError(null);
    getConversation(conversationId)
      .then((detail) => {
        setMessages(convertApiMessages(detail));
        setCurrentConversationId(conversationId);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load conversation");
      })
      .finally(() => setLoading(false));
  }, [conversationId]);

  const updateMessage = useCallback(
    (localId: string, update: Partial<LocalMessage>) => {
      setMessages((prev) =>
        prev.map((m) => (m.localId === localId ? { ...m, ...update } : m))
      );
    },
    []
  );

  const sendChat = useCallback(
    async (text: string, modelTier: ModelTier, enableWebSearch: boolean = false) => {
      if (isStreaming) return;

      const userLocalId = makeLocalId();
      const assistantLocalId = makeLocalId();

      const userMsg: LocalMessage = {
        localId: userLocalId,
        role: "user",
        content: text,
        isStreaming: false,
        isLowConfidence: false,
        webSearchUsed: false,
        webSearchPending: false,
        webSearchResultCount: 0,
        sources: [],
        webSources: [],
        retrievedChunkIds: [],
        createdAt: nowIso(),
      };

      const assistantMsg: LocalMessage = {
        localId: assistantLocalId,
        role: "assistant",
        content: "",
        isStreaming: true,
        isLowConfidence: false,
        webSearchUsed: false,
        webSearchPending: enableWebSearch,
        webSearchResultCount: 0,
        sources: [],
        webSources: [],
        retrievedChunkIds: [],
        createdAt: nowIso(),
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);
      setError(null);

      try {
        const stream = sendMessage({
          message: text,
          conversation_id: currentConversationId,
          model_tier: modelTier,
          enable_web_search: enableWebSearch,
        });

        let retrievedChunkIds: string[] = [];
        let sources: SourceChunk[] = [];
        let webSources: WebSource[] = [];
        let isLowConf = false;

        for await (const event of stream) {
          switch (event.type) {
            case "retrieval":
              retrievedChunkIds = event.chunk_ids;
              updateMessage(assistantLocalId, { retrievedChunkIds });
              break;
            case "confidence":
              isLowConf = !event.sufficient;
              updateMessage(assistantLocalId, { isLowConfidence: isLowConf });
              break;
            case "web_search_started":
              updateMessage(assistantLocalId, { webSearchPending: true });
              break;
            case "web_search_results":
              updateMessage(assistantLocalId, {
                webSearchPending: false,
                webSearchUsed: true,
                webSearchResultCount: event.results.length,
                isLowConfidence: false,
              });
              break;
            case "token":
              setMessages((prev) =>
                prev.map((m) =>
                  m.localId === assistantLocalId
                    ? { ...m, content: m.content + event.text }
                    : m
                )
              );
              break;
            case "sources":
              sources = event.sources;
              webSources = event.web_sources;
              updateMessage(assistantLocalId, { sources, webSources });
              break;
            case "message_persisted":
              setCurrentConversationId(event.conversation_id);
              setMessages((prev) =>
                prev.map((m) =>
                  m.localId === assistantLocalId
                    ? { ...m, serverId: event.assistant_message_id }
                    : m.localId === userLocalId
                      ? { ...m, serverId: m.serverId ?? m.localId }
                      : m
                )
              );
              break;
            case "error":
              updateMessage(assistantLocalId, {
                content: `Error: ${event.message}`,
                isStreaming: false,
                webSearchPending: false,
              });
              setError(event.message);
              break;
            case "done":
              updateMessage(assistantLocalId, { isStreaming: false, webSearchPending: false });
              break;
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Unknown error";
        updateMessage(assistantLocalId, {
          content: `Error: ${msg}`,
          isStreaming: false,
          webSearchPending: false,
        });
        setError(msg);
      } finally {
        setIsStreaming(false);
      }
    },
    [isStreaming, currentConversationId, updateMessage]
  );

  const regenerate = useCallback(
    async (messageServerId: string, localId: string) => {
      if (isStreaming) return;

      updateMessage(localId, {
        content: "",
        isStreaming: true,
        sources: [],
        webSources: [],
        isLowConfidence: false,
        webSearchUsed: false,
        webSearchPending: false,
        webSearchResultCount: 0,
      });
      setIsStreaming(true);
      setError(null);

      try {
        const stream = regenerateMessage(messageServerId);

        for await (const event of stream) {
          switch (event.type) {
            case "web_search_started":
              updateMessage(localId, { webSearchPending: true });
              break;
            case "web_search_results":
              updateMessage(localId, {
                webSearchPending: false,
                webSearchUsed: true,
                webSearchResultCount: event.results.length,
                isLowConfidence: false,
              });
              break;
            case "token":
              setMessages((prev) =>
                prev.map((m) =>
                  m.localId === localId
                    ? { ...m, content: m.content + event.text }
                    : m
                )
              );
              break;
            case "sources":
              updateMessage(localId, {
                sources: event.sources,
                webSources: event.web_sources,
              });
              break;
            case "message_persisted":
              updateMessage(localId, {
                serverId: event.assistant_message_id,
              });
              break;
            case "confidence":
              updateMessage(localId, { isLowConfidence: !event.sufficient });
              break;
            case "error":
              updateMessage(localId, {
                content: `Error: ${event.message}`,
                isStreaming: false,
                webSearchPending: false,
              });
              setError(event.message);
              break;
            case "done":
              updateMessage(localId, { isStreaming: false, webSearchPending: false });
              break;
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Unknown error";
        updateMessage(localId, {
          content: `Error: ${msg}`,
          isStreaming: false,
          webSearchPending: false,
        });
        setError(msg);
      } finally {
        setIsStreaming(false);
      }
    },
    [isStreaming, updateMessage]
  );

  const sendWithWebSearch = useCallback(
    (text: string, modelTier: ModelTier) => sendChat(text, modelTier, true),
    [sendChat]
  );

  return {
    messages,
    isStreaming,
    conversationId: currentConversationId,
    loading,
    error,
    sendMessage: sendChat,
    sendWithWebSearch,
    regenerate,
  };
}
