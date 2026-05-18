import { apiClient } from "@/api/client";
import type { NotificationListResponse } from "@/api/types";

export async function listNotifications(params: {
  role: string;
  limit?: number;
  offset?: number;
}): Promise<NotificationListResponse> {
  const clean: Record<string, string | number> = { role: params.role };
  if (params.limit != null) clean.limit = params.limit;
  if (params.offset != null) clean.offset = params.offset;
  const { data } = await apiClient.get<NotificationListResponse>(
    "/notifications",
    { params: clean },
  );
  return data;
}

/** URL til compliance-rapport (åpnes i ny fane). */
export function getInvoiceReportUrl(invoiceId: string): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
  return `${base}/invoices/${invoiceId}/report`;
}
