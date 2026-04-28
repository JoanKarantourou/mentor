"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, FileText } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { getDuplicates, resolveDuplicate } from "@/lib/api/curation";
import type { DuplicateMatch } from "@/lib/api/types";

interface DuplicateResolutionModalProps {
  documentId: string;
  filename: string;
  open: boolean;
  onClose: () => void;
  onResolved: (action: "replace" | "keep_both" | "skip") => void;
}

export function DuplicateResolutionModal({
  documentId,
  filename,
  open,
  onClose,
  onResolved,
}: DuplicateResolutionModalProps) {
  const [matches, setMatches] = useState<DuplicateMatch[]>([]);
  const [loading, setLoading] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    getDuplicates(documentId)
      .then(setMatches)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [open, documentId]);

  async function handleAction(
    action: "replace" | "keep_both" | "skip",
    replaceTargetId?: string
  ) {
    setResolving(true);
    setError(null);
    try {
      await resolveDuplicate(documentId, action, replaceTargetId);
      onResolved(action);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setResolving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md bg-zinc-900 border-zinc-800 text-zinc-100">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-sm font-semibold text-amber-400">
            <AlertTriangle className="h-4 w-4" />
            Possible duplicate detected
          </DialogTitle>
        </DialogHeader>

        <p className="text-xs text-zinc-400">
          <span className="text-zinc-200 font-medium">{filename}</span> looks similar to:
        </p>

        {loading ? (
          <div className="py-4 text-xs text-zinc-500">Loading matches…</div>
        ) : (
          <div className="flex flex-col gap-2">
            {matches.map((m) => (
              <div
                key={m.existing_document_id}
                className="flex items-start gap-2 rounded border border-zinc-800 bg-zinc-800/50 p-2"
              >
                <FileText className="h-4 w-4 text-zinc-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-zinc-200 truncate">
                    {m.existing_filename}
                  </p>
                  <p className="text-xs text-zinc-500">
                    {m.match_type === "exact" ? "Exact match" : `${Math.round(m.similarity * 100)}% similar`}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => handleAction("replace", m.existing_document_id)}
                  disabled={resolving}
                  className="text-xs text-zinc-400 hover:text-amber-300 h-7 px-2 flex-shrink-0"
                >
                  Replace
                </Button>
              </div>
            ))}
          </div>
        )}

        {error && <p className="text-xs text-red-400">{error}</p>}

        <div className="flex justify-end gap-2 pt-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleAction("skip")}
            disabled={resolving}
            className="text-xs text-zinc-500 hover:text-zinc-300"
          >
            Skip this upload
          </Button>
          <Button
            size="sm"
            onClick={() => handleAction("keep_both")}
            disabled={resolving}
            className="text-xs bg-zinc-700 hover:bg-zinc-600 text-zinc-100"
          >
            {resolving ? "Working…" : "Keep both"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
