"use client";

import { toast } from "sonner";

import { useSSE } from "@/hooks/use-sse";
import { useAuth } from "@/lib/auth-context";
import type { Notification } from "@/lib/types";

const EVENT_EMOJI: Record<string, string> = {
  listed: "🏠",
  price_drop: "📉",
  price_increase: "📈",
  relisted: "🔄",
  removed: "❌",
};

export function NotificationToastProvider() {
  const { user } = useAuth();

  useSSE({
    enabled: !!user,
    onNotification: (notification: Notification) => {
      const emoji = EVENT_EMOJI[notification.event_type] ?? "🔔";
      toast(`${emoji} ${notification.title}`, {
        description: notification.body,
        action: notification.listing_id
          ? {
              label: "View",
              onClick: () => {
                window.location.href = `/listings/${notification.listing_id}`;
              },
            }
          : undefined,
      });
    },
  });

  return null;
}
