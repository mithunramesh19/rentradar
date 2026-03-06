"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Search, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { CreateSearchDialog } from "@/components/create-search-dialog";
import { deleteSavedSearch, getSavedSearches } from "@/lib/api";
import type { SavedSearch } from "@/lib/types";

export function SearchesView() {
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchSearches = useCallback(async () => {
    try {
      const data = await getSavedSearches();
      setSearches(data);
    } catch {
      // noop
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSearches();
  }, [fetchSearches]);

  const handleDelete = async (id: string) => {
    await deleteSavedSearch(id);
    setSearches((s) => s.filter((x) => x.id !== id));
  };

  if (loading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-40 rounded-xl" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Saved Searches</h1>
        <CreateSearchDialog
          onCreated={(s) => setSearches((prev) => [s, ...prev])}
        >
          <Button className="gap-1.5">
            <Plus className="size-4" /> New Search
          </Button>
        </CreateSearchDialog>
      </div>

      {searches.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-24 text-muted-foreground">
          <Search className="size-10" />
          <p className="text-lg font-medium">No saved searches yet</p>
          <p className="text-sm">Create one to get notified about new listings</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {searches.map((s) => (
            <SearchCard key={s.id} search={s} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  );
}

function SearchCard({
  search,
  onDelete,
}: {
  search: SavedSearch;
  onDelete: (id: string) => void;
}) {
  const { filters } = search;
  const tags: string[] = [];
  if (filters.price_min || filters.price_max) {
    const min = filters.price_min ? `$${filters.price_min.toLocaleString()}` : "$0";
    const max = filters.price_max ? `$${filters.price_max.toLocaleString()}` : "∞";
    tags.push(`${min}–${max}`);
  }
  if (filters.bedrooms?.length) {
    tags.push(filters.bedrooms.map((b) => (b === 0 ? "Studio" : `${b}BR`)).join(", "));
  }
  if (filters.boroughs?.length) {
    tags.push(filters.boroughs.join(", "));
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <CardTitle className="text-base">{search.name}</CardTitle>
          <Button
            variant="ghost"
            size="icon"
            className="size-7 text-muted-foreground hover:text-destructive"
            onClick={() => onDelete(search.id)}
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
        <CardDescription>
          {search.notify
            ? `Notifying via ${search.channels.join(", ")}`
            : "Notifications off"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-1">
          {tags.map((t) => (
            <Badge key={t} variant="outline" className="text-xs">
              {t}
            </Badge>
          ))}
          {tags.length === 0 && (
            <span className="text-xs text-muted-foreground">All listings</span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
