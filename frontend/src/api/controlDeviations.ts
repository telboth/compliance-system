import { apiClient } from "./client";
import type { ControlDeviationListResponse } from "./types";

export async function listControlDeviations(params?: {
  deviation_type?: string;
  is_repeat_vendor?: boolean;
  vendor_name?: string;
  limit?: number;
  offset?: number;
}): Promise<ControlDeviationListResponse> {
  const { data } = await apiClient.get<ControlDeviationListResponse>(
    "/control-deviations",
    { params },
  );
  return data;
}
