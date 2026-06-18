import { apiClient } from "./client";
import type {
  RegulatoryAlertListResponse,
  RegulatoryRefreshResponse,
  RegulatorySource,
} from "./types";

export async function getRegulatoryAlerts(params?: {
  source?: string;
  severity?: string;
  limit?: number;
  offset?: number;
}): Promise<RegulatoryAlertListResponse> {
  const { data } = await apiClient.get<RegulatoryAlertListResponse>(
    "/regulatory-radar/alerts",
    { params },
  );
  return data;
}

export async function refreshRegulatoryFeeds(): Promise<RegulatoryRefreshResponse> {
  const { data } = await apiClient.post<RegulatoryRefreshResponse>(
    "/regulatory-radar/refresh",
  );
  return data;
}

export async function getRegulatorySourcesList(): Promise<RegulatorySource[]> {
  const { data } = await apiClient.get<RegulatorySource[]>(
    "/regulatory-radar/sources",
  );
  return data;
}
