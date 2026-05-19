import { apiClient } from "@/api/client";
import type {
  ExtendedScreenClaim,
  ExtendedScreenFeedback,
  ExtendedScreenFeedbackCreate,
  ExtendedScreenSource,
  ExtractionRequest,
  ExtractionResponse,
  ExtendedScreenRun,
  ExtendedScreenStartRequest,
  InvoiceSearchRequest,
  InvoiceSearchResponse,
  RAGSearchRequest,
  RAGSearchResponse,
  Invoice,
  ApprovalState,
  InvoiceDirection,
  InvoiceListResponse,
  InvoiceListPreferences,
  InvoiceUploadResponse,
  ReindexResponse,
  PipelineMetricsResponse,
  PipelineRecoveryActionResponse,
  PipelineRecoveryResponse,
  ReviewAndNextResponse,
  ReviewQueueResponse,
  SanctionsStatusResponse,
  SanctionsRefreshResponse,
  SanctionedEntityListResponse,
  SanctionedEntityType,
  ScreeningCandidatesResponse,
  ScreeningResultsResponse,
  ShipmentMapResponse,
  VatMismatchListResponse,
} from "@/api/types";

// Docling OCR kan ta opptil 2-3 minutter for store bilder og skannet PDF.
// Vi overstyrer global timeout kun for dette kallet.
const UPLOAD_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutter

export async function uploadInvoice(
  file: File,
  direction: InvoiceDirection = "incoming",
  customerId?: string | null,
): Promise<InvoiceUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("direction", direction);
  if (customerId) formData.append("customer_id", customerId);

  const { data } = await apiClient.post<InvoiceUploadResponse>(
    "/invoices/upload",
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: UPLOAD_TIMEOUT_MS,
    },
  );
  return data;
}

export async function listInvoices(params: {
  limit?: number;
  offset?: number;
  status?: string | null;
  direction?: string | null;
  compliance_score?: string | null;
  approval_state?: ApprovalState | null;
  vat_note_status?: string | null;
  email_note_status?: string | null;
  destination_country?: string | null;
  date_from?: string | null;
  date_to?: string | null;
  sort_by?: string | null;
  sort_dir?: "asc" | "desc" | null;
}): Promise<InvoiceListResponse> {
  // Strip null/undefined values — backend treats missing params as "no filter"
  const clean: Record<string, string | number> = {};
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== "") clean[k] = v;
  }
  const { data } = await apiClient.get<InvoiceListResponse>("/invoices", {
    params: clean,
  });
  return data;
}

export async function getInvoice(id: string): Promise<Invoice> {
  const { data } = await apiClient.get<Invoice>(`/invoices/${id}`);
  return data;
}

export async function listVatMismatches(params: {
  limit?: number;
  offset?: number;
  flagged_only?: boolean;
} = {}): Promise<VatMismatchListResponse> {
  const clean: Record<string, string | number | boolean> = {};
  for (const [k, v] of Object.entries(params)) {
    if (v != null) clean[k] = v;
  }
  const { data } = await apiClient.get<VatMismatchListResponse>(
    "/invoices/vat-mismatches",
    { params: clean },
  );
  return data;
}

export async function deleteInvoice(id: string): Promise<void> {
  await apiClient.delete(`/invoices/${id}`);
}

export function getInvoiceFileUrl(id: string): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
  return `${base}/invoices/${id}/file`;
}

export async function extractInvoice(
  id: string,
  request: ExtractionRequest,
): Promise<ExtractionResponse> {
  const { data } = await apiClient.post<ExtractionResponse>(
    `/invoices/${id}/extract`,
    request,
  );
  return data;
}

export async function reparseInvoice(id: string): Promise<Invoice> {
  const { data } = await apiClient.post<Invoice>(`/invoices/${id}/reparse`);
  return data;
}

// ── Manuelle korrigeringer ────────────────────────────────────────────────────

