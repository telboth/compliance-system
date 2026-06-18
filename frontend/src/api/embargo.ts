import { apiClient } from "./client";
import type { EmbargoCountry, EmbargoImportResult, EmbargoSyncState } from "./types";

/** Hent alle aktive embargoland. */
export async function listEmbargoCountries(): Promise<EmbargoCountry[]> {
  const { data } = await apiClient.get<EmbargoCountry[]>("/embargo/countries");
  return data;
}

/** Hent synkroniseringsstatus for embargo-lista. */
export async function getEmbargoSyncStatus(): Promise<EmbargoSyncState> {
  const { data } = await apiClient.get<EmbargoSyncState>("/embargo/sync/status");
  return data;
}

/** Sjekk manuelt om embargo-lista har ny versjon. */
export async function checkEmbargoUpdates(): Promise<{ status: string; result: string }> {
  const { data } = await apiClient.post<{ status: string; result: string }>(
    "/embargo/sync/check",
  );
  return data;
}

/** Last ned og importer embargo-lista. */
export async function importEmbargoList(actor = "manual"): Promise<EmbargoImportResult> {
  const { data } = await apiClient.post<EmbargoImportResult>(
    "/embargo/sync/import",
    null,
    { params: { actor } },
  );
  return data;
}

/** Oppdater nedlastings-URL for embargo-lista (kun admin). */
export async function setEmbargoListUrl(url: string): Promise<EmbargoSyncState> {
  const { data } = await apiClient.put<EmbargoSyncState>(
    "/embargo/sync/url",
    null,
    { params: { url } },
  );
  return data;
}
