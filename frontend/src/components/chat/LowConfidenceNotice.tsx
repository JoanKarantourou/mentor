import { AlertTriangle } from "lucide-react";

export function LowConfidenceNotice() {
  return (
    <div className="flex items-start gap-2 rounded-md border border-amber-700/40 bg-amber-950/20 px-3 py-2 text-xs text-amber-400 mb-2">
      <AlertTriangle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
      <span>
        Low confidence — answer based on limited corpus match.
      </span>
    </div>
  );
}
