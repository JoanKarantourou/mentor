"use client";

import { useEffect, useRef, useState } from "react";
import { getDocument } from "@/lib/api/documents";
import type { DocumentListItem, DocumentStatus } from "@/lib/api/types";

const TERMINAL: DocumentStatus[] = ["indexed", "failed"];

export function useDocumentStatus(
  documentId: string,
  onUpdate?: (doc: DocumentListItem) => void
) {
  const [status, setStatus] = useState<DocumentStatus>("pending");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let stopped = false;

    async function poll() {
      try {
        const doc = await getDocument(documentId);
        if (stopped) return;
        const s = doc.status as DocumentStatus;
        setStatus(s);
        onUpdate?.({
          id: doc.id,
          filename: doc.filename,
          status: s,
          file_category: doc.file_category,
          detected_language: doc.detected_language,
          size_bytes: doc.size_bytes,
          created_at: doc.created_at,
        });
        if (TERMINAL.includes(s)) {
          clearInterval(intervalRef.current!);
        }
      } catch {
        // ignore transient errors; stop on next interval
      }
    }

    poll();
    intervalRef.current = setInterval(poll, 2000);

    return () => {
      stopped = true;
      clearInterval(intervalRef.current!);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId]);

  return { status };
}