export type InvoiceFieldsUpdate = Partial<{
  invoice_number: string;
  invoice_date: string;        // YYYY-MM-DD
  total_amount: string;
  currency: string;
  incoterms: string;
  transport_mode: string;
  destination_country: string;
  po_number: string;
  comments: string;
}>;

export type InvoiceLineUpdate = Partial<{
  description: string;
  product_code: string;
  hs_code: string;
  eccn: string;
  serial_number: string;
  model_number: string;
  country_of_origin: string;
  quantity: string;
  unit_of_measure: string;
  unit_price: string;
  total_price: string;
  currency: string;
}>;

export type EntityUpdate = Partial<{
  name: string;
  role: string;
  entity_type: string;
  country: string;
  address: string;
  phone: string;
  email: string;
}>;

export async function updateInvoiceFields(
  id: string,
  update: InvoiceFieldsUpdate,
): Promise<Invoice> {
  const { data } = await apiClient.patch<Invoice>(`/invoices/${id}/fields`, update);
  return data;
}

export async function updateInvoiceLine(
  invoiceId: string,
  lineId: string,
  update: InvoiceLineUpdate,
): Promise<import("@/api/types").InvoiceLine> {
  const { data } = await apiClient.patch(
    `/invoices/${invoiceId}/lines/${lineId}`,
    update,
  );
  return data;
}

export async function updateEntity(
  invoiceId: string,
  entityId: string,
  update: EntityUpdate,
): Promise<import("@/api/types").Entity> {
  const { data } = await apiClient.patch(
    `/invoices/${invoiceId}/entities/${entityId}`,
    update,
  );
  return data;
}

// ── Sanksjonsscreening ────────────────────────────────────────────────────────

export async function startScreening(invoiceId: string): Promise<{ message: string }> {
  const { data } = await apiClient.post(`/invoices/${invoiceId}/screen`);
  return data;
}

export async function getScreeningResults(
  invoiceId: string,
): Promise<ScreeningResultsResponse> {
  const { data } = await apiClient.get<ScreeningResultsResponse>(
    `/invoices/${invoiceId}/screening`,
  );
  return data;
}

export async function getScreeningCandidates(
  invoiceId: string,
): Promise<ScreeningCandidatesResponse> {
  const { data } = await apiClient.get<ScreeningCandidatesResponse>(
    `/invoices/${invoiceId}/screening/candidates`,
  );
  return data;
}

export async function getSanctionsStatus(): Promise<SanctionsStatusResponse> {
  const { data } = await apiClient.get<SanctionsStatusResponse>("/sanctions/status");
  return data;
}

export async function refreshSanctions(): Promise<SanctionsRefreshResponse> {
  const { data } = await apiClient.post<SanctionsRefreshResponse>("/sanctions/refresh");
  return data;
}

export async function refreshExternalSources(): Promise<SanctionsRefreshResponse> {
  const { data } = await apiClient.post<SanctionsRefreshResponse>(
    "/sanctions/external-sources/refresh",
  );
  return data;
}

export async function getPipelineMetrics(params: {
  lookback_hours?: number;
} = {}): Promise<PipelineMetricsResponse> {
  const clean: Record<string, string | number> = {};
  if (params.lookback_hours != null) clean.lookback_hours = params.lookback_hours;
  const { data } = await apiClient.get<PipelineMetricsResponse>("/sanctions/pipeline/metrics", {
    params: clean,
  });
  return data;
}

export async function getPipelineRecovery(params: {
  stale_minutes?: number;
  limit?: number;
} = {}): Promise<PipelineRecoveryResponse> {
  const clean: Record<string, string | number> = {};
  if (params.stale_minutes != null) clean.stale_minutes = params.stale_minutes;
  if (params.limit != null) clean.limit = params.limit;
  const { data } = await apiClient.get<PipelineRecoveryResponse>("/sanctions/pipeline/recovery", {
    params: clean,
  });
  return data;
}

