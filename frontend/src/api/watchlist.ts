import { apiClient } from "@/api/client";
import type {
  WatchlistEntry,
  WatchlistEntryCreate,
  WatchlistEntryUpdate,
  WatchlistListResponse,
  HSClassification,
} from "@/api/types";

// ── Watchlist CRUD ─────────────────────────────────────────────────────────────

export async function listWatchlist(params?: {
  active_only?: boolean;
  limit?: number;
  offset?: number;
}): Promise<WatchlistListResponse> {
  const { data } = await apiClient.get<WatchlistListResponse>("/watchlist", {
    params: {
      active_only: params?.active_only ?? true,
      limit: params?.limit ?? 100,
      offset: params?.offset ?? 0,
    },
  });
  return data;
}

export async function createWatchlistEntry(
  body: WatchlistEntryCreate
): Promise<WatchlistEntry> {
  const { data } = await apiClient.post<WatchlistEntry>("/watchlist", body);
  return data;
}

export async function updateWatchlistEntry(
  id: string,
  body: WatchlistEntryUpdate
): Promise<WatchlistEntry> {
  const { data } = await apiClient.patch<WatchlistEntry>(`/watchlist/${id}`, body);
  return data;
}

export async function toggleWatchlistEntry(id: string): Promise<WatchlistEntry> {
  const { data } = await apiClient.patch<WatchlistEntry>(`/watchlist/${id}/toggle`);
  return data;
}

export async function deleteWatchlistEntry(id: string): Promise<void> {
  await apiClient.delete(`/watchlist/${id}`);
}

// ── HS-kode klassifisering ─────────────────────────────────────────────────────

export async function classifyHsCode(
  code: string
): Promise<HSClassification | null> {
  const { data } = await apiClient.get<HSClassification | null>("/hs-codes/classify", {
    params: { code },
  });
  return data;
}
