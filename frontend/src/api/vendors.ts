import { apiClient } from "./client";
import type { Vendor, VendorListResponse } from "./types";

export async function listVendors(params?: {
  risk_level?: string;
  country?: string;
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<VendorListResponse> {
  const { data } = await apiClient.get<VendorListResponse>("/vendors", { params });
  return data;
}

export async function updateVendorNotes(
  vendorId: string,
  notes: string | null,
): Promise<Vendor> {
  const { data } = await apiClient.patch<Vendor>(`/vendors/${vendorId}/notes`, {
    notes,
  });
  return data;
}
