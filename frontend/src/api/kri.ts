import { apiClient } from "./client";
import type { KRIReport } from "./types";

export async function getKRIReport(months: number = 12): Promise<KRIReport> {
  const { data } = await apiClient.get<KRIReport>("/kri", { params: { months } });
  return data;
}

export function getKRICSVUrl(months: number = 12): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
  return `${base}/kri/export/csv?months=${months}`;
}
