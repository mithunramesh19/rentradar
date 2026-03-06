import type { Metadata } from "next";

import { ListingDetailView } from "./listing-detail-view";

export const metadata: Metadata = {
  title: "Listing Detail | RentRadar",
  description: "View listing details, price history, and comparables",
};

export default async function ListingDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="container mx-auto px-4 py-8">
      <ListingDetailView id={id} />
    </div>
  );
}
