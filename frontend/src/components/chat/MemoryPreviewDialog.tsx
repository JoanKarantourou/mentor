"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  previewMemoryExtraction,
  saveMemoryExtraction,
} from "@/lib/api/curation";

interface MemoryPreviewDialogProps {
  open: boolean;
  conversationId: string;
  onClose: () => void;
  onSaved: (documentId: string) => void;
}

export function MemoryPreviewDialog({
  open,
  conversationId,
  onClose,
  onSaved,
}: MemoryPreviewDialogProps) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [factCount, setFactCount] = useState(0);
  const [sourceMsgCount, setSourceMsgCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const preview = await previewMemoryExtraction(conversationId);
      setTitle(preview.title);
      setContent(preview.content);
      setFactCount(preview.fact_count);
      setSourceMsgCount(preview.source_message_count);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to extract memories");
    } finally {
      setLoading(false);
    }
  }, [conversationId]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const result = await saveMemoryExtraction(conversationId, {
        title_override: title,
        content_override: content,
      });
      onSaved(result.document_id);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg bg-zinc-900 border-zinc-800 text-zinc-100">
        <DialogHeader>
          <DialogTitle className="text-sm font-semibold text-zinc-100">
            Save conversation notes
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="py-8 text-center text-xs text-zinc-500">Extracting key facts…</div>
        ) : error ? (
          <div className="py-4 text-xs text-red-400">{error}</div>
        ) : (
          <div className="flex flex-col gap-3">
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Title</label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="bg-zinc-800 border-zinc-700 text-zinc-100 text-xs h-8"
              />
            </div>
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Content</label>
              <Textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={10}
                className="bg-zinc-800 border-zinc-700 text-zinc-100 text-xs font-mono resize-none"
              />
            </div>
            {sourceMsgCount > 0 && (
              <p className="text-xs text-zinc-500">
                Sourced from {sourceMsgCount} message{sourceMsgCount !== 1 ? "s" : ""} ·{" "}
                {factCount} fact{factCount !== 1 ? "s" : ""} identified
              </p>
            )}
            {error && <p className="text-xs text-red-400">{error}</p>}
          </div>
        )}

        <div className="flex items-center justify-between pt-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={load}
            disabled={loading || saving}
            className="text-xs text-zinc-400 hover:text-zinc-200"
          >
            <RefreshCw className="h-3 w-3 mr-1" />
            Regenerate
          </Button>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              disabled={saving}
              className="text-xs text-zinc-400"
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={loading || saving || !content}
              className="text-xs bg-blue-700 hover:bg-blue-600 text-white"
            >
              {saving ? "Saving…" : "Save to my documents"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
