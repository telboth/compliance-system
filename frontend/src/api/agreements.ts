import { apiClient } from "@/api/client";

export interface Agreement {
  id: string;
  name: string;
  reference: string | null;
  description: string | null;
  original_filename: string | null;
  valid_from: string | null;
  valid_to: string | null;
  is_active: boolean;
  extracted_terms: Record<string, unknown> | null;
  extraction_model: string | null;
  extraction_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgreementDeviation {
  field: string;
  expected: unknown;
  actual: unknown;
  message: string;
}

export interface AgreementCheckResult {
  id: string;
  agreement_id: string;
  invoice_id: string;
  checked_at: string;
  compliant: boolean;
  deviations: AgreementDeviation[] | null;
  checked_terms: Record<string, unknown> | null;
}

export async function listAgreements(): Promise<Agreement[]> {
  const { data } = await apiClient.get<Agreement[]>("/agreements");
  return data;
}

export async function getAgreement(id: string): Promise<Agreement> {
  const { data } = await apiClient.get<Agreement>(`/agreements/${id}`);
  return data;
}

export async function createAgreement(formData: FormData): Promise<Agreement> {
  const { data } = await apiClient.post<Agreement>("/agreements", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function checkInvoiceAgainstAgreement(
  agreementId: string,
  invoiceId: string,
): Promise<AgreementCheckResult> {
  const { data } = await apiClient.post<AgreementCheckResult>(
    `/agreements/${agreementId}/check`,
    { invoice_id: invoiceId },
  );
  return data;
}

export async function getAgreementChecksForInvoice(
  invoiceId: string,
): Promise<AgreementCheckResult[]> {
  const { data } = await apiClient.get<AgreementCheckResult[]>(
    `/invoices/${invoiceId}/agreement-checks`,
  );
  return data;
}
