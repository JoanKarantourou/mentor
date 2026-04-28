"use client";

import { useState } from "react";
import { BookOpen, X } from "lucide-react";
import type { MemorySuggestion } from "@/lib/api/types";

interface MemorySuggestionBannerProps {
  suggestion: MemorySuggestion;
  conversationId: string;
  onDismiss: () => void;
  onPreview: () => void;
}

export function MemorySuggestionBanner({
  suggestion,
  conversationId,
  onDismiss,
  onPreview,
}: MemorySuggestionBannerProps) {
  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded-md border border-blue-800/40 bg-blue-950/20 px-3 py-2 text-xs text-blue-300 mt-3"
    >
      <BookOpen className="h-3.5 w-3.5 mt-0.5 flex-shrink-0 text-blue-400" />
      <div className="flex flex-col gap-1.5 flex-1 min-w-0">
        <span>
          This conversation has useful context
          {suggestion.preview_count > 0 && ` (~${suggestion.preview_count} key facts)`}.
          Save to your knowledge base?
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={onPreview}
            className="rounded px-2 py-0.5 text-xs font-medium text-blue-300 hover:bg-blue-900/40 border border-blue-700/50 transition-colors"
          >
            Preview
          </button>
          <button
            onClick={onDismiss}
            className="text-xs text-blue-500 hover:text-blue-300 transition-colors"
          >
            Not now
          </button>
        </div>
      </div>
      <button
        onClick={onDismiss}
        aria-label="Dismiss"
        className="flex-shrink-0 text-blue-600 hover:text-blue-300 transition-colors"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
