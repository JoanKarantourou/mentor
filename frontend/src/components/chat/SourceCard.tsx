import { ExternalLink, FileText } from "lucide-react";
import type { SourceChunk, WebSource } from "@/lib/api/types";

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

interface WebSourceCardProps {
  source: WebSource;
}

export function WebSourceCard({ source }: WebSourceCardProps) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex flex-col rounded-md border border-zinc-800 bg-zinc-900 p-3 text-left transition-colors hover:border-zinc-700 hover:bg-zinc-800/60"
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5 min-w-0">
          <img
            src={`https://www.google.com/s2/favicons?domain=${source.source_domain}&sz=16`}
            alt=""
            className="h-3.5 w-3.5 flex-shrink-0"
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
          <span className="text-xs text-zinc-500 truncate">{source.source_domain}</span>
        </div>
        <ExternalLink className="h-3 w-3 text-zinc-600 flex-shrink-0 mt-0.5" />
      </div>
      <p className="text-xs font-medium text-zinc-300 mb-1 line-clamp-1">
        {source.title}
      </p>
      <p className="text-xs text-zinc-500 leading-relaxed line-clamp-2">
        {source.snippet}
      </p>
      {source.published_date && (
        <p className="text-xs text-zinc-600 mt-1">{source.published_date}</p>
      )}
    </a>
  );
}