export async function retryPipelineInvoice(
  invoiceId: string,
  target: "auto" | "parse" | "extract" | "screen" = "auto",
): Promise<PipelineRecoveryActionResponse> {
  const { data } = await apiClient.post<PipelineRecoveryActionResponse>(
    `/sanctions/pipeline/recovery/${invoiceId}/retry`,
    undefined,
    { params: { target } },
  );
  return data;
}

export async function listSanctionedEntities(params: {
  q?: string;
  entity_type?: SanctionedEntityType;
  limit?: number;
  offset?: number;
  fuzzy?: boolean;
  simple?: boolean;
}): Promise<SanctionedEntityListResponse> {
  const clean: Record<string, string | number | boolean> = {};
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== "") clean[k] = v;
  }
  const { data } = await apiClient.get<SanctionedEntityListResponse>(
    "/sanctions/entities",
    { params: clean },
  );
  return data;
}

export async function startExtendedScreening(
  invoiceId: string,
  entityId: string,
  request: ExtendedScreenStartRequest,
): Promise<ExtendedScreenRun> {
  const { data } = await apiClient.post<ExtendedScreenRun>(
    `/invoices/${invoiceId}/entities/${entityId}/extended-screen`,
    request,
  );
  return data;
}

export async function getExtendedScreeningRun(
  invoiceId: string,
  entityId: string,
  runId: string,
): Promise<ExtendedScreenRun> {
  const { data } = await apiClient.get<ExtendedScreenRun>(
    `/invoices/${invoiceId}/entities/${entityId}/extended-screen/${runId}`,
  );
  return data;
}

export async function addExtendedScreenFeedback(
  invoiceId: string,
  entityId: string,
  runId: string,
  request: ExtendedScreenFeedbackCreate,
): Promise<ExtendedScreenFeedback> {
  const { data } = await apiClient.post<ExtendedScreenFeedback>(
    `/invoices/${invoiceId}/entities/${entityId}/extended-screen/${runId}/feedback`,
    request,
  );
  return data;
}

export async function listExtendedScreenFeedback(
  invoiceId: string,
  entityId: string,
  runId: string,
): Promise<ExtendedScreenFeedback[]> {
  const { data } = await apiClient.get<ExtendedScreenFeedback[]>(
    `/invoices/${invoiceId}/entities/${entityId}/extended-screen/${runId}/feedback`,
  );
  return data;
}

export async function getExtendedScreenSources(
  invoiceId: string,
  entityId: string,
  runId: string,
): Promise<ExtendedScreenSource[]> {
  const { data } = await apiClient.get<ExtendedScreenSource[]>(
    `/invoices/${invoiceId}/entities/${entityId}/extended-screen/${runId}/sources`,
  );
  return data;
}

export async function getExtendedScreenClaims(
  invoiceId: string,
  entityId: string,
  runId: string,
): Promise<ExtendedScreenClaim[]> {
  const { data } = await apiClient.get<ExtendedScreenClaim[]>(
    `/invoices/${invoiceId}/entities/${entityId}/extended-screen/${runId}/claims`,
  );
  return data;
}

// ── Invoice search ────────────────────────────────────────────────────────────

export async function searchInvoices(
  params: InvoiceSearchRequest,
): Promise<InvoiceSearchResponse> {
  const clean: Record<string, string | number> = {};
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== "") clean[k] = v as string | number;
  }
  const { data } = await apiClient.get<InvoiceSearchResponse>("/search/invoices", {
    params: clean,
  });
  return data;
}

export async function reindexInvoicesSearch(): Promise<ReindexResponse> {
  const { data } = await apiClient.post<ReindexResponse>("/search/reindex");
  return data;
}

