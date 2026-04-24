"use client";

import { useCallback, useRef, useState } from "react";
import { Upload } from "lucide-react";
import { uploadDocument } from "@/lib/api/documents";
import { cn } from "@/lib/utils";
import type { UploadItem } from "./UploadProgress";
import type { DocumentListItem } from "@/lib/api/types";

interface DocumentUploadProps {
  onUploaded: (item: UploadItem, doc: DocumentListItem) => void;
}

export function DocumentUpload({ onUploaded }: DocumentUploadProps) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      const arr = Array.from(files);
      if (arr.length === 0) return;
      setUploading(true);
      await Promise.all(
        arr.map(async (file) => {
          try {
            const resp = await uploadDocument(file);
            const pendingDoc: DocumentListItem = {
              id: resp.document_id,
              filename: file.name,
              status: "pending",
              file_category: "document",
              detected_language: null,
              size_bytes: file.size,
              created_at: new Date().toISOString(),
            };
            const uploadItem: UploadItem = {
              documentId: resp.document_id,
              filename: file.name,
              status: "pending",
            };
            onUploaded(uploadItem, pendingDoc);
          } catch (err) {
            console.error(`Upload failed for ${file.name}:`, err);
          }
        })
      );
      setUploading(false);
    },
    [onUploaded]
  );

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    setDragging(true);
  }

  function handleDragLeave() {
    setDragging(false);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files?.length) {
      handleFiles(e.target.files);
      e.target.value = "";
    }
  }

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed py-10 transition-colors",
        dragging
          ? "border-blue-500 bg-blue-950/20"
          : "border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900/50",
        uploading && "pointer-events-none opacity-60"
      )}
    >
      <Upload className="h-6 w-6 text-zinc-500" />
      <div className="text-center">
        <p className="text-sm text-zinc-300">
          Drop files here or <span className="text-blue-400">browse</span>
        </p>
        <p className="text-xs text-zinc-600 mt-1">
          PDF, DOCX, Markdown, Python, TypeScript, Go, and more
        </p>
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple
        className="hidden"
        onChange={handleInputChange}
      />
    </div>
  );
}
