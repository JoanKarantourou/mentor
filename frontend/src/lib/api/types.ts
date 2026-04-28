// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------

export type ModelTier = "default" | "strong";

export type DocumentStatus =
  | "pending"
  | "processing"
  | "ready"
  | "chunking"
  | "embedding"
  | "indexed"
  | "failed"
  | "awaiting_user_decision"
  | "skipped_duplicate";

export type FileCategory = "document" | "code";

// ---------------------------------------------------------------------------
// Chat types
// ---------------------------------------------------------------------------

export interface SourceChunk {
  chunk_id: string;
  document_id: string;
  filename: string;
  text_preview: string;
  score: number;
}

export interface WebSource {
  rank: number;
  title: string;
  url: string;
  snippet: string;
  published_date: string | null;
  source_domain: string;
}

export interface ChatRequest {
  message: string;
  conversation_id: string | null;
  model_tier: ModelTier;
  enable_web_search: boolean;
}

export interface GapAnalysis {
  missing_topic: string;
  related_topics_present: string[];
  suggested_document_types: string[];
  related_document_ids: string[];
}

export interface MemorySuggestion {
  should_suggest: boolean;
  reason: string;
  preview_count: number;
}

export interface DuplicateMatch {
  existing_document_id: string;
  existing_filename: string;
  similarity: number;
  match_type: "exact" | "near_duplicate";
  matching_chunks: number;
}

export type ChatEvent =
  | {
      type: "retrieval";
      chunk_ids: string[];
      top_similarity: number;
      avg_similarity: number;
    }
  | { type: "confidence"; sufficient: boolean; reason: string }
  | { type: "web_search_started" }
  | { type: "web_search_results"; results: WebSource[] }
  | { type: "token"; text: string }
  | { type: "sources"; sources: SourceChunk[]; web_sources: WebSource[] }
  | {
      type: "message_persisted";
      conversation_id: string;
      assistant_message_id: string;
    }
  | { type: "gap_analysis"; missing_topic: string; related_topics_present: string[]; suggested_document_types: string[]; related_document_ids: string[] }
  | { type: "memory_suggestion"; should_suggest: boolean; reason: string; preview_count: number }
  | { type: "error"; message: string }
  | { type: "done" };

export interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  message_index: number;
  retrieved_chunk_ids: string[] | null;
  cited_chunk_ids: string[] | null;
  model_used: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  low_confidence: boolean;
  web_search_used: boolean;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string | null;
  user_id: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
}

// ---------------------------------------------------------------------------
// Document types
// ---------------------------------------------------------------------------

export interface DocumentListItem {
  id: string;
  filename: string;
  status: DocumentStatus;
  file_category: FileCategory;
  detected_language: string | null;
  size_bytes: number;
  source_type: string;
  source_conversation_id: string | null;
  created_at: string;
}

export interface DocumentDetail {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  blob_path: string;
  detected_language: string | null;
  file_category: FileCategory;
  status: DocumentStatus;
  error_message: string | null;
  uploaded_by: string;
  scope: string;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentContent {
  document_id: string;
  content: string;
  detected_language: string | null;
}

export interface Chunk {
  id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  token_count: number;
  embedding_model: string | null;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface UploadResponse {
  document_id: string;
  status: string;
}

// ---------------------------------------------------------------------------
// Health types
// ---------------------------------------------------------------------------

export interface HealthStatus {
  status: string;
  database: string;
  llm_provider: string;
  embedding_provider: string;
  web_search_provider?: string;
  vector_index?: string;
}

// ---------------------------------------------------------------------------
// Local message type (frontend-only, not from API)
// ---------------------------------------------------------------------------

export interface LocalMessage {
  localId: string;
  serverId?: string;
  role: "user" | "assistant";
  content: string;
  isStreaming: boolean;
  isLowConfidence: boolean;
  webSearchUsed: boolean;
  webSearchPending: boolean;
  webSearchResultCount: number;
  sources: SourceChunk[];
  webSources: WebSource[];
  retrievedChunkIds: string[];
  modelUsed?: string;
  createdAt: string;
  gapAnalysis?: GapAnalysis;
}
