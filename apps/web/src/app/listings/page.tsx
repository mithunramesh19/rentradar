import type { Metadata } from "next";

import { ListingsView } from "./listings-view";

export const metadata: Metadata = {
  title: "Listings | RentRadar",
  description: "Browse NYC rental listings with real-time price tracking",
};

export default function ListingsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold">NYC Rental Listings</h1>
      <ListingsView />
    </div>
  );
}
