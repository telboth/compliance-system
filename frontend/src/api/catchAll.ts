import { apiClient } from "./client";
import type {
  CatchAllBackfillResponse,
  CatchAllListResponse,
} from "./types";

/** Arbeidsliste: fakturaer med catch-all-/sluttbrukerrisiko. */
export async function listCatchAllInvoices(params?: {
  flagged_only?: boolean;
  signal_filter?: string;
  limit?: number;
  offset?: number;
}): Promise<CatchAllListResponse> {
  const { data } = await apiClient.get<CatchAllListResponse>("/catch-all/invoices", {
    params,
  });
  return data;
}

/** Backfill catch-all-status for historiske fakturaer (admin-only). */
export async function runCatchAllBackfill(
  rescore = true,
): Promise<CatchAllBackfillResponse> {
  const { data } = await apiClient.post<CatchAllBackfillResponse>(
    "/catch-all/backfill",
    null,
    { params: { rescore } },
  );
  return data;
}
