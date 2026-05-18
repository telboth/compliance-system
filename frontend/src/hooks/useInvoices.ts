import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addExtendedScreenFeedback,
  deleteInvoice,
  extractInvoice,
  getPipelineMetrics,
  getPipelineRecovery,
  getExtendedScreeningRun,
  getExtendedScreenSources,
  getExtendedScreenClaims,
  getInvoice,
  getScreeningCandidates,
  refreshExternalSources,
  retryPipelineInvoice,
  getSanctionsStatus,
  refreshSanctions,
  getScreeningResults,
  getShipmentsMap,
  listReviewQueue,
  listVatMismatches,
  listSanctionedEntities,
  reindexInvoicesSearch,
  reindexInvoicesRAG,
  listInvoices,
  listExtendedScreenFeedback,
  reparseInvoice,
  reviewInvoice,
  startExtendedScreening,
  startScreening,
  searchInvoices,
  searchInvoicesRAG,
  updateEntity,
  updateInvoiceFields,
  updateInvoiceLine,
  uploadInvoice,
  type EntityUpdate,
  type InvoiceFieldsUpdate,
  type InvoiceLineUpdate,
  type ReviewCreate,
} from "@/api/invoices";
import type {
  ComplianceScore,
  ExtendedScreenClaim,
  ExtendedScreenFeedback,
  ExtendedScreenStartRequest,
  ExtendedScreenSource,
  ExtractionRequest,
  ExtendedScreenRun,
  InvoiceDirection,
  Invoice,
  ReviewQueueResponse,
  SanctionsStatusResponse,
  SanctionedEntityListResponse,
  InvoiceSearchRequest,
  InvoiceSearchResponse,
  RAGSearchRequest,
  RAGSearchResponse,
  ReindexResponse,
  PipelineMetricsResponse,
  PipelineRecoveryActionResponse,
  PipelineRecoveryResponse,
  SanctionedEntityType,
  ScreeningCandidatesResponse,
  InvoiceStatus,
  ScreeningResultsResponse,
  ShipmentMapResponse,
  VatMismatchListResponse,
} from "@/api/types";

export interface InvoiceListFilters {
  limit?: number;
  offset?: number;
  status?: InvoiceStatus | null;
  direction?: InvoiceDirection | null;
  compliance_score?: ComplianceScore | null;
  vat_note_status?: "ok" | "warn" | "error" | null;
  email_note_status?: "ok" | "warn" | "error" | null;
  destination_country?: string | null;
  date_from?: string | null;
  date_to?: string | null;
  sort_by?: string | null;
  sort_dir?: "asc" | "desc" | null;
}

const invoiceKeys = {
  all: ["invoices"] as const,
  lists: () => [...invoiceKeys.all, "list"] as const,
  list: (params: InvoiceListFilters) => [...invoiceKeys.lists(), params] as const,
  details: () => [...invoiceKeys.all, "detail"] as const,
  detail: (id: string) => [...invoiceKeys.details(), id] as const,
};

export function useInvoiceList(params: InvoiceListFilters = {}) {
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;
  return useQuery({
    queryKey: invoiceKeys.list({ ...params, limit, offset }),
    queryFn: () => listInvoices({ ...params, limit, offset }),
    // Poll hvert 3. sek hvis noen invoices holder på å parses
    refetchInterval: (query) => {
      const hasInProgress = query.state.data?.items.some((inv) =>
        PARSING_STATUSES.has(inv.status),
      );
      return hasInProgress ? 3000 : false;
    },
  });
}

// Statuser der backend fremdeles jobber — frontend poller til det er ferdig.
// "screening" er lagt til slik at polling fortsetter under sanksjonsscreening.
const PARSING_STATUSES = new Set(["uploaded", "parsing", "extracting", "screening"]);
const AUTO_SCREEN_TRANSITION_GRACE_MS = 60_000;

function shouldPollInvoiceStatus(invoice: Pick<Invoice, "status" | "updated_at"> | null | undefined): boolean {
  if (!invoice) return false;
  if (PARSING_STATUSES.has(invoice.status)) return true;
  if (invoice.status !== "extracted") return false;
  const updatedAt = Date.parse(invoice.updated_at);
  if (Number.isNaN(updatedAt)) return false;
  return Date.now() - updatedAt < AUTO_SCREEN_TRANSITION_GRACE_MS;
}

export function useInvoice(id: string | undefined) {
  return useQuery({
    queryKey: id ? invoiceKeys.detail(id) : invoiceKeys.details(),
    queryFn: () => (id ? getInvoice(id) : Promise.reject(new Error("Mangler ID"))),
    enabled: Boolean(id),
    // Poll hvert 2. sek mens parsing pågår
    refetchInterval: (query) => {
      const data = query.state.data;
      return shouldPollInvoiceStatus(data) ? 2000 : false;
    },
  });
}

