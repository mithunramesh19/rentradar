"use client";

import { useCallback, useEffect, useRef } from "react";

import { createSSEConnection, getAccessToken } from "@/lib/api";
import type { Notification } from "@/lib/types";

interface UseSSEOptions {
  onNotification: (notification: Notification) => void;
  enabled?: boolean;
}

export function useSSE({ onNotification, enabled = true }: UseSSEOptions) {
  const esRef = useRef<EventSource | null>(null);
  const cbRef = useRef(onNotification);
  cbRef.current = onNotification;

  const connect = useCallback(() => {
    // cleanup existing
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    if (!enabled || !getAccessToken()) return;

    const es = createSSEConnection();
    if (!es) return;

    es.addEventListener("notification", (event) => {
      try {
        const data = JSON.parse(event.data) as Notification;
        cbRef.current(data);
      } catch {
        // invalid payload
      }
    });

    es.onerror = () => {
      es.close();
      esRef.current = null;
      // reconnect after 5s
      setTimeout(connect, 5000);
    };

    esRef.current = es;
  }, [enabled]);

  useEffect(() => {
    connect();
    return () => {
      esRef.current?.close();
      esRef.current = null;
    };
  }, [connect]);
}
