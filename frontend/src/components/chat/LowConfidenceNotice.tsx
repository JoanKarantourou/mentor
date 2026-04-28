import { AlertTriangle, Globe, Upload } from "lucide-react";
import type { GapAnalysis } from "@/lib/api/types";

interface LowConfidenceNoticeProps {
  onTryWithWebSearch?: () => void;
  onUploadDocument?: () => void;
  gapAnalysis?: GapAnalysis;
}

export function LowConfidenceNotice({
  onTryWithWebSearch,
  onUploadDocument,
  gapAnalysis,
}: LowConfidenceNoticeProps) {
  if (gapAnalysis) {
    return (
      <div className="rounded-md border border-amber-700/40 bg-amber-950/20 px-3 py-2.5 text-xs text-amber-400 mb-2 space-y-2">
        <div className="flex items-center gap-1.5">
          <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
          <span className="font-medium">Low confidence — not enough indexed content.</span>
        </div>

        {gapAnalysis.missing_topic && (
          <div>
            <span className="text-amber-500">What seems to be missing: </span>
            <span className="text-amber-300">{gapAnalysis.missing_topic}</span>
          </div>
        )}

        {gapAnalysis.related_topics_present.length > 0 && (
          <div>
            <span className="text-amber-500">Your corpus covers nearby topics: </span>
            <span className="text-amber-300">
              {gapAnalysis.related_topics_present.join(", ")}
            </span>
          </div>
        )}

        {gapAnalysis.suggested_document_types.length > 0 && (
          <div>
            <span className="text-amber-500">Documents that might help: </span>
            <span className="text-amber-300">
              {gapAnalysis.suggested_document_types.join(", ")}
            </span>
          </div>
        )}

        <div className="flex items-center gap-2 pt-0.5">
          {onTryWithWebSearch && (
            <button
              onClick={onTryWithWebSearch}
              className="flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-emerald-400 hover:bg-emerald-900/30 transition-colors"
            >
              <Globe className="h-3 w-3" />
              Try with web search
            </button>
          )}
          {onUploadDocument && (
            <button
              onClick={onUploadDocument}
              className="flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-blue-400 hover:bg-blue-900/30 transition-colors"
            >
              <Upload className="h-3 w-3" />
              Upload a document
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-2 rounded-md border border-amber-700/40 bg-amber-950/20 px-3 py-2 text-xs text-amber-400 mb-2">
      <AlertTriangle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
      <div className="flex flex-col gap-1.5">
        <span>Low confidence — answer based on limited corpus match.</span>
        <div className="flex items-center gap-2">
          {onTryWithWebSearch && (
            <button
              onClick={onTryWithWebSearch}
              className="flex items-center gap-1 self-start rounded px-1.5 py-0.5 text-xs text-emerald-400 hover:bg-emerald-900/30 transition-colors"
            >
              <Globe className="h-3 w-3" />
              Try with web search
            </button>
          )}
          {onUploadDocument && (
            <button
              onClick={onUploadDocument}
              className="flex items-center gap-1 self-start rounded px-1.5 py-0.5 text-xs text-blue-400 hover:bg-blue-900/30 transition-colors"
            >
              <Upload className="h-3 w-3" />
              Upload a document
            </button>
          )}
        </div>
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
