"use client";

import { X } from "lucide-react";
import Link from "next/link";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { SourceChunk } from "@/lib/api/types";

interface SourceDrawerProps {
  source: SourceChunk | null;
  onClose: () => void;
}

export function SourceDrawer({ source, onClose }: SourceDrawerProps) {
  return (
    <Dialog open={source !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="fixed right-0 top-0 h-full w-full max-w-lg rounded-none border-l border-zinc-800 bg-zinc-950 flex flex-col p-0">
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm">
              {source?.filename}
            </DialogTitle>
          </DialogHeader>
          <div className="flex items-center gap-3">
            {source && (
              <Link
                href={`/documents/${source.document_id}`}
                className="text-xs text-blue-400 hover:text-blue-300"
              >
                Open document →
              </Link>
            )}
            <DialogClose className="rounded p-1 text-zinc-500 hover:text-zinc-300">
              <X className="h-4 w-4" />
            </DialogClose>
          </div>
        </div>
        <ScrollArea className="flex-1 px-5 py-4">
          {source && (
            <div>
              <div className="mb-3 flex items-center gap-2">
                <span className="text-xs text-zinc-500">
                  Similarity score:
                </span>
                <span className="text-xs font-medium text-zinc-300">
                  {Math.round(source.score * 100)}%
                </span>
              </div>
              <pre className="whitespace-pre-wrap font-mono text-sm text-zinc-300 leading-relaxed">
                {source.text_preview}
              </pre>
            </div>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
