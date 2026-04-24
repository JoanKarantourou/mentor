import { Skeleton } from "@/components/ui/skeleton";
import { DocumentListItem } from "./DocumentListItem";
import type { DocumentListItem as DocItem } from "@/lib/api/types";

interface DocumentListProps {
  documents: DocItem[];
  loading: boolean;
  onDelete: (id: string) => void;
}

export function DocumentList({
  documents,
  loading,
  onDelete,
}: DocumentListProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-14 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <p className="text-sm text-zinc-600 text-center py-8">
        No documents indexed yet. Upload some above.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {documents.map((doc) => (
        <DocumentListItem key={doc.id} doc={doc} onDelete={onDelete} />
      ))}
    </div>
  );
}
