"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { DocumentUpload } from "@/components/documents/DocumentUpload";
import { DocumentList } from "@/components/documents/DocumentList";
import { UploadProgress, type UploadItem } from "@/components/documents/UploadProgress";
import { useDocuments } from "@/hooks/useDocuments";
import { toast } from "@/components/ui/toaster";
import type { DocumentListItem } from "@/lib/api/types";

export default function DocumentsPage() {
  const { documents, loading, remove, upsert } = useDocuments();
  const [uploads, setUploads] = useState<UploadItem[]>([]);

  const handleUploaded = useCallback(
    (item: UploadItem, doc: DocumentListItem) => {
      setUploads((prev) => [...prev, item]);
      upsert(doc);
    },
    [upsert]
  );

  const handleDocUpdate = useCallback(
    (doc: DocumentListItem) => {
      upsert(doc);
      setUploads((prev) =>
        prev.map((u) =>
          u.documentId === doc.id ? { ...u, status: doc.status } : u
        )
      );
    },
    [upsert]
  );

  async function handleDelete(id: string) {
    try {
      await remove(id);
    } catch {
      toast.error("Failed to delete document");
    }
  }

  return (
    <div className="flex h-screen flex-col bg-zinc-950">
      <header className="border-b border-zinc-800 px-6 py-4 flex items-center gap-4">
        <Link
          href="/chat"
          className="text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <h1 className="text-sm font-semibold text-zinc-100">Documents</h1>
        <span className="text-xs text-zinc-600">
          {documents.length} indexed
        </span>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6 max-w-3xl mx-auto w-full">
        <div className="space-y-6">
          <DocumentUpload onUploaded={handleUploaded} />

          {uploads.length > 0 && (
            <UploadProgress uploads={uploads} onUpdate={handleDocUpdate} />
          )}

          <section>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-3">
              Corpus
            </h2>
            <DocumentList
              documents={documents}
              loading={loading}
              onDelete={handleDelete}
            />
          </section>
        </div>
      </div>
    </div>
  );
}
