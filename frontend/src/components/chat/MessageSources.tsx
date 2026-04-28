"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, FileText, Globe } from "lucide-react";
import { SourceCard, WebSourceCard } from "./SourceCard";
import { SourceDrawer } from "./SourceDrawer";
import type { SourceChunk, WebSource } from "@/lib/api/types";

interface MessageSourcesProps {
  sources: SourceChunk[];
  webSources?: WebSource[];
  defaultOpen?: boolean;
}

export function MessageSources({
  sources,
  webSources = [],
  defaultOpen = false,
}: MessageSourcesProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [selected, setSelected] = useState<SourceChunk | null>(null);

  const hasCorpus = sources.length > 0;
  const hasWeb = webSources.length > 0;

  if (!hasCorpus && !hasWeb) return null;

  const totalCount = sources.length + webSources.length;

  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
      >
        {open ? (
          <ChevronDown className="h-3.5 w-3.5" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5" />
        )}
        <span>
          {totalCount} source{totalCount !== 1 ? "s" : ""}
        </span>
      </button>

      {open && (
        <div className="mt-2 space-y-4">
          {hasCorpus && (
            <div>
              <p className="flex items-center gap-1.5 text-xs text-zinc-600 mb-2">
                <FileText className="h-3 w-3" />
                From your documents ({sources.length})
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {sources.map((s) => (
                  <SourceCard key={s.chunk_id} source={s} onClick={setSelected} />
                ))}
              </div>
            </div>
          )}

          {hasWeb && (
            <div>
              <p className="flex items-center gap-1.5 text-xs text-zinc-600 mb-2">
                <Globe className="h-3 w-3" />
                From the web ({webSources.length})
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {webSources.map((w) => (
                  <WebSourceCard key={`${w.rank}-${w.url}`} source={w} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <SourceDrawer source={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
