import type { Metadata } from "next";

import { SearchesView } from "./searches-view";

export const metadata: Metadata = {
  title: "Saved Searches | RentRadar",
  description: "Manage your saved search alerts",
};

export default function SearchesPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <SearchesView />
    </div>
  );
}
