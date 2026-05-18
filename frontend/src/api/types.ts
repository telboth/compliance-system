// Typer som speiler backend-skjemaer. Holdes manuelt i synk inntil vi
// genererer typer automatisk fra OpenAPI (planlagt i Sprint 6).

export type InvoiceDirection = "incoming" | "outgoing";

export type InvoiceStatus =
  | "uploaded"
  | "parsing"
  | "parsed"
  | "parsing_failed"
  | "not_invoice"
  | "extracting"
  | "extraction_failed"
  | "extracted"
  | "screening"
  | "screening_failed"
  | "screened"
  | "reviewed"
  | "approved"
  | "blocked";

export type ComplianceScore = "green" | "yellow" | "red";
export type ApprovalState =
  | "pending"
  | "approved"
  | "blocked"
  | "not_required"
  | "assessing";

export interface InvoiceLine {
  id: string;
  line_number: number | null;
  description: string | null;
  product_code: string | null;
  hs_code: string | null;
  eccn: string | null;
  serial_number: string | null;
  model_number: string | null;
  country_of_origin: string | null;
  quantity: string | null;
  unit_of_measure: string | null;
  unit_price: string | null;
  total_price: string | null;
  currency: string | null;
}

export type EntityRole =
  | "seller"
  | "buyer"
  | "consignor"
  | "consignee"
  | "end_user"
  | "delivery_address"
  | "signatory"
  | "other";

export interface Entity {
  id: string;
  name: string;
  entity_type: string;
  country: string | null;
  role: EntityRole;
  address: string | null;
  phone: string | null;
  email: string | null;
  confidence: number | null;
}

export interface ExtractionConfidence {
  invoice_number: number;
  invoice_date: number;
  total_amount: number;
  currency: number;
  incoterms: number;
  transport_mode: number;
  destination_country: number;
  // Nyere felt — kan mangle på eldre invoices
  vat_amount?: number;
  vat_rate?: number;
  instructions?: number;
  overall: number;
  low_confidence_fields: string[];
}

export interface VatMismatchCheck {
  sender_country: string | null;
  receiver_country: string | null;
  export_detected: boolean;
  has_vat: boolean;
  vat_amount: string | null;
  vat_rate: string | null;
  flagged: boolean;
  reason: string | null;
}

export interface Invoice {
  id: string;
  invoice_number: string | null;
  customer_id: string | null;
  direction: InvoiceDirection;
  pdf_path: string;
  original_filename: string | null;
  file_size_bytes: number | null;
  status: InvoiceStatus;
  parsing_error: string | null;
  total_amount: string | null;
  currency: string | null;
  invoice_date: string | null;
  compliance_score: ComplianceScore | null;
  approval_state: ApprovalState;
  created_at: string;
  updated_at: string;
  // Forsendelse og transport
  incoterms: string | null;
  transport_mode: string | null;
  destination_country: string | null;
  po_number: string | null;
  comments: string | null;
  // Instruksjoner og MVA
  instructions: string | null;
  vat_amount: string | null;
  vat_rate: string | null;
  // LLM-ekstraksjon
  extraction_confidence: ExtractionConfidence | null;
  extraction_error: string | null;
  extraction_model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  raw_text: string | null;
  vat_mismatch_check: VatMismatchCheck | null;
  lines: InvoiceLine[];
  entities: Entity[];
  // Review-beslutning
  review_decision: string | null;
  review_reason: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
}

export interface InvoiceSummary {
  id: string;
  invoice_number: string | null;
  direction: InvoiceDirection;
  status: InvoiceStatus;
  compliance_score: ComplianceScore | null;
  approval_state: ApprovalState;
  total_amount: string | null;
  currency: string | null;
  invoice_date: string | null;
  original_filename: string | null;
  created_at: string;
  vat_note_status: "ok" | "warn" | "error" | null;
  vat_note_text: string | null;
  email_note_status: "ok" | "warn" | "error" | null;
  email_note_text: string | null;
  llm_note_preview: string | null;
  llm_note_full: string | null;
}

