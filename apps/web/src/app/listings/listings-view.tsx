"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { FilterSidebar, parseFilters } from "@/components/filter-sidebar";
import { ListingGrid } from "@/components/listing-grid";
import { Pagination } from "@/components/pagination";
import { getListings } from "@/lib/api";
import type { Listing, PaginatedResponse } from "@/lib/types";

const EMPTY: PaginatedResponse<Listing> = {
  items: [],
  total: 0,
  page: 1,
  page_size: 24,
  pages: 0,
};

function ListingsContent() {
  const searchParams = useSearchParams();
  const [data, setData] = useState<PaginatedResponse<Listing>>(EMPTY);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const filters = parseFilters(searchParams);
      const page = Number(searchParams.get("page") ?? "1");
      const result = await getListings({ ...filters, page, page_size: 24 });
      setData(result);
    } catch {
      setData(EMPTY);
    } finally {
      setLoading(false);
    }
  }, [searchParams]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <>
      <ListingGrid listings={data.items} loading={loading} />
      <Pagination page={data.page} pages={data.pages} total={data.total} />
    </>
  );
}

export function ListingsView() {
  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <Suspense>
        <FilterSidebar />
      </Suspense>
      <div className="min-w-0 flex-1">
        <Suspense>
          <ListingsContent />
        </Suspense>
      </div>
    </div>
  );
}
