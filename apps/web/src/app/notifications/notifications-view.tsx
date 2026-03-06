"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Bell,
  CheckCheck,
  CircleDot,
  TrendingDown,
  TrendingUp,
  PlusCircle,
  RotateCcw,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "@/lib/api";
import type { EventType, Notification, PaginatedResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

const EVENT_CONFIG: Record<
  EventType,
  { icon: typeof Bell; label: string; color: string }
> = {
  listed: {
    icon: PlusCircle,
    label: "New Listing",
    color: "text-blue-600 dark:text-blue-400",
  },
  price_drop: {
    icon: TrendingDown,
    label: "Price Drop",
    color: "text-green-600 dark:text-green-400",
  },
  price_increase: {
    icon: TrendingUp,
    label: "Price Increase",
    color: "text-red-600 dark:text-red-400",
  },
  relisted: {
    icon: RotateCcw,
    label: "Relisted",
    color: "text-purple-600 dark:text-purple-400",
  },
  removed: {
    icon: XCircle,
    label: "Removed",
    color: "text-muted-foreground",
  },
};

const EMPTY: PaginatedResponse<Notification> = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
  pages: 0,
};

export function NotificationsView() {
  const [data, setData] = useState<PaginatedResponse<Notification>>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getNotifications(page);
      setData(res);
    } catch {
      setData(EMPTY);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleMarkRead = async (id: string) => {
    await markNotificationRead(id);
    setData((d) => ({
      ...d,
      items: d.items.map((n) =>
        n.id === id ? { ...n, read: true, read_at: new Date().toISOString() } : n,
      ),
    }));
  };

  const handleMarkAll = async () => {
    await markAllNotificationsRead();
    setData((d) => ({
      ...d,
      items: d.items.map((n) => ({
        ...n,
        read: true,
        read_at: n.read_at ?? new Date().toISOString(),
      })),
    }));
  };

  const unreadCount = data.items.filter((n) => !n.read).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">Notifications</h1>
          {unreadCount > 0 && (
            <Badge variant="default">{unreadCount} unread</Badge>
          )}
        </div>
        {unreadCount > 0 && (
          <Button
            variant="outline"
            size="sm"
            className="gap-1.5"
            onClick={handleMarkAll}
          >
            <CheckCheck className="size-4" /> Mark All Read
          </Button>
        )}
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
      ) : data.items.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-24 text-muted-foreground">
          <Bell className="size-10" />
          <p className="text-lg font-medium">No notifications yet</p>
          <p className="text-sm">
            Save a search to start receiving alerts
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {data.items.map((n) => (
            <NotificationRow
              key={n.id}
              notification={n}
              onMarkRead={handleMarkRead}
            />
          ))}
        </div>
      )}

      {/* Simple pagination */}
      {data.pages > 1 && (
        <div className="flex justify-center gap-2 pt-4">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <span className="flex items-center px-3 text-sm text-muted-foreground">
            {page} / {data.pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= data.pages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}

function NotificationRow({
  notification,
  onMarkRead,
}: {
  notification: Notification;
  onMarkRead: (id: string) => void;
}) {
  const config = EVENT_CONFIG[notification.event_type];
  const Icon = config.icon;
  const listing = notification.listing;
  const timeAgo = formatTimeAgo(notification.sent_at);

  return (
    <Card
      className={cn(
        "py-3 transition-colors",
        !notification.read && "border-primary/30 bg-primary/5",
      )}
    >
      <CardContent className="flex items-start gap-3 py-0 px-4">
        {/* Icon */}
        <div className={cn("mt-0.5 shrink-0", config.color)}>
          <Icon className="size-5" />
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-sm font-medium">{notification.title}</p>
              <p className="text-xs text-muted-foreground">
                {notification.body}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <span className="text-xs text-muted-foreground">{timeAgo}</span>
              {!notification.read && (
                <button
                  onClick={() => onMarkRead(notification.id)}
                  className="text-muted-foreground hover:text-foreground"
                  title="Mark as read"
                >
                  <CircleDot className="size-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Listing preview */}
          {listing && (
            <Link
              href={`/listings/${listing.id}`}
              className="mt-2 flex items-center gap-3 rounded-lg border bg-muted/50 p-2 transition-colors hover:bg-muted"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  ${listing.current_price.toLocaleString()}/mo
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {listing.address}
                </p>
              </div>
              <Badge variant="outline" className="shrink-0 text-[10px]">
                {listing.bedrooms}BR · {listing.bathrooms}BA
              </Badge>
            </Link>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function formatTimeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}
