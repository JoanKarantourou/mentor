"use client";

import { useState } from "react";
import { Check, Copy, Globe, RefreshCw } from "lucide-react";
import { Markdown } from "@/components/shared/Markdown";
import { LowConfidenceNotice, WebSearchUsedNotice } from "./LowConfidenceNotice";
import { MessageSources } from "./MessageSources";
import { StreamingIndicator } from "./StreamingIndicator";
import type { LocalMessage, ModelTier } from "@/lib/api/types";

interface MessageProps {
  message: LocalMessage;
  isLatest: boolean;
  onRegenerate?: (serverId: string, localId: string) => void;
  onTryWithWebSearch?: (text: string, tier: ModelTier) => void;
  isStreaming: boolean;
}

export function Message({
  message,
  isLatest,
  onRegenerate,
  onTryWithWebSearch,
  isStreaming,
}: MessageProps) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(message.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  if (message.role === "user") {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-zinc-800 px-4 py-2.5 text-sm text-zinc-100">
          {message.content}
        </div>
      </div>
    );
  }

  // Assistant message
  const showWebSearchIndicator = message.webSearchPending || (message.webSearchUsed && message.isStreaming);
  const showWebUsedNotice = message.webSearchUsed && !message.isStreaming && message.isLowConfidence === false;

  return (
    <div className="group animate-fade-in">
      {/* Web search pending / found indicator */}
      {showWebSearchIndicator && (
        <div className="flex items-center gap-1.5 text-xs text-emerald-400 mb-2">
          <Globe className="h-3.5 w-3.5 animate-pulse" />
          {message.webSearchPending
            ? "Searching the web..."
            : `Found ${message.webSearchResultCount} web result${message.webSearchResultCount !== 1 ? "s" : ""}`}
        </div>
      )}

      {/* Confidence notices */}
      {message.isLowConfidence && !message.webSearchUsed && (
        <LowConfidenceNotice
          gapAnalysis={message.gapAnalysis}
          onTryWithWebSearch={
            onTryWithWebSearch
              ? () => onTryWithWebSearch(message.content, "default")
              : undefined
          }
        />
      )}
      {showWebUsedNotice && (
        <WebSearchUsedNotice resultCount={message.webSearchResultCount} />
      )}

      <div className="text-sm text-zinc-100">
        {message.isStreaming && message.content === "" ? (
          <StreamingIndicator />
        ) : (
          <Markdown content={message.content} />
        )}
      </div>

      {!message.isStreaming && message.content && (
        <div className="mt-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300 transition-colors"
            title="Copy"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </button>

          {onRegenerate && message.serverId && isLatest && !isStreaming && (
            <button
              onClick={() => onRegenerate(message.serverId!, message.localId)}
              className="flex items-center gap-1 rounded px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300 transition-colors"
              title="Regenerate with strong model"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              <span>Regenerate</span>
            </button>
          )}

          {message.modelUsed && (
            <span className="ml-1 text-xs text-zinc-600 font-mono">
              {message.modelUsed.split(":")[1] ?? message.modelUsed}
            </span>
          )}

          {/* Web search badge */}
          {message.webSearchUsed && (
            <span
              title="This answer used web search"
              className="ml-1 flex items-center gap-0.5 text-xs text-emerald-600"
            >
              <Globe className="h-3 w-3" />
            </span>
          )}
        </div>
      )}

      <MessageSources
        sources={message.sources}
        webSources={message.webSources}
        defaultOpen={isLatest}
      />
    </div>
  );
}
