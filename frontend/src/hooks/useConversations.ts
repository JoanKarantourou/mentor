"use client";

import { useCallback, useEffect, useState } from "react";
import { deleteConversation, listConversations } from "@/lib/api/chat";
import type { Conversation } from "@/lib/api/types";

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await listConversations();
      setConversations(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load conversations");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const remove = useCallback(
    async (id: string) => {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
    },
    []
  );

  const prepend = useCallback((conv: Conversation) => {
    setConversations((prev) => {
      const filtered = prev.filter((c) => c.id !== conv.id);
      return [conv, ...filtered];
    });
  }, []);

  return { conversations, loading, error, refresh, remove, prepend };
}
