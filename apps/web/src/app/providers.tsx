"use client";

import { AuthProvider } from "@/lib/auth-context";
import { NotificationToastProvider } from "@/components/notification-toast-provider";
import { Toaster } from "@/components/ui/sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      {children}
      <NotificationToastProvider />
      <Toaster position="top-right" />
    </AuthProvider>
  );
}
