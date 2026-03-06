import Image from "next/image";
import Link from "next/link";
import {
  BedDouble,
  Bath,
  Ruler,
  Clock,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Listing, ListingSource } from "@/lib/types";
import { cn } from "@/lib/utils";

const SOURCE_LABELS: Record<ListingSource, string> = {
  streeteasy: "SE",
  craigslist: "CL",
  zillow: "ZL",
  rentcom: "RC",
  zumper: "ZM",
};

function PriceChangeBadge({ pct }: { pct: number }) {
  const isDown = pct < 0;
  const Icon = isDown ? TrendingDown : TrendingUp;
  return (
    <Badge
      variant={isDown ? "secondary" : "outline"}
      className={cn(
        "gap-0.5 text-[10px]",
        isDown ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
      )}
    >
      <Icon className="size-3" />
      {Math.abs(pct).toFixed(1)}%
    </Badge>
  );
}

function ScorePill({ label, value }: { label: string; value: number | null }) {
  if (value === null) return null;
  const pct = Math.round(value * 100);
  return (
    <Badge
      variant="outline"
      className="gap-1 text-[10px] font-normal"
    >
      {label} {pct}
    </Badge>
  );
}

interface ListingCardProps {
  listing: Listing;
}

export function ListingCard({ listing }: ListingCardProps) {
  const {
    id,
    address,
    current_price,
    price_change_pct,
    bedrooms,
    bathrooms,
    sqft,
    quality_score,
    rs_probability,
    undervalue_score,
    dom,
    images,
    sources,
  } = listing;

  const imgSrc = images[0] ?? "/placeholder-listing.svg";
  const uniqueSources = [...new Set(sources.map((s) => s.source))];

  return (
    <Link href={`/listings/${id}`} className="group">
      <Card className="overflow-hidden py-0 transition-shadow hover:shadow-md">
        {/* Image */}
        <div className="relative aspect-[4/3] w-full overflow-hidden bg-muted">
          <Image
            src={imgSrc}
            alt={address}
            fill
            className="object-cover transition-transform group-hover:scale-105"
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
          />
          {/* Source icons */}
          <div className="absolute left-2 top-2 flex gap-1">
            {uniqueSources.map((src) => (
              <Badge key={src} variant="secondary" className="text-[10px] px-1.5">
                {SOURCE_LABELS[src]}
              </Badge>
            ))}
          </div>
          {/* DOM badge */}
          {dom !== null && (
            <Badge
              variant="secondary"
              className="absolute right-2 top-2 gap-0.5 text-[10px]"
            >
              <Clock className="size-3" />
              {dom}d
            </Badge>
          )}
        </div>

        <CardContent className="space-y-2 p-4">
          {/* Price row */}
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-bold">
              ${current_price.toLocaleString()}
            </span>
            {price_change_pct !== null && price_change_pct !== 0 && (
              <PriceChangeBadge pct={price_change_pct} />
            )}
          </div>

          {/* Address */}
          <p className="truncate text-sm text-muted-foreground">{address}</p>

          {/* Beds / Baths / Sqft */}
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <BedDouble className="size-3.5" /> {bedrooms}
            </span>
            <span className="flex items-center gap-1">
              <Bath className="size-3.5" /> {bathrooms}
            </span>
            {sqft && (
              <span className="flex items-center gap-1">
                <Ruler className="size-3.5" /> {sqft.toLocaleString()} ft²
              </span>
            )}
          </div>

          {/* Score pills */}
          <div className="flex flex-wrap gap-1">
            <ScorePill label="Quality" value={quality_score} />
            <ScorePill label="RS" value={rs_probability} />
            <ScorePill label="Value" value={undervalue_score} />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