export function useUploadInvoice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      direction,
      customerId,
    }: {
      file: File;
      direction: InvoiceDirection;
      customerId?: string | null;
    }) => uploadInvoice(file, direction, customerId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: invoiceKeys.lists() });
    },
  });
}

export function useDeleteInvoice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteInvoice(id),
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: invoiceKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: invoiceKeys.lists() });
    },
  });
}

export function useReparseInvoice(invoiceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => reparseInvoice(invoiceId),
    onSuccess: (data) => {
      queryClient.setQueryData(invoiceKeys.detail(invoiceId), data);
      void queryClient.invalidateQueries({ queryKey: invoiceKeys.lists() });
    },
  });
}

// ── Manuelle korrigeringer ────────────────────────────────────────────────────

export function useUpdateInvoiceFields(invoiceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (update: InvoiceFieldsUpdate) => updateInvoiceFields(invoiceId, update),
    onSuccess: (data) => {
      queryClient.setQueryData(invoiceKeys.detail(invoiceId), data);
    },
  });
}

export function useUpdateInvoiceLine(invoiceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ lineId, update }: { lineId: string; update: InvoiceLineUpdate }) =>
      updateInvoiceLine(invoiceId, lineId, update),
    onSuccess: () => {
      // Reload full invoice so lines array is refreshed
      void queryClient.invalidateQueries({ queryKey: invoiceKeys.detail(invoiceId) });
    },
  });
}

export function useUpdateEntity(invoiceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entityId, update }: { entityId: string; update: EntityUpdate }) =>
      updateEntity(invoiceId, entityId, update),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: invoiceKeys.detail(invoiceId) });
    },
  });
}

export function useExtractInvoice(invoiceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: ExtractionRequest) => extractInvoice(invoiceId, request),
    onSuccess: (data) => {
      // Oppdater cache med den nye invoice-tilstanden
      queryClient.setQueryData(invoiceKeys.detail(invoiceId), data.invoice);
      // Tving ny henting for a plukke opp rask overgang extracted -> screening/screened.
      void queryClient.invalidateQueries({ queryKey: invoiceKeys.detail(invoiceId) });
      void queryClient.invalidateQueries({ queryKey: invoiceKeys.lists() });
    },
  });
}

// ── Review-kø ─────────────────────────────────────────────────────────────────

const reviewQueueKeys = {
  all: ["review-queue"] as const,
  list: (params: { limit?: number; offset?: number }) =>
    [...reviewQueueKeys.all, params] as const,
};

export function useReviewQueue(
  params: { limit?: number; offset?: number } = {},
  options: { enabled?: boolean } = {},
) {
  return useQuery<ReviewQueueResponse>({
    queryKey: reviewQueueKeys.list(params),
    queryFn: () => listReviewQueue(params),
    enabled: options.enabled !== false,
    staleTime: 15_000,
  });
}

export function useReviewInvoice(invoiceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      decision,
      reason,
      actor,
    }: ReviewCreate & { actor?: string }) =>
      reviewInvoice(invoiceId, { decision, reason }, actor),
    onSuccess: (data) => {
      queryClient.setQueryData(invoiceKeys.detail(invoiceId), data);
      void queryClient.invalidateQueries({ queryKey: invoiceKeys.lists() });
      void queryClient.invalidateQueries({ queryKey: reviewQueueKeys.all });
    },
  });
}

// ── Sanksjonsscreening ────────────────────────────────────────────────────────

const screeningKeys = {
  all: ["screening"] as const,
  detail: (invoiceId: string) => [...screeningKeys.all, invoiceId] as const,
};

const sanctionsKeys = {
  all: ["sanctions"] as const,
  status: () => [...sanctionsKeys.all, "status"] as const,
  pipelineMetrics: (lookbackHours: number) =>
    [...sanctionsKeys.all, "pipeline-metrics", lookbackHours] as const,
  pipelineRecovery: (staleMinutes: number, limit: number) =>
    [...sanctionsKeys.all, "pipeline-recovery", staleMinutes, limit] as const,
};

const extendedScreenKeys = {
  all: ["extended-screen"] as const,
  detail: (invoiceId: string, entityId: string, runId: string) =>
    [...extendedScreenKeys.all, invoiceId, entityId, runId] as const,
};

export function useSanctionsStatus(enabled = true) {
  return useQuery<SanctionsStatusResponse>({
    queryKey: sanctionsKeys.status(),
    queryFn: getSanctionsStatus,
    enabled,
    staleTime: 10_000,
    refetchInterval: enabled ? 10_000 : false,
  });
}

