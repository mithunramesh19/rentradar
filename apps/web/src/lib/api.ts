import type {
  ApiError,
  AuthTokens,
  Listing,
  ListingDetail,
  ListingFilters,
  ListingStats,
  LoginRequest,
  Notification,
  PaginatedResponse,
  RegisterRequest,
  SavedSearch,
  User,
} from "./types";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------- Token storage (client-side only) ----------

const TOKEN_KEY = "rr_access_token";
const REFRESH_KEY = "rr_refresh_token";

function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

function setTokens(tokens: AuthTokens) {
  localStorage.setItem(TOKEN_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
}

function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

// ---------- Core fetch wrapper ----------

class ApiClient {
  private refreshing: Promise<boolean> | null = null;

  async request<T>(
    path: string,
    options: RequestInit = {},
  ): Promise<T> {
    const res = await this.rawFetch(path, options);

    if (res.status === 401 && getRefreshToken()) {
      const refreshed = await this.tryRefresh();
      if (refreshed) {
        const retry = await this.rawFetch(path, options);
        if (!retry.ok) throw await this.toApiError(retry);
        return retry.json() as Promise<T>;
      }
    }

    if (!res.ok) throw await this.toApiError(res);
    if (res.status === 204) return undefined as T;
    return res.json() as Promise<T>;
  }

  private async rawFetch(
    path: string,
    options: RequestInit,
  ): Promise<Response> {
    const headers = new Headers(options.headers);
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (!headers.has("Content-Type") && options.body) {
      headers.set("Content-Type", "application/json");
    }
    return fetch(`${API_URL}${path}`, { ...options, headers });
  }

  private async tryRefresh(): Promise<boolean> {
    if (this.refreshing) return this.refreshing;

    this.refreshing = (async () => {
      try {
        const res = await fetch(`${API_URL}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: getRefreshToken() }),
        });
        if (!res.ok) {
          clearTokens();
          return false;
        }
        const tokens: AuthTokens = await res.json();
        setTokens(tokens);
        return true;
      } catch {
        clearTokens();
        return false;
      } finally {
        this.refreshing = null;
      }
    })();

    return this.refreshing;
  }

  private async toApiError(res: Response): Promise<ApiError> {
    try {
      const body = await res.json();
      return { detail: body.detail ?? res.statusText, status: res.status };
    } catch {
      return { detail: res.statusText, status: res.status };
    }
  }
}

const client = new ApiClient();

// ---------- Auth endpoints ----------

export async function login(data: LoginRequest): Promise<AuthTokens> {
  const tokens = await client.request<AuthTokens>("/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
  setTokens(tokens);
  return tokens;
}

export async function register(data: RegisterRequest): Promise<AuthTokens> {
  const tokens = await client.request<AuthTokens>("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
  setTokens(tokens);
  return tokens;
}

export async function getMe(): Promise<User> {
  return client.request<User>("/auth/me");
}

export function logout() {
  clearTokens();
}

// ---------- Listings ----------

export async function getListings(
  filters: ListingFilters & { page?: number; page_size?: number } = {},
): Promise<PaginatedResponse<Listing>> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      value.forEach((v) => params.append(key, String(v)));
    } else {
      params.set(key, String(value));
    }
  }
  return client.request<PaginatedResponse<Listing>>(
    `/listings?${params.toString()}`,
  );
}

export async function getListing(id: string): Promise<ListingDetail> {
  return client.request<ListingDetail>(`/listings/${id}`);
}

export async function getListingStats(): Promise<ListingStats> {
  return client.request<ListingStats>("/listings/stats");
}

// ---------- Saved searches ----------

export async function getSavedSearches(): Promise<SavedSearch[]> {
  return client.request<SavedSearch[]>("/searches");
}

export async function createSavedSearch(
  data: Omit<SavedSearch, "id" | "user_id" | "created_at" | "updated_at">,
): Promise<SavedSearch> {
  return client.request<SavedSearch>("/searches", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteSavedSearch(id: string): Promise<void> {
  return client.request<void>(`/searches/${id}`, { method: "DELETE" });
}

export async function testSavedSearch(
  id: string,
): Promise<PaginatedResponse<Listing>> {
  return client.request<PaginatedResponse<Listing>>(
    `/searches/${id}/test`,
    { method: "POST" },
  );
}

// ---------- Notifications ----------

export async function getNotifications(
  page = 1,
  page_size = 20,
): Promise<PaginatedResponse<Notification>> {
  return client.request<PaginatedResponse<Notification>>(
    `/notifications?page=${page}&page_size=${page_size}`,
  );
}

export async function markNotificationRead(id: string): Promise<void> {
  return client.request<void>(`/notifications/${id}/read`, {
    method: "POST",
  });
}

export async function markAllNotificationsRead(): Promise<void> {
  return client.request<void>("/notifications/read-all", {
    method: "POST",
  });
}

// ---------- SSE ----------

export function createSSEConnection(): EventSource | null {
  const token = getAccessToken();
  if (!token) return null;
  return new EventSource(`${API_URL}/sse/events?token=${token}`);
}

// ---------- Export client for advanced usage ----------

export { client, getAccessToken, clearTokens, setTokens };