export interface InvoiceListResponse {
  items: InvoiceSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface VatMismatchItem {
  invoice_id: string;
  invoice_number: string | null;
  original_filename: string | null;
  direction: InvoiceDirection;
  status: InvoiceStatus;
  invoice_date: string | null;
  created_at: string;
  vat_check: VatMismatchCheck;
}

export interface VatMismatchListResponse {
  total_scanned: number;
  total_flagged: number;
  limit: number;
  offset: number;
  items: VatMismatchItem[];
}

// ── Review-kø ─────────────────────────────────────────────────────────────────

export interface ReviewQueueItem {
  id: string;
  invoice_number: string | null;
  original_filename: string | null;
  direction: InvoiceDirection;
  status: InvoiceStatus;
  compliance_score: ComplianceScore | null;
  total_amount: string | null;
  currency: string | null;
  destination_country: string | null;
  created_at: string;
  review_decision: string | null;
  reviewed_at: string | null;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  total: number;
}

export interface InvoiceUploadResponse {
  // Parsing skjer asynkront — sjekk invoice.status for fremdrift
  invoice: Invoice;
}

// ── In-app varsler ────────────────────────────────────────────────────────────

export interface AppNotification {
  id: string;
  message: string;
  level: "info" | "warn" | "error";
  invoice_id: string | null;
  target_roles: string[];
  created_at: string;
}

export interface NotificationListResponse {
  items: AppNotification[];
  total: number;
}

// ── Sanksjonsscreening ────────────────────────────────────────────────────────

export type MatchStatus = "clear" | "potential_match" | "confirmed_match";

export interface ScreeningResult {
  id: string;
  invoice_id: string;
  entity_id: string;
  dataset: string;
  dataset_entity_id: string | null;
  matched_name: string | null;
  score: string; // Decimal serialisert som streng
  listed_on: string | null; // ISO-dato
  status: MatchStatus;
  screened_at: string;
  // Denormalisert fra Entity
  entity_name: string | null;
  entity_role: string | null;
  match_explanation: string | null;
}

export interface ScreeningResultsResponse {
  invoice_id: string;
  compliance_score: string | null;
  results: ScreeningResult[];
  screened_at: string | null;
  total_entities: number;
  confirmed_matches: number;
  potential_matches: number;
  clear: number;
}

export interface ScreeningCandidateDebug {
  key: string;
  entity_id: string;
  entity_name: string | null;
  entity_role: string | null;
  candidate_name: string;
  entity_type: string;
  country: string | null;
  source: string;
  source_email: string | null;
  primary: boolean;
}

export interface ScreeningCandidatesResponse {
  invoice_id: string;
  run_id: string | null;
  run_status: string | null;
  run_started_at: string | null;
  run_finished_at: string | null;
  mode: "snapshot" | "preview" | string;
  total: number;
  items: ScreeningCandidateDebug[];
}

export interface YenteDatasetStatus {
  name: string;
  title: string | null;
  entity_count: number | null;
  last_updated: string | null;
  status: string;
}

export interface LocalSanctionsSourceStatus {
  source: string;
  last_updated: string | null;
  entry_count: number | null;
  update_status: string;
  error_message: string | null;
}

export interface ExternalSourceHealthStatus {
  source: string;
  enabled: boolean;
  status: string;
  entry_count: number | null;
  last_updated: string | null;
  error_message: string | null;
  stale: boolean;
}

export interface SanctionsRefreshRunStatus {
  trigger: string;
  status: string;
  message: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface SanctionsStatusResponse {
  yente_available: boolean;
  elasticsearch_available: boolean;
  elasticsearch_error: string | null;
  yente_version: string | null;
  datasets: YenteDatasetStatus[];
  local_sources: LocalSanctionsSourceStatus[];
  external_sources: ExternalSourceHealthStatus[];
  refresh_schedule_time: string;
  refresh_schedule_timezone: string;
  external_refresh_schedule_time: string;
  last_refresh_run: SanctionsRefreshRunStatus | null;
}

export interface SanctionsRefreshResponse {
  message: string;
  datasets_triggered: string[];
}

export interface PipelineStageSummary {
  stage: string;
  in_progress: number;
  stuck: number;
  failed: number;
  completed_last_window: number;
}

export interface PipelineLatencySummary {
  metric: string;
  p50_seconds: number | null;
  p95_seconds: number | null;
  average_seconds: number | null;
}

export interface PipelineMetricsResponse {
  generated_at: string;
  lookback_hours: number;
  total_invoices: number;
  total_invoices_last_window: number;
  staged: PipelineStageSummary[];
  latencies: PipelineLatencySummary[];
  alerts: string[];
}

export interface PipelineRecoveryItem {
  invoice_id: string;
  invoice_number: string | null;
  original_filename: string | null;
  status: string;
  compliance_score: string | null;
  updated_at: string;
  minutes_in_status: number;
  reason: string | null;
}

export interface PipelineRecoveryResponse {
  generated_at: string;
  stale_minutes: number;
  total: number;
  items: PipelineRecoveryItem[];
}

export interface PipelineRecoveryActionResponse {
  invoice_id: string;
  target: "parse" | "extract" | "screen" | string;
  message: string;
}

export type SanctionedEntityType = "all" | "company" | "person";

export interface SanctionedEntity {
  id: string;
  caption: string;
  schema: string;
  datasets: string[];
  countries: string[];
  topics: string[];
  first_seen: string | null;
  last_seen: string | null;
  last_change: string | null;
}

export interface SanctionedEntityListResponse {
  items: SanctionedEntity[];
  total: number;
  total_relation: string;
  limit: number;
  offset: number;
  query: string;
  entity_type: SanctionedEntityType;
}

export interface ExtractionRequest {
  model_id: string | null;
}

export interface ExtractionResponse {
  invoice: Invoice;
  overall_confidence: number;
  low_confidence_fields: string[];
  model_id: string;
  input_tokens: number;
  output_tokens: number;
}

export interface ExtendedScreenStartRequest {
  aggressiveness: number;
  min_edge_confidence?: number;
  selected_only?: boolean;
  sanctions_near_only?: boolean;
  enable_brreg?: boolean;
  enable_uk_sanctions?: boolean;
  enable_world_bank_debarred?: boolean;
  enable_ai_entity_research?: boolean;
  enable_ai_web_search?: boolean;
}

export interface ExtendedScreenRunConfig {
  min_edge_confidence: number;
  selected_only: boolean;
  sanctions_near_only: boolean;
  enable_brreg: boolean;
  enable_uk_sanctions: boolean;
  enable_world_bank_debarred: boolean;
  enable_ai_entity_research: boolean;
  enable_ai_web_search: boolean;
}

export interface ExtendedScreenRun {
  id: string;
  invoice_id: string;
  entity_id: string;
  aggressiveness: number;
  status: "queued" | "running" | "completed" | "failed";
  summary_risk: "low" | "medium" | "high" | null;
  summary_text: string | null;
  error_message: string | null;
  run_config?: ExtendedScreenRunConfig | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  result_payload?: Record<string, unknown> | null;
}

export interface ExtendedScreenFeedbackCreate {
  feedback_label: "false_positive" | "good_hit";
  target_qid?: string | null;
  target_name?: string | null;
  note?: string | null;
}

export interface ExtendedScreenFeedback {
  id: string;
  run_id: string;
  invoice_id: string;
  entity_id: string;
  feedback_label: "false_positive" | "good_hit";
  target_qid: string | null;
  target_name: string | null;
  note: string | null;
  created_at: string;
}

export interface ExtendedScreenSource {
  id: string;
  run_id: string;
  invoice_id: string;
  entity_id: string;
  provider: string;
  source_url: string;
  source_title: string | null;
  source_domain: string | null;
  published_at: string | null;
  fetched_at: string;
  raw_payload: Record<string, unknown> | null;
}

export interface ExtendedScreenClaim {
  id: string;
  run_id: string;
  invoice_id: string;
  entity_id: string;
  claim_type: string;
  claim_subject: string;
  claim_object: string;
  confidence: number | null;
  verification_status: string;
  source_provider: string;
  source_url: string | null;
  quoted_text: string | null;
  raw_payload: Record<string, unknown> | null;
  created_at: string;
}

// ── Invoice search ────────────────────────────────────────────────────────────

export interface SearchFieldInfo {
  key: string;
  label: string;
  field_type: string;
  fuzzy: boolean;
  exact: boolean;
}

export interface SearchFieldsResponse {
  global_search: SearchFieldInfo;
  fields: SearchFieldInfo[];
}

export interface InvoiceSearchHit {
  invoice_id: string;
  score: number;
  invoice_number: string | null;
  original_filename: string | null;
  status: string | null;
  direction: string | null;
  destination_country: string | null;
  invoice_date: string | null;
  total_amount: string | null;
  currency: string | null;
  matched_entities: string[];
  matched_lines: string[];
  highlights: string[];
  field_matches: Array<{
    field: string;
    label: string;
    snippets: string[];
  }>;
  shipment_summary: {
    consignor?: string | null;
    consignee?: string | null;
    end_user?: string | null;
    destination_country?: string | null;
    top_items?: string[];
  };
}

export interface InvoiceSearchResponse {
  total: number;
  limit: number;
  offset: number;
  took_ms: number | null;
  query_mode: string;
  hits: InvoiceSearchHit[];
}

export interface InvoiceSearchRequest {
  q?: string;
  entity_q?: string;
  line_q?: string;
  serial_number?: string;
  destination_country?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export interface ReindexResponse {
  message: string;
  indexed: number;
  failed: number;
}

export interface RAGSearchRequest {
  query: string;
  entity_q?: string;
  line_q?: string;
  serial_number?: string;
  destination_country?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  with_answer?: boolean;
}

export interface RAGSourceRef {
  invoice_id: string;
  chunk_id: string;
  original_filename: string | null;
  invoice_number: string | null;
  chunk_index: number;
  score: number;
  snippet: string;
  evidence_hit: boolean;
  focus_match_count: number;
}

export interface RAGSearchResponse {
  query: string;
  took_ms: number | null;
  total: number;
  total_raw: number;
  total_after_dedupe: number;
  answer: string | null;
  answer_model: string | null;
  answer_source_count: number;
  hits: RAGSourceRef[];
}

// ── Intern sperreliste ────────────────────────────────────────────────────────

export type WatchlistEntryType = "name" | "email_domain" | "country" | "regex";
export type WatchlistSeverity = "yellow" | "red";

export interface WatchlistEntry {
  id: string;
  entry_type: WatchlistEntryType;
  value: string;
  reason: string | null;
  severity: WatchlistSeverity;
  added_by: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WatchlistListResponse {
  total: number;
  items: WatchlistEntry[];
}

export interface WatchlistEntryCreate {
  entry_type: WatchlistEntryType;
  value: string;
  reason?: string;
  severity?: WatchlistSeverity;
  added_by?: string;
}

export interface WatchlistEntryUpdate {
  value?: string;
  reason?: string;
  severity?: WatchlistSeverity;
  is_active?: boolean;
}

// ── HS-kode klassifisering ────────────────────────────────────────────────────

export interface HSClassification {
  code: string;
  chapter: string;
  chapter_description: string;
  heading: string | null;
  heading_description: string | null;
  risk_level: "high" | "medium" | "low" | null;
  risk_reason: string | null;
  is_controlled: boolean;
  dual_use_flag: boolean;
}

// ── Shipment map ──────────────────────────────────────────────────────────────

export interface ShipmentMapPoint {
  name: string | null;
  country: string | null;
  address: string | null;
  city: string | null;
  lat: number;
  lon: number;
  geo_precision: "address" | "city" | "country";
}

export interface ShipmentMapRoute {
  invoice_id: string;
  invoice_number: string | null;
  original_filename: string | null;
  invoice_date: string | null;
  total_amount: string | null;
  currency: string | null;
  compliance_score: string | null;
  risk_level: "low" | "medium" | "high";
  screening_hits: number;
  source: ShipmentMapPoint;
  destination: ShipmentMapPoint;
  low_precision_line: boolean;
}

export interface ShipmentMapResponse {
  total_routes: number;
  missing_location_count: number;
  geocode_cache_hits: number;
  geocode_external_calls: number;
  items: ShipmentMapRoute[];
}
