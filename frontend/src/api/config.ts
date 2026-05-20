import { apiClient } from "./client";

export interface KeysStatus {
  /** Er ANTHROPIC_API_KEY konfigurert? */
  anthropic: boolean;
  /** Er OPENAI_API_KEY konfigurert? */
  openai: boolean;
}

export interface KeysUpdatePayload {
  anthropic_api_key?: string;
  openai_api_key?: string;
}

/** Henter boolsk nøkkelstatus — ingen verdier eksponeres fra backend. */
export async function fetchKeysStatus(): Promise<KeysStatus> {
  const { data } = await apiClient.get<KeysStatus>("/config/keys/status");
  return data;
}

/** Lagrer nye API-nøkler via backend (admin-only). */
export async function updateApiKeys(payload: KeysUpdatePayload): Promise<void> {
  await apiClient.post("/config/keys", payload);
}
