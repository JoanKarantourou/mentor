"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DocumentDetail } from "@/components/documents/DocumentDetail";
import { Skeleton } from "@/components/ui/skeleton";
import { getDocument, deleteDocument } from "@/lib/api/documents";
import { toast } from "@/components/ui/toaster";
import type { DocumentDetail as DocDetail } from "@/lib/api/types";

export default function DocumentDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const { id } = params;
  const router = useRouter();
  const [doc, setDoc] = useState<DocDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    getDocument(id)
      .then(setDoc)
      .catch(() => toast.error("Failed to load document"))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleDelete() {
    if (!confirmDelete) {
      setConfirmDelete(true);
      setTimeout(() => setConfirmDelete(false), 4000);
      return;
    }
    setDeleting(true);
    try {
      await deleteDocument(id);
      router.push("/documents");
    } catch {
      toast.error("Failed to delete document");
      setDeleting(false);
    }
  }

  return (
    <div className="flex h-screen flex-col bg-zinc-950">
      <header className="border-b border-zinc-800 px-6 py-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0">
          <Link
            href="/documents"
            className="text-zinc-500 hover:text-zinc-300 transition-colors flex-shrink-0"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          {loading ? (
            <Skeleton className="h-4 w-48" />
          ) : (
            <h1 className="text-sm font-mono font-semibold text-zinc-100 truncate">
              {doc?.filename ?? "Document"}
            </h1>
          )}
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={handleDelete}
          disabled={deleting}
          className={confirmDelete ? "text-red-400 hover:text-red-300" : ""}
        >
          <Trash2 className="h-4 w-4 mr-1.5" />
          {confirmDelete ? "Confirm delete" : "Delete"}
        </Button>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6 max-w-3xl mx-auto w-full">
        {loading ? (
          <div className="space-y-3">
            {[...Array(8)].map((_, i) => (
              <Skeleton key={i} className="h-4 w-full" />
            ))}
          </div>
        ) : doc ? (
          <DocumentDetail document={doc} />
        ) : (
          <p className="text-sm text-zinc-600">Document not found.</p>
        )}
      </div>
    </div>
  );
}
