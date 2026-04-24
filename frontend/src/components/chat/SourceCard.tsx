import { FileText } from "lucide-react";
import type { SourceChunk } from "@/lib/api/types";

interface SourceCardProps {
  source: SourceChunk;
  onClick: (source: SourceChunk) => void;
}

export function SourceCard({ source, onClick }: SourceCardProps) {
  const score = Math.round(source.score * 100);
  const preview = source.text_preview.slice(0, 200);

  return (
    <button
      onClick={() => onClick(source)}
      className="w-full rounded-md border border-zinc-800 bg-zinc-900 p-3 text-left transition-colors hover:border-zinc-700 hover:bg-zinc-800/60"
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5 min-w-0">
          <FileText className="h-3.5 w-3.5 text-zinc-500 flex-shrink-0" />
          <span className="text-xs font-medium text-zinc-300 truncate">
            {source.filename}
          </span>
        </div>
        <span className="text-xs text-zinc-500 flex-shrink-0">{score}%</span>
      </div>
      <p className="text-xs text-zinc-500 leading-relaxed line-clamp-2 font-mono">
        {preview}
        {source.text_preview.length > 200 && "…"}
      </p>
    </button>
  );
}
