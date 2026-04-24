"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { SourceCard } from "./SourceCard";
import { SourceDrawer } from "./SourceDrawer";
import type { SourceChunk } from "@/lib/api/types";

interface MessageSourcesProps {
  sources: SourceChunk[];
  defaultOpen?: boolean;
}

export function MessageSources({
  sources,
  defaultOpen = false,
}: MessageSourcesProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [selected, setSelected] = useState<SourceChunk | null>(null);

  if (sources.length === 0) return null;

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
          {sources.length} source{sources.length !== 1 ? "s" : ""}
        </span>
      </button>

      {open && (
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {sources.map((s) => (
            <SourceCard key={s.chunk_id} source={s} onClick={setSelected} />
          ))}
        </div>
      )}

      <SourceDrawer source={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
