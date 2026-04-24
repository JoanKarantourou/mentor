"use client";

import { useEffect, useState } from "react";
import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from "@/components/ui/toast";

type ToastData = {
  id: string;
  title: string;
  description?: string;
  variant?: "default" | "error";
};

// Simple global toast store
let listeners: Array<(toasts: ToastData[]) => void> = [];
let toasts: ToastData[] = [];

function emitChange() {
  listeners.forEach((l) => l([...toasts]));
}

export const toast = {
  show(title: string, description?: string, variant?: "default" | "error") {
    const id = Math.random().toString(36).slice(2);
    toasts = [...toasts, { id, title, description, variant }];
    emitChange();
    setTimeout(() => {
      toasts = toasts.filter((t) => t.id !== id);
      emitChange();
    }, 5000);
  },
  error(title: string, description?: string) {
    this.show(title, description, "error");
  },
};

export function Toaster() {
  const [items, setItems] = useState<ToastData[]>([]);

  useEffect(() => {
    listeners.push(setItems);
    return () => {
      listeners = listeners.filter((l) => l !== setItems);
    };
  }, []);

  return (
    <ToastProvider>
      {items.map((item) => (
        <Toast key={item.id} variant={item.variant} open>
          <div className="flex-1">
            <ToastTitle>{item.title}</ToastTitle>
            {item.description && (
              <ToastDescription>{item.description}</ToastDescription>
            )}
          </div>
          <ToastClose />
        </Toast>
      ))}
      <ToastViewport />
    </ToastProvider>
  );
}
