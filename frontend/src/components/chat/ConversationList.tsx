"use client";

import { usePathname } from "next/navigation";
import { Skeleton } from "@/components/ui/skeleton";
import { ConversationListItem } from "./ConversationListItem";
import type { Conversation } from "@/lib/api/types";

interface ConversationListProps {
  conversations: Conversation[];
  loading: boolean;
  onDelete: (id: string) => void;
}

export function ConversationList({
  conversations,
  loading,
  onDelete,
}: ConversationListProps) {
  const pathname = usePathname();

  if (loading) {
    return (
      <div className="space-y-1 px-2">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-md" />
        ))}
      </div>
    );
  }

  if (conversations.length === 0) {
    return (
      <p className="px-4 py-3 text-xs text-zinc-600">
        No conversations yet. Start one above.
      </p>
    );
  }

  return (
    <div className="space-y-0.5 px-2">
      {conversations.map((conv) => (
        <ConversationListItem
          key={conv.id}
          conversation={conv}
          active={pathname === `/chat/${conv.id}`}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}
