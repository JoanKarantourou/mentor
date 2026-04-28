import { apiFetch } from "./client";
import type { DuplicateMatch } from "./types";

// ---------------------------------------------------------------------------
// Memory extraction
// ---------------------------------------------------------------------------

export interface ExtractMemoryPreview {
  title: string;
  content: string;
  fact_count: number;
  source_message_count: number;
}

export interface SavedMemoryResult {
  document_id: string;
}

export function previewMemoryExtraction(conversationId: string): Promise<ExtractMemoryPreview> {
  return apiFetch<ExtractMemoryPreview>(`/conversations/${conversationId}/extract-memory`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approve: false }),
  });
}

export function saveMemoryExtraction(
  conversationId: string,
  opts: { title_override?: string; content_override?: string }
): Promise<SavedMemoryResult> {
  return apiFetch<SavedMemoryResult>(`/conversations/${conversationId}/extract-memory`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approve: true, ...opts }),
  });
}

// ---------------------------------------------------------------------------
// Duplicate resolution
// ---------------------------------------------------------------------------

export function getDuplicates(documentId: string): Promise<DuplicateMatch[]> {
  return apiFetch<DuplicateMatch[]>(`/documents/${documentId}/duplicates`);
}

export function resolveDuplicate(
  documentId: string,
  action: "replace" | "keep_both" | "skip",
  replaceTargetId?: string
): Promise<void> {
  return apiFetch<void>(`/documents/${documentId}/resolve-duplicate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, replace_target_id: replaceTargetId ?? null }),
  });
}
