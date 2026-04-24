"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FileText, MessageSquare, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ConversationList } from "@/components/chat/ConversationList";
import { useConversations } from "@/hooks/useConversations";
import { useHealth } from "@/hooks/useHealth";
import { cn } from "@/lib/utils";
import { useEffect } from "react";
import { toast } from "@/components/ui/toaster";

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { conversations, loading, remove, refresh } = useConversations();
  const { state: healthState, health } = useHealth();

  // Refresh conversation list when navigating back to sidebar
  useEffect(() => {
    refresh();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  async function handleDelete(id: string) {
    try {
      await remove(id);
      if (pathname === `/chat/${id}`) {
        router.push("/chat");
      }
    } catch {
      toast.error("Failed to delete conversation");
    }
  }

  const healthDot = {
    ok: "bg-emerald-500",
    degraded: "bg-amber-500",
    unreachable: "bg-red-500",
  }[healthState];

  const healthTooltip = {
    ok: "All systems operational",
    degraded: health
      ? Object.entries(health)
          .filter(([k, v]) => k !== "status" && v !== "ok" && v !== "stub")
          .map(([k, v]) => `${k}: ${v}`)
          .join(", ") || "Degraded"
      : "Degraded",
    unreachable: "Backend unreachable",
  }[healthState];

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="flex w-64 flex-col border-r border-zinc-800 bg-zinc-900">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <Link
            href="/chat"
            className="text-sm font-semibold text-zinc-100 hover:text-white"
          >
            mentor
          </Link>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push("/chat")}
            title="New conversation"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>

        {/* Conversation list */}
        <ScrollArea className="flex-1 py-2">
          <ConversationList
            conversations={conversations}
            loading={loading}
            onDelete={handleDelete}
          />
        </ScrollArea>

        {/* Footer nav */}
        <div className="border-t border-zinc-800 px-2 py-2 space-y-0.5">
          <Link
            href="/documents"
            className={cn(
              "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
              pathname.startsWith("/documents")
                ? "bg-zinc-800 text-zinc-100"
                : "text-zinc-500 hover:bg-zinc-800/60 hover:text-zinc-300"
            )}
          >
            <FileText className="h-4 w-4" />
            Documents
          </Link>

          {/* Health indicator */}
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center gap-2.5 px-3 py-2 text-xs text-zinc-600 cursor-default">
                  <span
                    className={cn("h-2 w-2 rounded-full flex-shrink-0", healthDot)}
                  />
                  <span>System {healthState}</span>
                </div>
              </TooltipTrigger>
              <TooltipContent side="right">{healthTooltip}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex flex-1 flex-col overflow-hidden">{children}</main>
    </div>
  );
}
