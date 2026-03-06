"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  ArrowLeft,
  BedDouble,
  Bath,
  Ruler,
  Clock,
  ExternalLink,
  Shield,
  ShieldCheck,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { ListingGrid } from "@/components/listing-grid";
import { PriceChart } from "@/components/price-chart";
import { getListing } from "@/lib/api";
import type { ListingDetail } from "@/lib/types";

interface ListingDetailViewProps {
  id: string;
}

export function ListingDetailView({ id }: ListingDetailViewProps) {
  const [listing, setListing] = useState<ListingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [imgIdx, setImgIdx] = useState(0);

  useEffect(() => {
    getListing(id)
      .then(setListing)
      .catch(() => setListing(null))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <DetailSkeleton />;
  if (!listing) {
    return (
      <div className="py-24 text-center">
        <p className="text-lg font-medium">Listing not found</p>
        <Link href="/listings" className="mt-2 text-sm text-primary underline">
          Back to listings
        </Link>
      </div>
    );
  }

  const images = listing.images.length > 0 ? listing.images : ["/placeholder-listing.svg"];
  const rsIcon = listing.is_rent_stabilized ? ShieldCheck : Shield;
  const RsIcon = rsIcon;

  return (
    <div className="space-y-6">
      {/* Back */}
      <Link href="/listings">
        <Button variant="ghost" size="sm" className="gap-1">
          <ArrowLeft className="size-4" /> Back
        </Button>
      </Link>

      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        {/* Left column */}
        <div className="space-y-6">
          {/* Gallery */}
          <div className="relative aspect-[16/10] overflow-hidden rounded-xl bg-muted">
            <Image
              src={images[imgIdx]}
              alt={listing.address}
              fill
              className="object-cover"
              priority
              sizes="(max-width: 1024px) 100vw, 60vw"
            />
          </div>
          {images.length > 1 && (
            <div className="flex gap-2 overflow-x-auto pb-1">
              {images.map((src, i) => (
                <button
                  key={i}
                  onClick={() => setImgIdx(i)}
                  className={`relative h-16 w-20 shrink-0 overflow-hidden rounded-md border-2 ${
                    i === imgIdx ? "border-primary" : "border-transparent"
                  }`}
                >
                  <Image src={src} alt="" fill className="object-cover" sizes="80px" />
                </button>
              ))}
            </div>
          )}

          {/* Tabs */}
          <Tabs defaultValue="price">
            <TabsList>
              <TabsTrigger value="price">Price History</TabsTrigger>
              <TabsTrigger value="comps">Comparables</TabsTrigger>
              <TabsTrigger value="permits">Permits</TabsTrigger>
            </TabsList>
            <TabsContent value="price" className="pt-4">
              <PriceChart data={listing.price_history} />
            </TabsContent>
            <TabsContent value="comps" className="pt-4">
              {listing.similar_listings.length > 0 ? (
                <ListingGrid listings={listing.similar_listings} />
              ) : (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No comparable listings found
                </p>
              )}
            </TabsContent>
            <TabsContent value="permits" className="pt-4">
              {listing.building_permits.length > 0 ? (
                <div className="space-y-3">
                  {listing.building_permits.map((p) => (
                    <Card key={p.id} className="py-4">
                      <CardContent className="flex items-start justify-between gap-2 py-0">
                        <div>
                          <p className="text-sm font-medium">{p.permit_type}</p>
                          <p className="text-xs text-muted-foreground">
                            {p.description ?? "No description"}
                          </p>
                        </div>
                        <Badge variant="outline" className="shrink-0 text-[10px]">
                          {p.status}
                        </Badge>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No building permits on file
                </p>
              )}
            </TabsContent>
          </Tabs>
        </div>

        {/* Right sidebar */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-2xl">
                ${listing.current_price.toLocaleString()}
                <span className="text-base font-normal text-muted-foreground">
                  /mo
                </span>
              </CardTitle>
              <CardDescription>{listing.address}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Key stats */}
              <div className="flex gap-4 text-sm">
                <span className="flex items-center gap-1">
                  <BedDouble className="size-4" /> {listing.bedrooms} bed
                </span>
                <span className="flex items-center gap-1">
                  <Bath className="size-4" /> {listing.bathrooms} bath
                </span>
                {listing.sqft && (
                  <span className="flex items-center gap-1">
                    <Ruler className="size-4" /> {listing.sqft.toLocaleString()} ft²
                  </span>
                )}
                {listing.dom !== null && (
                  <span className="flex items-center gap-1">
                    <Clock className="size-4" /> {listing.dom}d
                  </span>
                )}
              </div>

              <Separator />

              {/* Scores */}
              <div className="space-y-2">
                {listing.quality_score !== null && (
                  <ScoreRow label="Quality Score" value={listing.quality_score} />
                )}
                {listing.undervalue_score !== null && (
                  <ScoreRow label="Value Score" value={listing.undervalue_score} />
                )}
              </div>

              {/* RS Badge */}
              {listing.rs_probability !== null && (
                <>
                  <Separator />
                  <div className="flex items-center gap-2">
                    <RsIcon className="size-5 text-primary" />
                    <div>
                      <p className="text-sm font-medium">
                        {listing.is_rent_stabilized
                          ? "Rent Stabilized"
                          : `RS Probability: ${Math.round(listing.rs_probability * 100)}%`}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {listing.is_rent_stabilized
                          ? "This building is on the HCR rent-stabilized list"
                          : "Based on building characteristics"}
                      </p>
                    </div>
                  </div>
                </>
              )}

              <Separator />

              {/* Sources */}
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase text-muted-foreground">
                  Sources
                </p>
                {listing.sources.map((src) => (
                  <a
                    key={src.id}
                    href={src.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm text-primary hover:underline"
                  >
                    <ExternalLink className="size-3.5" />
                    {src.source}
                  </a>
                ))}
              </div>

              {/* Amenities */}
              {listing.amenities.length > 0 && (
                <>
                  <Separator />
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase text-muted-foreground">
                      Amenities
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {listing.amenities.map((a) => (
                        <Badge key={a} variant="outline" className="capitalize">
                          {a}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function ScoreRow({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center justify-between text-sm">
      <span>{label}</span>
      <div className="flex items-center gap-2">
        <div className="h-2 w-24 rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="w-8 text-right font-medium">{pct}</span>
      </div>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-20" />
      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <div className="space-y-6">
          <Skeleton className="aspect-[16/10] w-full rounded-xl" />
          <Skeleton className="h-[300px] w-full" />
        </div>
        <div className="space-y-4">
          <Skeleton className="h-[500px] w-full rounded-xl" />
        </div>
      </div>
    </div>
  );
}
