"use client";

import { useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Borough, SortField, type ListingFilters } from "@/lib/types";
import { cn } from "@/lib/utils";

const BOROUGHS = Object.values(Borough);
const BEDROOM_OPTIONS = [0, 1, 2, 3, 4] as const;
const AMENITIES = [
  "doorman",
  "elevator",
  "laundry",
  "dishwasher",
  "parking",
  "gym",
  "pool",
  "roof",
  "pets",
] as const;

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "created_at:desc", label: "Newest" },
  { value: "price:asc", label: "Price: Low → High" },
  { value: "price:desc", label: "Price: High → Low" },
  { value: "quality_score:desc", label: "Quality Score" },
  { value: "undervalue_score:desc", label: "Best Value" },
  { value: "dom:asc", label: "Days on Market" },
];

const PRICE_MIN = 500;
const PRICE_MAX = 10000;
const PRICE_STEP = 100;

/** Parse current filters from URL search params */
export function parseFilters(params: URLSearchParams): ListingFilters {
  const filters: ListingFilters = {};

  const priceMin = params.get("price_min");
  const priceMax = params.get("price_max");
  if (priceMin) filters.price_min = Number(priceMin);
  if (priceMax) filters.price_max = Number(priceMax);

  const beds = params.getAll("bedrooms");
  if (beds.length) filters.bedrooms = beds.map(Number);

  const boroughs = params.getAll("boroughs");
  if (boroughs.length) filters.boroughs = boroughs as Borough[];

  const amenities = params.getAll("amenities");
  if (amenities.length) filters.amenities = amenities;

  const distLat = params.get("distance_lat");
  const distLng = params.get("distance_lng");
  const distMi = params.get("distance_miles");
  if (distLat) filters.distance_lat = Number(distLat);
  if (distLng) filters.distance_lng = Number(distLng);
  if (distMi) filters.distance_miles = Number(distMi);

  const sortBy = params.get("sort_by");
  const sortOrder = params.get("sort_order");
  if (sortBy) filters.sort_by = sortBy as ListingFilters["sort_by"];
  if (sortOrder) filters.sort_order = sortOrder as ListingFilters["sort_order"];

  return filters;
}

export function FilterSidebar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const filters = parseFilters(searchParams);

  const update = useCallback(
    (patch: Partial<ListingFilters>) => {
      const params = new URLSearchParams(searchParams.toString());

      for (const [key, value] of Object.entries(patch)) {
        params.delete(key);
        if (value === undefined || value === null) continue;
        if (Array.isArray(value)) {
          value.forEach((v) => params.append(key, String(v)));
        } else {
          params.set(key, String(value));
        }
      }
      // reset page on filter change
      params.delete("page");
      router.push(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  const clearAll = useCallback(() => {
    router.push("?", { scroll: false });
  }, [router]);

  // Sort value from combined field:order
  const sortValue = filters.sort_by
    ? `${filters.sort_by}:${filters.sort_order ?? "desc"}`
    : "created_at:desc";

  return (
    <aside className="w-full space-y-6 lg:w-64 lg:shrink-0">
      {/* Price Range */}
      <fieldset className="space-y-3">
        <Label className="text-sm font-semibold">Price Range</Label>
        <Slider
          min={PRICE_MIN}
          max={PRICE_MAX}
          step={PRICE_STEP}
          value={[
            filters.price_min ?? PRICE_MIN,
            filters.price_max ?? PRICE_MAX,
          ]}
          onValueCommit={([min, max]) =>
            update({
              price_min: min === PRICE_MIN ? undefined : min,
              price_max: max === PRICE_MAX ? undefined : max,
            })
          }
        />
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>${(filters.price_min ?? PRICE_MIN).toLocaleString()}</span>
          <span className="flex-1 border-t" />
          <span>${(filters.price_max ?? PRICE_MAX).toLocaleString()}</span>
        </div>
      </fieldset>

      {/* Bedrooms */}
      <fieldset className="space-y-3">
        <Label className="text-sm font-semibold">Bedrooms</Label>
        <div className="flex flex-wrap gap-1.5">
          {BEDROOM_OPTIONS.map((n) => {
            const active = filters.bedrooms?.includes(n);
            return (
              <Badge
                key={n}
                variant={active ? "default" : "outline"}
                className={cn(
                  "cursor-pointer select-none px-3 py-1",
                  active && "ring-1 ring-primary",
                )}
                onClick={() => {
                  const current = filters.bedrooms ?? [];
                  const next = active
                    ? current.filter((b) => b !== n)
                    : [...current, n];
                  update({ bedrooms: next.length ? next : undefined });
                }}
              >
                {n === 0 ? "Studio" : `${n}BR`}
              </Badge>
            );
          })}
        </div>
      </fieldset>

      {/* Boroughs */}
      <fieldset className="space-y-3">
        <Label className="text-sm font-semibold">Borough</Label>
        <div className="space-y-2">
          {BOROUGHS.map((borough) => {
            const checked = filters.boroughs?.includes(borough) ?? false;
            return (
              <div key={borough} className="flex items-center gap-2">
                <Checkbox
                  id={`borough-${borough}`}
                  checked={checked}
                  onCheckedChange={(c) => {
                    const current = filters.boroughs ?? [];
                    const next = c
                      ? [...current, borough]
                      : current.filter((b) => b !== borough);
                    update({ boroughs: next.length ? next : undefined });
                  }}
                />
                <Label
                  htmlFor={`borough-${borough}`}
                  className="text-sm font-normal"
                >
                  {borough}
                </Label>
              </div>
            );
          })}
        </div>
      </fieldset>

      {/* Distance */}
      <fieldset className="space-y-3">
        <Label className="text-sm font-semibold">Max Distance (miles)</Label>
        <Input
          type="number"
          min={0}
          step={0.5}
          placeholder="e.g. 2"
          value={filters.distance_miles ?? ""}
          onChange={(e) =>
            update({
              distance_miles: e.target.value
                ? Number(e.target.value)
                : undefined,
            })
          }
        />
      </fieldset>

      {/* Amenities */}
      <fieldset className="space-y-3">
        <Label className="text-sm font-semibold">Amenities</Label>
        <div className="flex flex-wrap gap-1.5">
          {AMENITIES.map((a) => {
            const active = filters.amenities?.includes(a);
            return (
              <Badge
                key={a}
                variant={active ? "default" : "outline"}
                className="cursor-pointer select-none capitalize"
                onClick={() => {
                  const current = filters.amenities ?? [];
                  const next = active
                    ? current.filter((x) => x !== a)
                    : [...current, a];
                  update({ amenities: next.length ? next : undefined });
                }}
              >
                {a}
              </Badge>
            );
          })}
        </div>
      </fieldset>

      {/* Sort */}
      <fieldset className="space-y-3">
        <Label className="text-sm font-semibold">Sort By</Label>
        <Select
          value={sortValue}
          onValueChange={(v) => {
            const [field, order] = v.split(":");
            update({
              sort_by: field as ListingFilters["sort_by"],
              sort_order: order as ListingFilters["sort_order"],
            });
          }}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </fieldset>

      {/* Clear */}
      <Button variant="outline" className="w-full" onClick={clearAll}>
        Clear All Filters
      </Button>
    </aside>
  );
}
