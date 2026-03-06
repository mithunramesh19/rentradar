"use client";

import { useCallback, useState } from "react";

import { requestPushPermission } from "@/lib/firebase";
import { client } from "@/lib/api";

export function usePushNotifications() {
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enable = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const fcmToken = await requestPushPermission();
      if (!fcmToken) {
        setError("Push notifications not supported or permission denied");
        return;
      }
      // Register token with backend
      await client.request("/auth/push-token", {
        method: "POST",
        body: JSON.stringify({ token: fcmToken }),
      });
      setToken(fcmToken);
    } catch {
      setError("Failed to enable push notifications");
    } finally {
      setLoading(false);
    }
  }, []);

  return { token, loading, error, enable };
}
