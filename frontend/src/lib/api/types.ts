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
  | "failed";

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

export interface ChatRequest {
  message: string;
  conversation_id: string | null;
  model_tier: ModelTier;
}

export type ChatEvent =
  | {
      type: "retrieval";
      chunk_ids: string[];
      top_similarity: number;
      avg_similarity: number;
    }
  | { type: "confidence"; sufficient: boolean; reason: string }
  | { type: "token"; text: string }
  | { type: "sources"; sources: SourceChunk[] }
  | {
      type: "message_persisted";
      conversation_id: string;
      assistant_message_id: string;
    }
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
  sources: SourceChunk[];
  retrievedChunkIds: string[];
  modelUsed?: string;
  createdAt: string;
}
