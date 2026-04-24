"use client";

import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { useDocumentStatus } from "@/hooks/useDocumentStatus";
import type { DocumentListItem, DocumentStatus } from "@/lib/api/types";

interface UploadItem {
  documentId: string;
  filename: string;
  status: DocumentStatus;
}

interface UploadItemRowProps {
  item: UploadItem;
  onUpdate: (doc: DocumentListItem) => void;
}

function UploadItemRow({ item, onUpdate }: UploadItemRowProps) {
  const { status } = useDocumentStatus(item.documentId, onUpdate);

  const isTerminal = status === "indexed" || status === "failed";
  const icon =
    status === "indexed" ? (
      <CheckCircle2 className="h-4 w-4 text-emerald-400" />
    ) : status === "failed" ? (
      <XCircle className="h-4 w-4 text-red-400" />
    ) : (
      <Loader2 className="h-4 w-4 text-blue-400 animate-spin" />
    );

  const label =
    status === "indexed"
      ? "Indexed"
      : status === "failed"
        ? "Failed"
        : status === "pending"
          ? "Queued"
          : status.charAt(0).toUpperCase() + status.slice(1);

  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-zinc-300 font-mono truncate">{item.filename}</span>
      <div className="flex items-center gap-1.5 flex-shrink-0">
        {icon}
        <span
          className={
            status === "indexed"
              ? "text-emerald-400"
              : status === "failed"
                ? "text-red-400"
                : "text-blue-400"
          }
        >
          {label}
        </span>
      </div>
    </div>
  );
}

interface UploadProgressProps {
  uploads: UploadItem[];
  onUpdate: (doc: DocumentListItem) => void;
}

export function UploadProgress({ uploads, onUpdate }: UploadProgressProps) {
  if (uploads.length === 0) return null;

  const allDone = uploads.every(
    (u) => u.status === "indexed" || u.status === "failed"
  );

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
        {allDone ? "Completed" : "Uploading & indexing"}
      </h3>
      <div className="space-y-2">
        {uploads.map((u) => (
          <UploadItemRow key={u.documentId} item={u} onUpdate={onUpdate} />
        ))}
      </div>
    </div>
  );
}

export type { UploadItem };
