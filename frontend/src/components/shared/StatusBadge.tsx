import { Badge } from "@/components/ui/badge";
import type { DocumentStatus } from "@/lib/api/types";

const CONFIG: Record<
  DocumentStatus,
  { label: string; variant: "default" | "blue" | "green" | "yellow" | "red" | "purple" }
> = {
  pending: { label: "Pending", variant: "default" },
  processing: { label: "Processing", variant: "blue" },
  ready: { label: "Ready", variant: "blue" },
  chunking: { label: "Chunking", variant: "purple" },
  embedding: { label: "Embedding", variant: "purple" },
  indexed: { label: "Indexed", variant: "green" },
  failed: { label: "Failed", variant: "red" },
};

interface StatusBadgeProps {
  status: DocumentStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const { label, variant } = CONFIG[status] ?? { label: status, variant: "default" };
  return (
    <Badge variant={variant} className={className}>
      {label}
    </Badge>
  );
}
