import { apiClient } from "./client";

export interface Customer {
  id: string;
  name: string;
  country: string | null;
  org_number: string | null;
  risk_level: string;
  created_at: string;
  updated_at: string;
}

export interface CustomerListResponse {
  items: Customer[];
  total: number;
  limit: number;
  offset: number;
}

export interface CustomerCreate {
  name: string;
  country?: string | null;
  org_number?: string | null;
  risk_level?: string;
}

export interface CustomerUpdate {
  name?: string | null;
  country?: string | null;
  org_number?: string | null;
  risk_level?: string | null;
}

export async function listCustomers(params?: {
  limit?: number;
  offset?: number;
  search?: string;
}): Promise<CustomerListResponse> {
  const p = new URLSearchParams();
  if (params?.limit) p.set("limit", String(params.limit));
  if (params?.offset) p.set("offset", String(params.offset));
  if (params?.search) p.set("search", params.search);
  const { data } = await apiClient.get<CustomerListResponse>(
    `/customers?${p.toString()}`,
  );
  return data;
}

export async function createCustomer(body: CustomerCreate): Promise<Customer> {
  const { data } = await apiClient.post<Customer>("/customers", body);
  return data;
}

export async function getCustomer(id: string): Promise<Customer> {
  const { data } = await apiClient.get<Customer>(`/customers/${id}`);
  return data;
}

export async function updateCustomer(
  id: string,
  body: CustomerUpdate,
): Promise<Customer> {
  const { data } = await apiClient.patch<Customer>(`/customers/${id}`, body);
  return data;
}

export async function deleteCustomer(id: string): Promise<void> {
  await apiClient.delete(`/customers/${id}`);
}
