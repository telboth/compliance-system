import { apiClient } from "./client";
import type {
  ExportControlBackfillResponse,
  ExportControlClassifyResponse,
  ExportControlListResponse,
  ExportControlReferenceResponse,
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
