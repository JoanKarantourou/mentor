"use client";

import { useState } from "react";
import Link from "next/link";
import { Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelative } from "@/lib/utils";
import type { Conversation } from "@/lib/api/types";

interface ConversationListItemProps {
  conversation: Conversation;
  active: boolean;
  onDelete: (id: string) => void;
}

export function ConversationListItem({
  conversation,
  active,
  onDelete,
}: ConversationListItemProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  function handleDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (confirmDelete) {
      onDelete(conversation.id);
    } else {
      setConfirmDelete(true);
      setTimeout(() => setConfirmDelete(false), 3000);
    }
  }

  return (
    <Link
      href={`/chat/${conversation.id}`}
      className={cn(
        "group flex items-start justify-between gap-2 rounded-md px-3 py-2.5 text-sm transition-colors",
        active
          ? "bg-zinc-800 text-zinc-100"
          : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200"
      )}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm leading-snug">
          {conversation.title ?? "New conversation"}
        </p>
        <p className="text-xs text-zinc-600 mt-0.5">
          {formatRelative(conversation.updated_at)} ·{" "}
          {conversation.message_count}{" "}
          {conversation.message_count === 1 ? "msg" : "msgs"}
        </p>
      </div>
      <button
        onClick={handleDelete}
        className={cn(
          "flex-shrink-0 rounded p-1 transition-colors opacity-0 group-hover:opacity-100",
          confirmDelete
            ? "text-red-400 hover:text-red-300 opacity-100"
            : "text-zinc-600 hover:text-zinc-400"
        )}
        title={confirmDelete ? "Click again to confirm" : "Delete"}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </Link>
  );
}
