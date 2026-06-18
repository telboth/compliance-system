import { apiClient } from "./client";
import type {
  ExportControlBackfillResponse,
  ExportControlClassifyResponse,
  ExportControlListResponse,
  ExportControlReferenceResponse,
  ExportListSyncState,
  ExportListImportResult,
} from "./types";

/** Arbeidsliste: fakturaer med mulig listematch mot Vareliste I/II. */
export async function listExportControlInvoices(params?: {
  flagged_only?: boolean;
  list_filter?: string;
  status_filter?: string;
  limit?: number;
  offset?: number;
}): Promise<ExportControlListResponse> {
  const { data } = await apiClient.get<ExportControlListResponse>(
    "/export-control/invoices",
    { params },
  );
  return data;
}

/** Bla i den importerte referanselista (kontrollnumre + titler). */
export async function browseExportControlItems(params?: {
  list_code?: string;
  category?: string;
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<ExportControlReferenceResponse> {
  const { data } = await apiClient.get<ExportControlReferenceResponse>(
    "/export-control/items",
    { params },
  );
  return data;
}

/** Klassifiser et enkelt kontrollnummer (ECCN/ML) strukturelt. */
export async function classifyControlCode(
  code: string,
): Promise<ExportControlClassifyResponse> {
  const { data } = await apiClient.get<ExportControlClassifyResponse>(
    "/export-control/classify",
    { params: { code } },
  );
  return data;
}

/** Backfill eksportkontroll-status for historiske fakturaer (admin-only). */
export async function runExportControlBackfill(
  rescore = true,
): Promise<ExportControlBackfillResponse> {
  const { data } = await apiClient.post<ExportControlBackfillResponse>(
    "/export-control/backfill",
    null,
    { params: { rescore } },
  );
  return data;
}

// ── Vareliste-synkronisering ───────────────────────────────────────────────────

/** Hent synkroniseringsstatus for Vareliste I og II. */
export async function getExportListSyncStatus(): Promise<ExportListSyncState[]> {
  const { data } = await apiClient.get<ExportListSyncState[]>("/export-control/sync/status");
  return data;
}

/** Sjekk manuelt om Vareliste I/II har ny versjon. */
export async function checkExportListUpdates(): Promise<{ status: string; result: string }> {
  const { data } = await apiClient.post<{ status: string; result: string }>(
    "/export-control/sync/check",
  );
  return data;
}

/** Last ned og importer en vareliste (list_code = "I" eller "II"). */
export async function importExportList(
  listCode: string,
  actor = "manual",
): Promise<ExportListImportResult> {
  const { data } = await apiClient.post<ExportListImportResult>(
    `/export-control/sync/import/${listCode}`,
    null,
    { params: { triggered_by: actor } },
  );
  return data;
}

/** Oppdater nedlastings-URL for en vareliste (kun admin). */
export async function setExportListUrl(
  listCode: string,
  url: string,
): Promise<ExportListSyncState> {
  const { data } = await apiClient.put<ExportListSyncState>(
    `/export-control/sync/url/${listCode}`,
    null,
    { params: { url } },
  );
  return data;
}
