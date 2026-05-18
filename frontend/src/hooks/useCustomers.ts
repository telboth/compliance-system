import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createCustomer,
  deleteCustomer,
  listCustomers,
  updateCustomer,
  type CustomerCreate,
  type CustomerUpdate,
} from "@/api/customers";

const customerKeys = {
  all: ["customers"] as const,
  lists: () => [...customerKeys.all, "list"] as const,
  list: (params: { limit: number; offset: number; search?: string }) =>
    [...customerKeys.lists(), params] as const,
  detail: (id: string) => [...customerKeys.all, "detail", id] as const,
};

export function useCustomerList(
  params: { limit?: number; offset?: number; search?: string } = {},
) {
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;
  return useQuery({
    queryKey: customerKeys.list({ limit, offset, search: params.search }),
    queryFn: () => listCustomers({ limit, offset, search: params.search }),
  });
}

export function useCreateCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CustomerCreate) => createCustomer(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: customerKeys.lists() });
    },
  });
}

export function useUpdateCustomer(customerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CustomerUpdate) => updateCustomer(customerId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: customerKeys.lists() });
      void queryClient.invalidateQueries({ queryKey: customerKeys.detail(customerId) });
    },
  });
}

export function useDeleteCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteCustomer(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: customerKeys.lists() });
    },
  });
}
