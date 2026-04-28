import { AlertTriangle, Globe } from "lucide-react";

interface LowConfidenceNoticeProps {
  onTryWithWebSearch?: () => void;
}

export function LowConfidenceNotice({ onTryWithWebSearch }: LowConfidenceNoticeProps) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-amber-700/40 bg-amber-950/20 px-3 py-2 text-xs text-amber-400 mb-2">
      <AlertTriangle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
      <div className="flex flex-col gap-1.5">
        <span>Low confidence — answer based on limited corpus match.</span>
        {onTryWithWebSearch && (
          <button
            onClick={onTryWithWebSearch}
            className="flex items-center gap-1 self-start rounded px-1.5 py-0.5 text-xs text-emerald-400 hover:bg-emerald-900/30 transition-colors"
          >
            <Globe className="h-3 w-3" />
            Try with web search
          </button>
        )}
      </div>
    </div>
  );
}

interface WebSearchUsedNoticeProps {
  resultCount: number;
}

export function WebSearchUsedNotice({ resultCount }: WebSearchUsedNoticeProps) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-emerald-800/40 bg-emerald-950/20 px-3 py-1.5 text-xs text-emerald-400 mb-2">
      <Globe className="h-3.5 w-3.5 flex-shrink-0" />
      <span>Not in your documents — searched the web instead ({resultCount} results).</span>
    </div>
  );
}