export async function searchInvoicesRAG(
  request: RAGSearchRequest,
): Promise<RAGSearchResponse> {
  const clean: Record<string, string | number | boolean> = {};
  for (const [k, v] of Object.entries(request)) {
    if (v != null && v !== "") clean[k] = v as string | number | boolean;
  }
  const { data } = await apiClient.post<RAGSearchResponse>("/search/rag/query", clean);
  return data;
}

export async function reindexInvoicesRAG(): Promise<ReindexResponse> {
  const { data } = await apiClient.post<ReindexResponse>("/search/rag/reindex");
  return data;
}

// ── Review ────────────────────────────────────────────────────────────────────

export interface ReviewCreate {
  decision: "approved" | "blocked";
  reason: string;
  rule_reference: string;
  evidence_summary: string;
  deviation_approval: boolean;
}

export interface RiskEscalationCreate {
  target_score: "yellow" | "red";
  reason: string;
}

export interface InvoiceListPreferencesUpdate {
  table_col_widths?: Record<string, number>;
  table_col_presets?: Array<Record<string, unknown>>;
  default_filters?: Record<string, string | number | null>;
}

export async function reviewInvoice(
  id: string,
  request: ReviewCreate,
  actor?: string,
): Promise<Invoice> {
  const params: Record<string, string> = {};
  if (actor) params.actor = actor;
  const { data } = await apiClient.post<Invoice>(
    `/invoices/${id}/review`,
    request,
    { params },
  );
  return data;
}

export async function reviewInvoiceAndNext(
  id: string,
  request: ReviewCreate,
  actor?: string,
): Promise<ReviewAndNextResponse> {
  const params: Record<string, string> = {};
  if (actor) params.actor = actor;
  const { data } = await apiClient.post<ReviewAndNextResponse>(
    `/invoices/${id}/review-and-next`,
    request,
    { params },
  );
  return data;
}

export async function claimReviewInvoice(id: string): Promise<Invoice> {
  const { data } = await apiClient.post<Invoice>(`/invoices/${id}/claim`);
  return data;
}

export async function releaseReviewClaim(id: string): Promise<Invoice> {
  const { data } = await apiClient.delete<Invoice>(`/invoices/${id}/claim`);
  return data;
}

export async function getInvoiceListPreferences(): Promise<InvoiceListPreferences> {
  const { data } = await apiClient.get<InvoiceListPreferences>("/invoices/preferences/invoice-list");
  return data;
}

export async function updateInvoiceListPreferences(
  payload: InvoiceListPreferencesUpdate,
): Promise<InvoiceListPreferences> {
  const { data } = await apiClient.put<InvoiceListPreferences>(
    "/invoices/preferences/invoice-list",
    payload,
  );
  return data;
}

export async function escalateInvoiceRisk(
  id: string,
  request: RiskEscalationCreate,
  actor?: string,
): Promise<Invoice> {
  const params: Record<string, string> = {};
  if (actor) params.actor = actor;
  const { data } = await apiClient.post<Invoice>(
    `/invoices/${id}/risk/escalate`,
    request,
    { params },
  );
  return data;
}

export async function listReviewQueue(params: {
  limit?: number;
  offset?: number;
} = {}): Promise<ReviewQueueResponse> {
  const clean: Record<string, number> = {};
  if (params.limit != null) clean.limit = params.limit;
  if (params.offset != null) clean.offset = params.offset;
  const { data } = await apiClient.get<ReviewQueueResponse>(
    "/invoices/queue/review",
    { params: clean },
  );
  return data;
}

// ── Shipment map ──────────────────────────────────────────────────────────────

export async function getShipmentsMap(params: {
  limit?: number;
  risk?: "low" | "medium" | "high" | null;
  date_from?: string | null;
  date_to?: string | null;
  max_geocode_lookups?: number | null;
}): Promise<ShipmentMapResponse> {
  const clean: Record<string, string | number> = {};
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== "") clean[k] = v;
  }
  const { data } = await apiClient.get<ShipmentMapResponse>("/shipments/map", {
    params: clean,
  });
  return data;
}