export function useRefreshSanctions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: refreshSanctions,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: sanctionsKeys.status() });
      void queryClient.invalidateQueries({ queryKey: ["sanctioned-entities"] });
    },
  });
}

export function useRefreshExternalSources() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: refreshExternalSources,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: sanctionsKeys.status() });
    },
  });
}

export function usePipelineMetrics(lookbackHours = 24, enabled = true) {
  return useQuery<PipelineMetricsResponse>({
    queryKey: sanctionsKeys.pipelineMetrics(lookbackHours),
    queryFn: () => getPipelineMetrics({ lookback_hours: lookbackHours }),
    enabled,
    staleTime: 5_000,
    refetchInterval: enabled ? 10_000 : false,
  });
}

export function usePipelineRecovery(staleMinutes = 10, limit = 100, enabled = true) {
  return useQuery<PipelineRecoveryResponse>({
    queryKey: sanctionsKeys.pipelineRecovery(staleMinutes, limit),
    queryFn: () => getPipelineRecovery({ stale_minutes: staleMinutes, limit }),
    enabled,
    staleTime: 5_000,
    refetchInterval: enabled ? 8_000 : false,
  });
}

export function useRetryPipelineInvoice() {
  const queryClient = useQueryClient();
  return useMutation<PipelineRecoveryActionResponse, Error, { invoiceId: string; target: "auto" | "parse" | "extract" | "screen" }>({
    mutationFn: ({ invoiceId, target }) => retryPipelineInvoice(invoiceId, target),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: sanctionsKeys.all });
      void queryClient.invalidateQueries({ queryKey: invoiceKeys.lists() });
    },
  });
}

export function useScreeningResults(invoiceId: string) {
  return useQuery<ScreeningResultsResponse>({
    queryKey: screeningKeys.detail(invoiceId),
    queryFn: () => getScreeningResults(invoiceId),
    // Hent resultater kun nar screeningen er ferdig (sjekkes via invoice-status)
    enabled: Boolean(invoiceId),
  });
}

export function useScreeningCandidates(invoiceId: string) {
  return useQuery<ScreeningCandidatesResponse>({
    queryKey: [...screeningKeys.detail(invoiceId), "candidates"],
    queryFn: () => getScreeningCandidates(invoiceId),
    enabled: Boolean(invoiceId),
  });
}

export function useStartScreening(invoiceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => startScreening(invoiceId),
    onSuccess: () => {
      // Sett status lokalt med en gang for tydelig UI-feedback.
      queryClient.setQueryData(invoiceKeys.detail(invoiceId), (prev: Invoice | undefined) => {
        if (!prev) return prev;
        return { ...prev, status: "screening" };
      });

      // Invalider invoice slik at backend-state synkes inn.
      void queryClient.invalidateQueries({ queryKey: invoiceKeys.detail(invoiceId) });
      void queryClient.invalidateQueries({ queryKey: screeningKeys.detail(invoiceId) });
    },
  });
}

export function useStartExtendedScreening(invoiceId: string, entityId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: ExtendedScreenStartRequest) =>
      startExtendedScreening(invoiceId, entityId, request),
    onSuccess: (run) => {
      queryClient.setQueryData(
        extendedScreenKeys.detail(invoiceId, entityId, run.id),
        run,
      );
    },
  });
}

export function useExtendedScreeningRun(
  invoiceId: string,
  entityId: string,
  runId: string | null,
  enabled = true,
) {
  return useQuery<ExtendedScreenRun>({
    queryKey: runId
      ? extendedScreenKeys.detail(invoiceId, entityId, runId)
      : [...extendedScreenKeys.all, invoiceId, entityId, "none"],
    queryFn: () => {
      if (!runId) throw new Error("Mangler run-id");
      return getExtendedScreeningRun(invoiceId, entityId, runId);
    },
    enabled: enabled && Boolean(runId),
    refetchInterval: (query) => {
      const state = query.state.data?.status;
      return state === "queued" || state === "running" ? 2000 : false;
    },
  });
}

export function useExtendedScreenSources(
  invoiceId: string,
  entityId: string,
  runId: string | null,
  enabled = true,
) {
  return useQuery<ExtendedScreenSource[]>({
    queryKey: ["extended-screen-sources", invoiceId, entityId, runId ?? "none"],
    queryFn: () => {
      if (!runId) throw new Error("Mangler run-id");
      return getExtendedScreenSources(invoiceId, entityId, runId);
    },
    enabled: enabled && Boolean(runId),
  });
}

