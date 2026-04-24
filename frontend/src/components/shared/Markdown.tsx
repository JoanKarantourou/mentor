"use client";

import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import "highlight.js/styles/github-dark.css";
import { cn } from "@/lib/utils";

interface MarkdownProps {
  content: string;
  className?: string;
}

export function Markdown({ content, className }: MarkdownProps) {
  return (
    <div className={cn("prose-mentor", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          pre({ children }) {
            return (
              <pre className="not-prose overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-900 p-4 my-3 text-sm font-mono">
                {children}
              </pre>
            );
          },
          code({ className: cls, children, ...props }) {
            const isBlock = cls?.includes("language-");
            if (!isBlock) {
              return (
                <code
                  className="rounded bg-zinc-800 px-1.5 py-0.5 text-[0.875em] font-mono text-zinc-200"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return (
              <code className={cls} {...props}>
                {children}
              </code>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
