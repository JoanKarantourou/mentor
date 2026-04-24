"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Markdown } from "@/components/shared/Markdown";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Skeleton } from "@/components/ui/skeleton";
import { getDocumentContent, getDocumentChunks } from "@/lib/api/documents";
import { formatBytes } from "@/lib/utils";
import type { Chunk, DocumentDetail as DocDetail } from "@/lib/api/types";

interface DocumentDetailProps {
  document: DocDetail;
}

function ChunkItem({ chunk }: { chunk: Chunk }) {
  const [expanded, setExpanded] = useState(false);
  const heading = (chunk.meta as Record<string, string>)?.heading ?? "";

  return (
    <div className="rounded-md border border-zinc-800 overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-zinc-800/40 transition-colors"
      >
        <div className="flex items-center gap-2 min-w-0">
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-zinc-500 flex-shrink-0" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-zinc-500 flex-shrink-0" />
          )}
          <span className="text-xs text-zinc-400 truncate font-mono">
            #{chunk.chunk_index}{heading && ` · ${heading}`}
          </span>
        </div>
        <span className="text-xs text-zinc-600 flex-shrink-0">
          {chunk.token_count} tokens
        </span>
      </button>
      {expanded && (
        <div className="border-t border-zinc-800 px-4 py-3">
          <pre className="whitespace-pre-wrap font-mono text-xs text-zinc-300 leading-relaxed">
            {chunk.text}
          </pre>
        </div>
      )}
    </div>
  );
}

export function DocumentDetail({ document }: DocumentDetailProps) {
  const [content, setContent] = useState<string | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [contentLoading, setContentLoading] = useState(false);
  const [chunksLoading, setChunksLoading] = useState(false);

  const isContentReady = ["ready", "chunking", "embedding", "indexed"].includes(
    document.status
  );
  const isIndexed = document.status === "indexed";

  useEffect(() => {
    if (!isContentReady) return;
    setContentLoading(true);
    getDocumentContent(document.id)
      .then((r) => setContent(r.content))
      .catch(() => setContent(null))
      .finally(() => setContentLoading(false));
  }, [document.id, isContentReady]);

  useEffect(() => {
    if (!isIndexed) return;
    setChunksLoading(true);
    getDocumentChunks(document.id)
      .then(setChunks)
      .catch(() => setChunks([]))
      .finally(() => setChunksLoading(false));
  }, [document.id, isIndexed]);

  return (
    <div>
      {/* Metadata */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6 text-sm">
        {[
          ["Status", <StatusBadge key="s" status={document.status} />],
          ["Category", document.file_category],
          ["Size", formatBytes(document.size_bytes)],
          ["Language", document.detected_language ?? "—"],
          ["Type", document.content_type],
          ["Uploaded by", document.uploaded_by],
        ].map(([label, value]) => (
          <div key={String(label)}>
            <p className="text-xs text-zinc-600 mb-1">{label}</p>
            <div className="text-zinc-300">{value}</div>
          </div>
        ))}
      </div>

      <Tabs defaultValue="content">
        <TabsList>
          <TabsTrigger value="content">Content</TabsTrigger>
          <TabsTrigger value="chunks" disabled={!isIndexed}>
            Chunks {isIndexed && `(${chunks.length})`}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="content">
          {contentLoading ? (
            <div className="space-y-2">
              {[...Array(6)].map((_, i) => (
                <Skeleton key={i} className="h-4 w-full" />
              ))}
            </div>
          ) : content ? (
            <Markdown content={content} />
          ) : (
            <p className="text-sm text-zinc-600">
              {isContentReady
                ? "Could not load content."
                : "Document is still processing."}
            </p>
          )}
        </TabsContent>

        <TabsContent value="chunks">
          {chunksLoading ? (
            <div className="space-y-2">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full rounded-md" />
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {chunks.map((c) => (
                <ChunkItem key={c.id} chunk={c} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
