"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertTriangle, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { DuplicateResolutionModal } from "./DuplicateResolutionModal";
import { formatBytes, formatRelative } from "@/lib/utils";
import type { DocumentListItem as DocItem } from "@/lib/api/types";

interface DocumentListItemProps {
  doc: DocItem;
  onDelete: (id: string) => void;
  onRefresh?: () => void;
}

export function DocumentListItem({ doc, onDelete, onRefresh }: DocumentListItemProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [duplicateOpen, setDuplicateOpen] = useState(false);

  const isDuplicatePending = doc.status === "awaiting_user_decision";

  function handleDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (confirmDelete) {
      onDelete(doc.id);
    } else {
      setConfirmDelete(true);
      setTimeout(() => setConfirmDelete(false), 3000);
    }
  }

  function handleDuplicateBadgeClick(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDuplicateOpen(true);
  }

  function handleDuplicateResolved() {
    setDuplicateOpen(false);
    onRefresh?.();
  }

  return (
    <>
      <div className="group flex items-center justify-between gap-4 rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3 transition-colors hover:border-zinc-700">
        <Link
          href={`/documents/${doc.id}`}
          className="flex items-center gap-3 min-w-0 flex-1"
        >
          <div className="min-w-0">
            <p className="text-sm text-zinc-200 truncate font-mono">
              {doc.filename}
            </p>
            <p className="text-xs text-zinc-600 mt-0.5">
              {formatBytes(doc.size_bytes)} · {formatRelative(doc.created_at)}
              {doc.detected_language && ` · ${doc.detected_language}`}
            </p>
          </div>
        </Link>

        <div className="flex items-center gap-2 flex-shrink-0">
          <Badge variant={doc.file_category === "code" ? "purple" : "default"}>
            {doc.file_category}
          </Badge>
          {isDuplicatePending ? (
            <button
              onClick={handleDuplicateBadgeClick}
              className="flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium text-amber-400 border border-amber-700/50 bg-amber-950/30 hover:bg-amber-900/40 transition-colors"
              title="Possible duplicate — click to resolve"
            >
              <AlertTriangle className="h-3 w-3" />
              Possible duplicate
            </button>
          ) : (
            <StatusBadge status={doc.status} />
          )}
          <button
            onClick={handleDelete}
            className={`rounded p-1 transition-colors opacity-0 group-hover:opacity-100 ${
              confirmDelete
                ? "text-red-400 hover:text-red-300 opacity-100"
                : "text-zinc-600 hover:text-zinc-400"
            }`}
            title={confirmDelete ? "Click again to confirm" : "Delete"}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {isDuplicatePending && (
        <DuplicateResolutionModal
          documentId={doc.id}
          filename={doc.filename}
          open={duplicateOpen}
          onClose={() => setDuplicateOpen(false)}
          onResolved={handleDuplicateResolved}
        />
      )}
    </>
  );
}
