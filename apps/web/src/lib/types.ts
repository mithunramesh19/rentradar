// Enums — mirror packages/rentradar_common/constants.py

export const Borough = {
  MANHATTAN: "Manhattan",
  BROOKLYN: "Brooklyn",
  QUEENS: "Queens",
  BRONX: "Bronx",
  STATEN_ISLAND: "Staten Island",
} as const;
export type Borough = (typeof Borough)[keyof typeof Borough];

export const ListingSource = {
  STREETEASY: "streeteasy",
  CRAIGSLIST: "craigslist",
  ZILLOW: "zillow",
  RENTCOM: "rentcom",
  ZUMPER: "zumper",
} as const;
export type ListingSource = (typeof ListingSource)[keyof typeof ListingSource];

export const ListingStatus = {
  ACTIVE: "active",
  REMOVED: "removed",
  RENTED: "rented",
} as const;
export type ListingStatus = (typeof ListingStatus)[keyof typeof ListingStatus];

export const EventType = {
  LISTED: "listed",
  PRICE_DROP: "price_drop",
  PRICE_INCREASE: "price_increase",
  RELISTED: "relisted",
  REMOVED: "removed",
} as const;
export type EventType = (typeof EventType)[keyof typeof EventType];

export const NotificationChannel = {
  PUSH: "push",
  EMAIL: "email",
  SSE: "sse",
} as const;
export type NotificationChannel =
  (typeof NotificationChannel)[keyof typeof NotificationChannel];

// ---------- Core data types ----------

export interface PriceHistory {
  id: string;
  listing_id: string;
  source: ListingSource;
  price: number;
  recorded_at: string; // ISO datetime
}

export interface ListingSourceRecord {
  id: string;
  listing_id: string;
  source: ListingSource;
  source_url: string;
  source_id: string;
  first_seen: string;
  last_seen: string;
  status: ListingStatus;
}

export interface Listing {
  id: string;
  address: string;
  unit: string | null;
  lat: number;
  lng: number;
  borough: Borough;
  neighborhood: string | null;
  status: ListingStatus;
  bedrooms: number;
  bathrooms: number;
  sqft: number | null;
  amenities: string[];
  current_price: number;
  original_price: number | null;
  price_change_pct: number | null;
  quality_score: number | null;
  rs_probability: number | null;
  undervalue_score: number | null;
  is_rent_stabilized: boolean | null;
  dom: number | null; // days on market
  images: string[];
  sources: ListingSourceRecord[];
  created_at: string;
  updated_at: string;
  last_seen_at: string;
}

export interface ListingDetail extends Listing {
  price_history: PriceHistory[];
  similar_listings: Listing[];
  building_permits: BuildingPermit[];
}

export interface BuildingPermit {
  id: string;
  address: string;
  permit_type: string;
  issued_date: string;
  status: string;
  description: string | null;
}

// ---------- User & Auth ----------

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

// ---------- Saved searches ----------

export interface SavedSearch {
  id: string;
  user_id: string;
  name: string;
  filters: ListingFilters;
  notify: boolean;
  channels: NotificationChannel[];
  created_at: string;
  updated_at: string;
}

export interface ListingFilters {
  price_min?: number;
  price_max?: number;
  bedrooms?: number[];
  bathrooms_min?: number;
  boroughs?: Borough[];
  neighborhoods?: string[];
  amenities?: string[];
  distance_lat?: number;
  distance_lng?: number;
  distance_miles?: number;
  status?: ListingStatus;
  sort_by?: SortField;
  sort_order?: "asc" | "desc";
}

export const SortField = {
  PRICE: "price",
  CREATED: "created_at",
  QUALITY: "quality_score",
  DOM: "dom",
  UNDERVALUE: "undervalue_score",
} as const;
export type SortField = (typeof SortField)[keyof typeof SortField];

// ---------- Notifications ----------

export interface Notification {
  id: string;
  user_id: string;
  event_type: EventType;
  listing_id: string;
  listing: Listing | null;
  channel: NotificationChannel;
  title: string;
  body: string;
  read: boolean;
  sent_at: string;
  read_at: string | null;
}

// ---------- Stats ----------

export interface ListingStats {
  total_listings: number;
  avg_price: number;
  median_price: number;
  by_borough: Record<Borough, { count: number; avg_price: number }>;
  by_bedrooms: Record<number, { count: number; avg_price: number }>;
}

// ---------- Pagination ----------

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ---------- API error ----------

export interface ApiError {
  detail: string;
  status: number;
}