export function useExtendedScreenClaims(
  invoiceId: string,
  entityId: string,
  runId: string | null,
  enabled = true,
) {
  return useQuery<ExtendedScreenClaim[]>({
    queryKey: ["extended-screen-claims", invoiceId, entityId, runId ?? "none"],
    queryFn: () => {
      if (!runId) throw new Error("Mangler run-id");
      return getExtendedScreenClaims(invoiceId, entityId, runId);
    },
    enabled: enabled && Boolean(runId),
  });
}

export function useExtendedScreenFeedback(
  invoiceId: string,
  entityId: string,
  runId: string | null,
  enabled = true,
) {
  return useQuery<ExtendedScreenFeedback[]>({
    queryKey: ["extended-screen-feedback", invoiceId, entityId, runId ?? "none"],
    queryFn: () => {
      if (!runId) throw new Error("Mangler run-id");
      return listExtendedScreenFeedback(invoiceId, entityId, runId);
    },
    enabled: enabled && Boolean(runId),
  });
}

export function useAddExtendedScreenFeedback(invoiceId: string, entityId: string, runId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      feedback_label: "false_positive" | "good_hit";
      target_qid?: string | null;
      target_name?: string | null;
      note?: string | null;
    }) => addExtendedScreenFeedback(invoiceId, entityId, runId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["extended-screen-feedback", invoiceId, entityId, runId],
      });
    },
  });
}

export interface SanctionedEntityFilters {
  q?: string;
  entity_type?: SanctionedEntityType;
  limit?: number;
  offset?: number;
  fuzzy?: boolean;
  simple?: boolean;
}

export function useSanctionedEntities(params: SanctionedEntityFilters) {
  const q = params.q ?? "";
  const entity_type = params.entity_type ?? "all";
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;
  const fuzzy = params.fuzzy ?? true;
  const simple = params.simple ?? true;

  return useQuery<SanctionedEntityListResponse>({
    queryKey: [
      "sanctioned-entities",
      { q, entity_type, limit, offset, fuzzy, simple },
    ],
    queryFn: () =>
      listSanctionedEntities({
        q,
        entity_type,
        limit,
        offset,
        fuzzy,
        simple,
      }),
  });
}

export interface VatMismatchFilters {
  limit?: number;
  offset?: number;
  flagged_only?: boolean;
}

export function useVatMismatches(params: VatMismatchFilters = {}) {
  const limit = params.limit ?? 100;
  const offset = params.offset ?? 0;
  const flagged_only = params.flagged_only ?? true;
  return useQuery<VatMismatchListResponse>({
    queryKey: ["vat-mismatches", { limit, offset, flagged_only }],
    queryFn: () => listVatMismatches({ limit, offset, flagged_only }),
  });
}

// ── Invoice search ────────────────────────────────────────────────────────────

export function useInvoiceSearch(params: InvoiceSearchRequest, enabled = true) {
  return useQuery<InvoiceSearchResponse>({
    queryKey: ["invoice-search", params],
    queryFn: () => searchInvoices(params),
    enabled,
  });
}

export function useReindexInvoiceSearch() {
  const queryClient = useQueryClient();
  return useMutation<ReindexResponse>({
    mutationFn: () => reindexInvoicesSearch(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["invoice-search"] });
    },
  });
}

export function useInvoiceRAGSearch(request: RAGSearchRequest | null, enabled = true) {
  return useQuery<RAGSearchResponse>({
    queryKey: ["invoice-rag-search", request],
    queryFn: () => {
      if (!request) throw new Error("Mangler RAG-request");
      return searchInvoicesRAG(request);
    },
    enabled: enabled && Boolean(request),
  });
}

export function useReindexInvoiceRAG() {
  const queryClient = useQueryClient();
  return useMutation<ReindexResponse>({
    mutationFn: () => reindexInvoicesRAG(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["invoice-rag-search"] });
    },
  });
}

// ── Shipment map ──────────────────────────────────────────────────────────────

export interface ShipmentMapFilters {
  limit?: number;
  risk?: "low" | "medium" | "high" | null;
  date_from?: string | null;
  date_to?: string | null;
  max_geocode_lookups?: number | null;
}

export function useShipmentMap(filters: ShipmentMapFilters, enabled = true) {
  return useQuery<ShipmentMapResponse>({
    queryKey: ["shipments-map", filters],
    queryFn: () =>
      getShipmentsMap({
        limit: filters.limit ?? 300,
        risk: filters.risk ?? null,
        date_from: filters.date_from ?? null,
        date_to: filters.date_to ?? null,
        max_geocode_lookups: filters.max_geocode_lookups ?? null,
      }),
    enabled,
  });
}
