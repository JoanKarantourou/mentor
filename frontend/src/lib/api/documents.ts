import { BACKEND_URL, apiFetch } from "./client";
import type {
  Chunk,
  DocumentContent,
  DocumentDetail,
  DocumentListItem,
  UploadResponse,
} from "./types";

export function listDocuments(): Promise<DocumentListItem[]> {
  return apiFetch<DocumentListItem[]>("/documents");
}

export function getDocument(id: string): Promise<DocumentDetail> {
  return apiFetch<DocumentDetail>(`/documents/${id}`);
}

export function getDocumentContent(id: string): Promise<DocumentContent> {
  return apiFetch<DocumentContent>(`/documents/${id}/content`);
}

export function getDocumentChunks(id: string): Promise<Chunk[]> {
  return apiFetch<Chunk[]>(`/documents/${id}/chunks`);
}

export function deleteDocument(id: string): Promise<void> {
  return apiFetch<void>(`/documents/${id}`, { method: "DELETE" });
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${BACKEND_URL}/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Upload failed (${res.status}): ${text}`);
  }

  return res.json() as Promise<UploadResponse>;
}
