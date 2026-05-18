import { apiClient } from "@/api/client";

export interface AuditLogEntry {
  id: string;
  invoice_id: string | null;
  action: string;
  actor: string;
  details: Record<string, unknown> | null;
  previous_hash: string | null;
  current_hash: string;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
}

export interface ChainVerifyResponse {
  ok: boolean;
  errors: string[];
}

export async function getAuditLog(invoiceId: string): Promise<AuditLogListResponse> {
  const { data } = await apiClient.get<AuditLogListResponse>(`/invoices/${invoiceId}/audit`);
  return data;
}

export async function verifyAuditChain(invoiceId: string): Promise<ChainVerifyResponse> {
  const { data } = await apiClient.get<ChainVerifyResponse>(`/invoices/${invoiceId}/audit/verify`);
  return data;
}
