import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import clsx from "clsx";

import { apiClient } from "@/api/client";

import { useAuth } from "@/auth/AuthContext";
import { InvoiceUploader } from "@/components/InvoiceUploader";
import { Pagination } from "@/components/Pagination";
import { StatusBadge } from "@/components/StatusBadge";
import { ComplianceChip } from "@/components/ComplianceBadge";
import { CountryAutocomplete } from "@/components/CountryAutocomplete";
import {
  useDeleteInvoice,
  useInvoiceList,
  useInvoiceListPreferences,
  useSanctionsStatus,
  useUpdateInvoiceListPreferences,
  type InvoiceListFilters,
} from "@/hooks/useInvoices";
import type { ApprovalState, ComplianceScore, InvoiceDirection, InvoiceStatus } from "@/api/types";
import { resolveCountryToIso2 } from "@/lib/country";

type InvoiceTableColumnKey =
  | "signal"
  | "file"
  | "direction"
  | "status"
  | "approval"
  | "vat"
  | "email"
  | "llm"
  | "invoice_date"
  | "amount"
  | "created_at"
  | "actions";

const COL_WIDTH_STORAGE_KEY_PREFIX = "invoice_table_col_widths_v3";
const COL_PRESETS_STORAGE_KEY_PREFIX = "invoice_table_col_presets_v1";

const DEFAULT_COL_WIDTHS: Record<InvoiceTableColumnKey, number> = {
  signal: 130,
  file: 220,
  direction: 90,
  status: 130,
  approval: 170,
  vat: 220,
  email: 240,
  llm: 360,
  invoice_date: 120,
  amount: 130,
  created_at: 150,
  actions: 80,
};

const MIN_COL_WIDTHS: Record<InvoiceTableColumnKey, number> = {
  signal: 100,
  file: 140,
  direction: 70,
  status: 100,
  approval: 130,
  vat: 160,
  email: 170,
  llm: 220,
  invoice_date: 100,
  amount: 100,
  created_at: 120,
  actions: 60,
};

interface ColumnPreset {
  id: string;
  label?: string;
  widths: Record<InvoiceTableColumnKey, number>;
}

interface InvoiceListPreferencePayload {
  table_col_widths: Record<InvoiceTableColumnKey, number>;
  table_col_presets: Array<{
    id: string;
    label: string;
    widths: Record<InvoiceTableColumnKey, number>;
  }>;
}

const BUILTIN_PRESETS: ColumnPreset[] = [
  { id: "balanced", widths: DEFAULT_COL_WIDTHS },
  {
    id: "compact",
    widths: {
      signal: 110,
      file: 180,
      direction: 80,
      status: 110,
      approval: 140,
      vat: 180,
      email: 200,
      llm: 260,
      invoice_date: 110,
      amount: 110,
      created_at: 130,
      actions: 70,
    },
  },
  {
    id: "review_focus",
    widths: {
      signal: 140,
      file: 240,
      direction: 90,
      status: 140,
      approval: 190,
      vat: 260,
      email: 280,
      llm: 420,
      invoice_date: 120,
      amount: 130,
      created_at: 150,
      actions: 80,
    },
  },
];

function colWidthStorageKey(userId: string): string {
  return `${COL_WIDTH_STORAGE_KEY_PREFIX}:${userId}`;
}

function colPresetStorageKey(userId: string): string {
  return `${COL_PRESETS_STORAGE_KEY_PREFIX}:${userId}`;
}

function normalizeWidths(
  parsed: Partial<Record<InvoiceTableColumnKey, number>> | null | undefined,
): Record<InvoiceTableColumnKey, number> {
  if (!parsed) return DEFAULT_COL_WIDTHS;
  return {
    signal: Number(parsed.signal) || DEFAULT_COL_WIDTHS.signal,
    file: Number(parsed.file) || DEFAULT_COL_WIDTHS.file,
    direction: Number(parsed.direction) || DEFAULT_COL_WIDTHS.direction,
    status: Number(parsed.status) || DEFAULT_COL_WIDTHS.status,
    approval: Number(parsed.approval) || DEFAULT_COL_WIDTHS.approval,
    vat: Number(parsed.vat) || DEFAULT_COL_WIDTHS.vat,
    email: Number(parsed.email) || DEFAULT_COL_WIDTHS.email,
    llm: Number(parsed.llm) || DEFAULT_COL_WIDTHS.llm,
    invoice_date: Number(parsed.invoice_date) || DEFAULT_COL_WIDTHS.invoice_date,
    amount: Number(parsed.amount) || DEFAULT_COL_WIDTHS.amount,
    created_at: Number(parsed.created_at) || DEFAULT_COL_WIDTHS.created_at,
    actions: Number(parsed.actions) || DEFAULT_COL_WIDTHS.actions,
  };
}

function loadSavedColWidths(userId: string): Record<InvoiceTableColumnKey, number> {
  if (typeof window === "undefined") {
    return DEFAULT_COL_WIDTHS;
  }
  try {
    const raw =
      window.localStorage.getItem(colWidthStorageKey(userId))
      ?? window.localStorage.getItem("invoice_table_col_widths_v2");
    if (!raw) return DEFAULT_COL_WIDTHS;
    const parsed = JSON.parse(raw) as Partial<Record<InvoiceTableColumnKey, number>>;
    return normalizeWidths(parsed);
  } catch {
    return DEFAULT_COL_WIDTHS;
  }
}

function loadCustomPresets(userId: string): ColumnPreset[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(colPresetStorageKey(userId));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Array<{
      id: string;
      label: string;
      widths: Partial<Record<InvoiceTableColumnKey, number>>;
    }>;
    return parsed
      .filter((row) => row && typeof row.id === "string" && typeof row.label === "string")
      .map((row) => ({
        id: row.id,
        label: row.label,
        widths: normalizeWidths(row.widths),
      }));
  } catch {
    return [];
  }
}

function buildPreferencePayload(
  colWidths: Record<InvoiceTableColumnKey, number>,
  customPresets: ColumnPreset[],
): InvoiceListPreferencePayload {
  return {
    table_col_widths: colWidths,
    table_col_presets: customPresets.map((preset) => ({
      id: preset.id,
      label: preset.label ?? "",
      widths: preset.widths,
    })),
  };
}

function preferencePayloadSignature(payload: InvoiceListPreferencePayload): string {
  return JSON.stringify(payload);
}

type NoteStatus = "ok" | "warn" | "error" | null;

function noteClass(status: NoteStatus): string {
  if (status === "error") return "bg-red-100 text-red-800 border-red-200";
  if (status === "warn") return "bg-amber-100 text-amber-800 border-amber-200";
  return "bg-green-100 text-green-800 border-green-200";
}

function shortText(value: string | null | undefined, max = 90): string {
  const text = (value ?? "").trim();
  if (!text) return "—";
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

function approvalBadgeClass(
  state: "pending" | "approved" | "blocked" | "not_required" | "assessing",
): string {
  if (state === "approved") return "bg-green-100 text-green-800 border-green-200";
  if (state === "blocked") return "bg-red-100 text-red-800 border-red-200";
  if (state === "pending") return "bg-amber-100 text-amber-800 border-amber-200";
  if (state === "assessing") return "bg-blue-100 text-blue-800 border-blue-200";
  return "bg-gray-100 text-gray-700 border-gray-200";
}

// ── CSV-eksport ───────────────────────────────────────────────────────────────

function CsvExportButton({ filters }: { filters: InvoiceListFilters }) {
  const { t } = useTranslation("invoices");
  const [busy, setBusy] = useState(false);

  async function handleExport() {
    setBusy(true);
    try {
      const params = new URLSearchParams();
      if (filters.status) params.set("status", filters.status);
      if (filters.direction) params.set("direction", filters.direction);
      if (filters.compliance_score) params.set("compliance_score", filters.compliance_score);
      if (filters.approval_state) params.set("approval_state", filters.approval_state);
      if (filters.destination_country) params.set("destination_country", filters.destination_country);
      if (filters.date_from) params.set("date_from", filters.date_from);
      if (filters.date_to) params.set("date_to", filters.date_to);

      const url = `/api/v1/invoices/export?${params.toString()}`;
      const response = await apiClient.get(url, { responseType: "blob" });

      const blob = new Blob([response.data as BlobPart], { type: "text/csv;charset=utf-8;" });
      const blobUrl = URL.createObjectURL(blob);
      const today = new Date().toISOString().slice(0, 10);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = `fakturaer-${today}.csv`;
      a.click();
      URL.revokeObjectURL(blobUrl);
    } catch {
      alert(t("export.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      onClick={handleExport}
      disabled={busy}
      className="flex items-center gap-1.5 rounded border border-gray-200 bg-white px-3 py-1.5 text-xs text-xlent-muted hover:bg-gray-50 hover:text-xlent-ink disabled:opacity-50"
    >
      {busy ? t("export.busy") : t("export.button")}
    </button>
  );
}

// ── Filterrad ─────────────────────────────────────────────────────────────────

const selectCls =
  "rounded border border-gray-200 bg-white px-2 py-1 text-xs text-xlent-ink focus:outline-none focus:ring-1 focus:ring-xlent-primary";

interface FilterBarProps {
  filters: InvoiceListFilters;
  onChange: (f: InvoiceListFilters) => void;
}

function FilterBar({ filters, onChange }: FilterBarProps) {
  const { t } = useTranslation("invoices");
  const tCommon = useTranslation("common").t;
  const [countryInput, setCountryInput] = useState(filters.destination_country ?? "");

  // STATUS_OPTIONS built here so labels update when language changes
  const statusOptions: { value: InvoiceStatus; label: string }[] = [
    { value: "uploaded", label: tCommon("status.uploaded") },
    { value: "parsing", label: tCommon("status.parsing") },
    { value: "parsed", label: tCommon("status.parsed") },
    { value: "parsing_failed", label: tCommon("status.parsing_failed") },
    { value: "not_invoice", label: `⚠️ ${tCommon("status.not_invoice")}` },
    { value: "extracting", label: tCommon("status.extracting") },
    { value: "extraction_failed", label: tCommon("status.extraction_failed") },
    { value: "extracted", label: tCommon("status.extracted") },
    { value: "screening_failed", label: tCommon("status.screening_failed") },
  ];

  function set<K extends keyof InvoiceListFilters>(
    key: K,
    value: InvoiceListFilters[K] | "",
  ) {
    onChange({ ...filters, offset: 0, [key]: value || null });
  }

  const countryResolved = resolveCountryToIso2(countryInput);
  const countryInvalid = countryInput.trim().length > 0 && !countryResolved;

  const hasFilters =
    filters.status || filters.direction || filters.compliance_score ||
    filters.approval_state ||
    filters.vat_note_status || filters.email_note_status ||
    filters.destination_country || filters.date_from || filters.date_to;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Status */}
      <select
        value={filters.status ?? ""}
        onChange={(e) => set("status", e.target.value as InvoiceStatus)}
        className={selectCls}
        aria-label={t("filter.all_statuses")}
      >
        <option value="">{t("filter.all_statuses")}</option>
        {statusOptions.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      {/* Retning */}
      <select
        value={filters.direction ?? ""}
        onChange={(e) => set("direction", e.target.value as InvoiceDirection)}
        className={selectCls}
      >
        <option value="">{t("filter.all_directions")}</option>
        <option value="incoming">{tCommon("direction.incoming_full")}</option>
        <option value="outgoing">{tCommon("direction.outgoing_full")}</option>
      </select>

      {/* Compliance */}
      <select
        value={filters.compliance_score ?? ""}
        onChange={(e) => set("compliance_score", e.target.value as ComplianceScore)}
        className={selectCls}
      >
        <option value="">{t("filter.all_compliance")}</option>
        <option value="green">{t("filter.compliance_green")}</option>
        <option value="yellow">{t("filter.compliance_yellow")}</option>
        <option value="red">{t("filter.compliance_red")}</option>
      </select>

      {/* Godkjenning */}
      <select
        value={filters.approval_state ?? ""}
        onChange={(e) => set("approval_state", e.target.value as ApprovalState)}
        className={selectCls}
      >
        <option value="">{t("filter.all_approval")}</option>
        <option value="pending">{t("table.approval_pending")}</option>
        <option value="approved">{t("table.approval_approved")}</option>
        <option value="blocked">{t("table.approval_blocked")}</option>
        <option value="not_required">{t("table.approval_not_required")}</option>
        <option value="assessing">{t("table.approval_assessing")}</option>
      </select>

      {/* Moms-merknad */}
      <select
        value={filters.vat_note_status ?? ""}
        onChange={(e) => set("vat_note_status", e.target.value as "ok" | "warn" | "error")}
        className={selectCls}
      >
        <option value="">{t("filter.all_vat")}</option>
        <option value="ok">{t("note.ok")}</option>
        <option value="warn">{t("note.warn")}</option>
        <option value="error">{t("note.error")}</option>
      </select>

      {/* Epost-merknad */}
      <select
        value={filters.email_note_status ?? ""}
        onChange={(e) => set("email_note_status", e.target.value as "ok" | "warn" | "error")}
        className={selectCls}
      >
        <option value="">{t("filter.all_email")}</option>
        <option value="ok">{t("note.ok")}</option>
        <option value="warn">{t("note.warn")}</option>
        <option value="error">{t("note.error")}</option>
      </select>

      {/* Land */}
      <CountryAutocomplete
        value={countryInput}
        onChange={(e) => {
          const next = e;
          setCountryInput(next);
          const resolved = resolveCountryToIso2(next);
          set("destination_country", resolved);
        }}
        placeholder={t("filter.country_placeholder")}
        className={clsx(selectCls, "w-48")}
      />
      {countryInvalid && (
        <p className="text-xs text-traffic-red">{t("filter.country_invalid")}</p>
      )}

      {/* Dato fra */}
      <input
        type="date"
        value={filters.date_from ?? ""}
        onChange={(e) => set("date_from", e.target.value)}
        className={selectCls}
      />

      {/* Dato til */}
      <input
        type="date"
        value={filters.date_to ?? ""}
        onChange={(e) => set("date_to", e.target.value)}
        className={selectCls}
      />

      {/* Nullstill */}
      {hasFilters && (
        <button
          onClick={() => {
            setCountryInput("");
            onChange({
              limit: filters.limit,
              offset: 0,
              sort_by: filters.sort_by ?? "created_at",
              sort_dir: filters.sort_dir ?? "desc",
            });
          }}
          className="rounded px-2 py-1 text-xs text-xlent-muted underline hover:text-xlent-ink"
        >
          {t("filter.reset")}
        </button>
      )}

      {/* Sortering */}
      <select
        value={filters.sort_by ?? "created_at"}
        onChange={(e) => set("sort_by", e.target.value)}
        className={selectCls}
      >
        <option value="created_at">{t("sort.created_at")}</option>
        <option value="invoice_date">{t("sort.invoice_date")}</option>
        <option value="total_amount">{t("sort.amount")}</option>
        <option value="status">{t("sort.status")}</option>
        <option value="compliance_score">{t("sort.compliance")}</option>
        <option value="approval_state">{t("sort.approval")}</option>
        <option value="vat_note_status">{t("sort.vat")}</option>
        <option value="email_note_status">{t("sort.email")}</option>
        <option value="llm_note_preview">{t("sort.llm")}</option>
        <option value="original_filename">{t("sort.filename")}</option>
      </select>
      <select
        value={filters.sort_dir ?? "desc"}
        onChange={(e) => set("sort_dir", e.target.value as "asc" | "desc")}
        className={selectCls}
      >
        <option value="desc">{t("sort.desc")}</option>
        <option value="asc">{t("sort.asc")}</option>
      </select>
    </div>
  );
}

// ── Hoved-komponent ───────────────────────────────────────────────────────────

export function InvoiceList() {
  const { can, user } = useAuth();
  const { t, i18n } = useTranslation("invoices");
  const tCommon = useTranslation("common").t;

  const [filters, setFilters] = useState<InvoiceListFilters>({
    limit: 50,
    offset: 0,
    sort_by: "created_at",
    sort_dir: "desc",
  });
  const { data, isLoading, error } = useInvoiceList(filters);
  const { data: sanctionsStatus, isLoading: sanctionsStatusLoading } = useSanctionsStatus(true);
  const preferencesQuery = useInvoiceListPreferences(user.id, true);
  const savePreferences = useUpdateInvoiceListPreferences(user.id);
  const deleteInvoice = useDeleteInvoice();
  const tableScrollerRef = useRef<HTMLDivElement | null>(null);
  const [fixedScrollbarVisible, setFixedScrollbarVisible] = useState(false);
  const [tableScrollLeft, setTableScrollLeft] = useState(0);
  const [tableMaxScroll, setTableMaxScroll] = useState(0);
  const [colWidths, setColWidths] = useState<Record<InvoiceTableColumnKey, number>>(() => loadSavedColWidths(user.id));
  const [customPresets, setCustomPresets] = useState<ColumnPreset[]>(() => loadCustomPresets(user.id));
  const [activePresetId, setActivePresetId] = useState<string>("balanced");
  const [preferencesHydrated, setPreferencesHydrated] = useState(false);
  const lastSavedPrefSignatureRef = useRef<string>("");

  useEffect(() => {
    setColWidths(loadSavedColWidths(user.id));
    setCustomPresets(loadCustomPresets(user.id));
    setActivePresetId("balanced");
    setPreferencesHydrated(false);
    lastSavedPrefSignatureRef.current = "";
  }, [user.id]);

  useEffect(() => {
    if (preferencesHydrated) return;
    const pref = preferencesQuery.data;
    if (!pref) return;
    const widths = pref.table_col_widths ?? {};
    if (Object.keys(widths).length > 0) {
      setColWidths(normalizeWidths(widths as Partial<Record<InvoiceTableColumnKey, number>>));
    }
    const rawPresets = Array.isArray(pref.table_col_presets) ? pref.table_col_presets : [];
    const parsedPresets: ColumnPreset[] = [];
    for (const row of rawPresets) {
      const id = typeof row.id === "string" ? row.id : null;
      if (!id) continue;
      const label = typeof row.label === "string" ? row.label : undefined;
      const widthsRaw =
        row.widths && typeof row.widths === "object"
          ? (row.widths as Partial<Record<InvoiceTableColumnKey, number>>)
          : undefined;
      parsedPresets.push({
        id,
        label,
        widths: normalizeWidths(widthsRaw),
      });
    }
    if (parsedPresets.length > 0) {
      setCustomPresets(parsedPresets);
    }
    const serverWidths =
      Object.keys(widths).length > 0
        ? normalizeWidths(widths as Partial<Record<InvoiceTableColumnKey, number>>)
        : DEFAULT_COL_WIDTHS;
    lastSavedPrefSignatureRef.current = preferencePayloadSignature(
      buildPreferencePayload(
        serverWidths,
        parsedPresets,
      ),
    );
    setPreferencesHydrated(true);
  }, [preferencesHydrated, preferencesQuery.data]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(colWidthStorageKey(user.id), JSON.stringify(colWidths));
  }, [colWidths, user.id]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(colPresetStorageKey(user.id), JSON.stringify(customPresets));
  }, [customPresets, user.id]);

  useEffect(() => {
    if (!preferencesHydrated) return;
    const payload = buildPreferencePayload(colWidths, customPresets);
    const nextSignature = preferencePayloadSignature(payload);
    if (nextSignature === lastSavedPrefSignatureRef.current) {
      return;
    }
    const timer = window.setTimeout(() => {
      savePreferences.mutate(payload, {
        onSuccess: () => {
          lastSavedPrefSignatureRef.current = nextSignature;
        },
      });
    }, 700);
    return () => window.clearTimeout(timer);
  }, [colWidths, customPresets, preferencesHydrated, savePreferences]);

  useEffect(() => {
    function updateScrollbarState() {
      const tableScroller = tableScrollerRef.current;
      if (!tableScroller) {
        setFixedScrollbarVisible(false);
        setTableMaxScroll(0);
        setTableScrollLeft(0);
        return;
      }
      const maxScroll = Math.max(0, tableScroller.scrollWidth - tableScroller.clientWidth);
      setTableMaxScroll(maxScroll);
      setFixedScrollbarVisible(maxScroll > 0);
      setTableScrollLeft(Math.min(tableScroller.scrollLeft, maxScroll));
    }

    updateScrollbarState();
    window.addEventListener("resize", updateScrollbarState);
    return () => window.removeEventListener("resize", updateScrollbarState);
  }, [data, colWidths]);

  function handleTableScroll() {
    const tableScroller = tableScrollerRef.current;
    if (!tableScroller) return;
    setTableScrollLeft(tableScroller.scrollLeft);
  }

  function handleFixedSliderChange(nextValue: number) {
    const tableScroller = tableScrollerRef.current;
    if (!tableScroller) return;
    tableScroller.scrollLeft = nextValue;
    setTableScrollLeft(nextValue);
  }

  function startColumnResize(column: InvoiceTableColumnKey, startClientX: number) {
    const startWidth = colWidths[column];
    const minWidth = MIN_COL_WIDTHS[column];
    const previousUserSelect = document.body.style.userSelect;
    const previousCursor = document.body.style.cursor;
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";

    function onMouseMove(event: MouseEvent) {
      const delta = event.clientX - startClientX;
      const next = Math.max(minWidth, Math.round(startWidth + delta));
      setColWidths((prev) => {
        if (prev[column] === next) return prev;
        return { ...prev, [column]: next };
      });
    }

    function onMouseUp() {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      document.body.style.userSelect = previousUserSelect;
      document.body.style.cursor = previousCursor;
    }

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }

  const availablePresets = [...BUILTIN_PRESETS, ...customPresets];

  function presetLabel(preset: ColumnPreset): string {
    if (preset.id === "balanced") return t("table.preset_balanced");
    if (preset.id === "compact") return t("table.preset_compact");
    if (preset.id === "review_focus") return t("table.preset_review_focus");
    return preset.label ?? t("table.preset_custom_label");
  }

  function applyPreset(presetId: string) {
    const preset = availablePresets.find((row) => row.id === presetId);
    if (!preset) return;
    setColWidths(preset.widths);
    setActivePresetId(preset.id);
  }

  function saveCurrentAsPreset() {
    const baseLabel = t("table.preset_custom_label");
    const nextIndex = customPresets.length + 1;
    const id = `custom_${Date.now()}`;
    const preset: ColumnPreset = {
      id,
      label: `${baseLabel} ${nextIndex}`,
      widths: colWidths,
    };
    setCustomPresets((prev) => [...prev, preset]);
    setActivePresetId(preset.id);
  }

  function resetColWidths() {
    setColWidths(DEFAULT_COL_WIDTHS);
    setActivePresetId("balanced");
  }

  function handleDelete(id: string, filename: string | null) {
    const label = filename ?? id;
    if (!window.confirm(t("table.delete_confirm", { name: label }))) {
      return;
    }
    deleteInvoice.mutate(id);
  }

  const locale = i18n.language === "en" ? "en-GB" : "nb-NO";
  const limit = filters.limit ?? 50;
  const offset = filters.offset ?? 0;
  const total = data?.total ?? 0;
  const externalSources = sanctionsStatus?.external_sources ?? [];
  const driftSources = externalSources.filter(
    (row) => row.status !== "ok" || row.stale || row.error_message,
  );
  const okSources = externalSources.length - driftSources.length;
  const latestExternalUpdate = externalSources
    .map((row) => row.last_updated)
    .filter((value): value is string => Boolean(value))
    .map((value) => new Date(value))
    .filter((value) => !Number.isNaN(value.getTime()))
    .sort((a, b) => b.getTime() - a.getTime())[0];

  return (
    <div className="mx-auto max-w-5xl space-y-8 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-xlent-ink">{t("page.title")}</h1>
        <p className="mt-1 text-sm text-xlent-muted">{t("page.subtitle")}</p>
      </header>

      <section className="rounded-lg border border-gray-200 bg-white p-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
            {t("ingest.title")}
          </h2>
          <details className="relative">
            <summary
              className="list-none cursor-pointer rounded border border-gray-200 px-2 py-1 text-sm text-xlent-muted hover:bg-gray-50 hover:text-xlent-ink"
              title={t("ingest.title")}
            >
              ⋯
            </summary>
            <div className="absolute right-0 z-20 mt-2 w-[360px] rounded border border-gray-200 bg-white p-3 shadow-lg">
              <p className="text-xs text-xlent-muted">
                {t("ingest.sources")}{" "}
                <span className={driftSources.length === 0 ? "text-green-700" : "text-amber-700"}>
                  {sanctionsStatusLoading
                    ? t("ingest.checking")
                    : t("ingest.ok_format", { ok: okSources, total: externalSources.length || 0 })}
                </span>
                {" · "}
                {t("ingest.schedule")} {sanctionsStatus?.external_refresh_schedule_time ?? "07:45"}{" "}
                {sanctionsStatus?.refresh_schedule_timezone ?? "Europe/Oslo"}
              </p>
              <p className="mt-1 text-xs text-xlent-muted">
                {t("ingest.last_updated")}{" "}
                {latestExternalUpdate
                  ? latestExternalUpdate.toLocaleString(locale)
                  : t("ingest.unknown")}
              </p>
              {driftSources.length > 0 && (
                <p className="mt-1 text-xs text-amber-800">
                  {t("ingest.warning_prefix")} {driftSources.map((row) => row.source).join(", ")}
                </p>
              )}
              <div className="mt-2">
                <Link
                  to="/sanctioned-entities"
                  className="rounded border border-gray-200 px-2 py-1 text-xs text-xlent-muted hover:bg-gray-50 hover:text-xlent-ink"
                >
                  {t("ingest.open_details")}
                </Link>
              </div>
            </div>
          </details>
        </div>
      </section>

      <section
        className={clsx(
          "rounded-lg border bg-white p-4",
          can("invoices:upload") ? "border-gray-200" : "border-gray-100 opacity-50",
        )}
      >
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-xlent-muted">
          {t("upload.section_title")}
          {!can("invoices:upload") && (
            <span className="ml-2 font-normal normal-case text-gray-400">
              {t("upload.unavailable")}
            </span>
          )}
        </h2>
        {can("invoices:upload") ? (
          <InvoiceUploader />
        ) : (
          <p className="text-sm text-gray-400">{t("upload.role_required")}</p>
        )}
      </section>

      <section>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-xlent-muted">
            {t("table.section_title")}
            {total > 0 && (
              <span className="ml-2 font-normal normal-case text-xlent-muted/60">
                {t("table.total", { count: total })}
              </span>
            )}
          </h2>
          <CsvExportButton filters={filters} />
        </div>

        <div className="mb-3">
          <FilterBar filters={filters} onChange={setFilters} />
        </div>
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
          <label className="text-xlent-muted">{t("table.preset_label")}</label>
          <select
            value={activePresetId}
            onChange={(e) => applyPreset(e.target.value)}
            className="rounded border border-gray-200 bg-white px-2 py-1 text-xs text-xlent-ink"
          >
            {availablePresets.map((preset) => (
              <option key={preset.id} value={preset.id}>
                {presetLabel(preset)}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={saveCurrentAsPreset}
            className="rounded border border-gray-200 bg-white px-2 py-1 text-xs text-xlent-muted hover:bg-gray-50 hover:text-xlent-ink"
          >
            {t("table.preset_save")}
          </button>
          <button
            type="button"
            onClick={resetColWidths}
            className="rounded border border-gray-200 bg-white px-2 py-1 text-xs text-xlent-muted hover:bg-gray-50 hover:text-xlent-ink"
          >
            {t("table.preset_reset")}
          </button>
        </div>

        {isLoading && <p className="text-sm text-xlent-muted">{tCommon("loading")}</p>}
        {error && (
          <p className="text-sm text-traffic-red">{t("table.error")}</p>
        )}

        {data && (
          <>
            {fixedScrollbarVisible && tableMaxScroll > 0 && (
              <div className="sticky top-2 z-20 mb-2 rounded border border-gray-200 bg-white/95 px-3 py-2 shadow-sm backdrop-blur">
                <label className="mb-1 block text-[11px] text-xlent-muted">
                  {t("table.scroll_label")}
                </label>
                <input
                  type="range"
                  min={0}
                  max={tableMaxScroll}
                  value={tableScrollLeft}
                  onChange={(e) => handleFixedSliderChange(Number(e.target.value))}
                  className="w-full"
                  aria-label={t("table.scroll_label")}
                />
              </div>
            )}
            <div
              ref={tableScrollerRef}
              onScroll={handleTableScroll}
              className="overflow-x-auto overflow-y-hidden rounded-lg border border-gray-200 bg-white"
            >
              <table className="min-w-[1930px] divide-y divide-gray-200 text-sm">
                <colgroup>
                  <col style={{ width: `${colWidths.signal}px` }} />
                  <col style={{ width: `${colWidths.file}px` }} />
                  <col style={{ width: `${colWidths.direction}px` }} />
                  <col style={{ width: `${colWidths.status}px` }} />
                  <col style={{ width: `${colWidths.approval}px` }} />
                  <col style={{ width: `${colWidths.vat}px` }} />
                  <col style={{ width: `${colWidths.email}px` }} />
                  <col style={{ width: `${colWidths.llm}px` }} />
                  <col style={{ width: `${colWidths.invoice_date}px` }} />
                  <col style={{ width: `${colWidths.amount}px` }} />
                  <col style={{ width: `${colWidths.created_at}px` }} />
                  <col style={{ width: `${colWidths.actions}px` }} />
                </colgroup>
                <thead className="bg-xlent-surface text-left text-xs uppercase text-xlent-muted">
                  <tr>
                    <th className="group sticky top-0 z-10 bg-xlent-surface relative px-3 py-2" title={t("table.col_compliance")}>
                      <button
                        type="button"
                        onMouseDown={(e) => { e.preventDefault(); startColumnResize("signal", e.clientX); }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label={`${t("table.resize_prefix")}${t("table.col_compliance")}`}
                      />
                    </th>
                    <th className="group sticky top-0 z-10 bg-xlent-surface relative px-3 py-2">
                      {t("table.col_file")}
                      <button
                        type="button"
                        onMouseDown={(e) => { e.preventDefault(); startColumnResize("file", e.clientX); }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label={`${t("table.resize_prefix")}${t("table.col_file")}`}
                      />
                    </th>
                    <th className="group sticky top-0 z-10 bg-xlent-surface relative px-3 py-2">
                      {t("table.col_direction")}
                      <button
                        type="button"
                        onMouseDown={(e) => { e.preventDefault(); startColumnResize("direction", e.clientX); }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label={`${t("table.resize_prefix")}${t("table.col_direction")}`}
                      />
                    </th>
                    <th className="group sticky top-0 z-10 bg-xlent-surface relative px-3 py-2">
                      {t("table.col_status")}
                      <button
                        type="button"
                        onMouseDown={(e) => { e.preventDefault(); startColumnResize("status", e.clientX); }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label={`${t("table.resize_prefix")}${t("table.col_status")}`}
                      />
                    </th>
                    <th className="group sticky top-0 z-10 bg-xlent-surface relative px-3 py-2">
                      {t("table.col_approval")}
                      <button
                        type="button"
                        onMouseDown={(e) => { e.preventDefault(); startColumnResize("approval", e.clientX); }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label={`${t("table.resize_prefix")}${t("table.col_approval")}`}
                      />
                    </th>
                    <th className="group sticky top-0 z-10 bg-xlent-surface relative px-3 py-2">
                      {t("table.col_vat")}
                      <button
                        type="button"
                        onMouseDown={(e) => { e.preventDefault(); startColumnResize("vat", e.clientX); }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label={`${t("table.resize_prefix")}${t("table.col_vat")}`}
                      />
                    </th>
                    <th className="group sticky top-0 z-10 bg-xlent-surface relative px-3 py-2">
                      {t("table.col_email")}
                      <button
                        type="button"
                        onMouseDown={(e) => { e.preventDefault(); startColumnResize("email", e.clientX); }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label={`${t("table.resize_prefix")}${t("table.col_email")}`}
                      />
                    </th>
                    <th className="group sticky top-0 z-10 bg-xlent-surface relative px-3 py-2">
                      {t("table.col_llm")}
                      <button
                        type="button"
                        onMouseDown={(e) => { e.preventDefault(); startColumnResize("llm", e.clientX); }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label={`${t("table.resize_prefix")}${t("table.col_llm")}`}
                      />
                    </th>
                    <th className="group sticky top-0 z-10 bg-xlent-surface relative px-3 py-2">
                      {t("table.col_invoice_date")}
                      <button
                        type="button"
                        onMouseDown={(e) => { e.preventDefault(); startColumnResize("invoice_date", e.clientX); }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label={`${t("table.resize_prefix")}${t("table.col_invoice_date")}`}
                      />
                    </th>
                    <th className="group sticky top-0 z-10 bg-xlent-surface relative px-3 py-2">
                      {t("table.col_amount")}
                      <button
                        type="button"
                        onMouseDown={(e) => { e.preventDefault(); startColumnResize("amount", e.clientX); }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label={`${t("table.resize_prefix")}${t("table.col_amount")}`}
                      />
                    </th>
                    <th className="group sticky top-0 z-10 bg-xlent-surface relative px-3 py-2">
                      {t("table.col_created_at")}
                      <button
                        type="button"
                        onMouseDown={(e) => { e.preventDefault(); startColumnResize("created_at", e.clientX); }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label={`${t("table.resize_prefix")}${t("table.col_created_at")}`}
                      />
                    </th>
                    <th className="group sticky top-0 z-10 bg-xlent-surface relative px-3 py-2">
                      <button
                        type="button"
                        onMouseDown={(e) => { e.preventDefault(); startColumnResize("actions", e.clientX); }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label={t("table.delete")}
                      />
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data.items.length === 0 && (
                    <tr>
                      <td colSpan={12} className="px-3 py-6 text-center text-xlent-muted">
                        {t("table.empty")}
                      </td>
                    </tr>
                  )}
                  {data.items.map((invoice) => (
                    <tr key={invoice.id} className="hover:bg-xlent-surface">
                      <td className="px-3 py-2">
                        <ComplianceChip invoice={invoice} />
                      </td>
                      <td className="px-3 py-2">
                        <Link
                          to={`/invoices/${invoice.id}`}
                          className="block max-w-[220px] truncate text-xlent-primary hover:underline"
                          title={invoice.original_filename ?? invoice.id}
                        >
                          {invoice.original_filename ?? invoice.id}
                        </Link>
                        {invoice.invoice_number && (
                          <span className="ml-2 text-xs text-xlent-muted">
                            #{invoice.invoice_number}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 capitalize text-xlent-muted text-xs">
                        {invoice.direction === "incoming"
                          ? tCommon("direction.incoming")
                          : tCommon("direction.outgoing")}
                      </td>
                      <td className="px-3 py-2">
                        <StatusBadge status={invoice.status} score={invoice.compliance_score} />
                      </td>
                      <td className="px-3 py-2">
                        {(() => {
                          let state: "pending" | "approved" | "blocked" | "not_required" | "assessing";
                          let label: string;
                          state = invoice.approval_state;
                          if (state === "approved") label = t("table.approval_approved");
                          else if (state === "blocked") label = t("table.approval_blocked");
                          else if (state === "pending") label = t("table.approval_pending");
                          else if (state === "not_required") label = t("table.approval_not_required");
                          else label = t("table.approval_assessing");

                          return (
                            <span
                              className={clsx(
                                "inline-flex rounded border px-1.5 py-0.5 text-[11px] font-medium",
                                approvalBadgeClass(state),
                              )}
                            >
                              {label}
                            </span>
                          );
                        })()}
                      </td>
                      <td className="px-3 py-2">
                        <div className="space-y-1">
                          <span
                            className={clsx(
                              "inline-flex rounded border px-1.5 py-0.5 text-[11px] font-medium",
                              noteClass(invoice.vat_note_status),
                            )}
                          >
                            {invoice.vat_note_status === "error"
                              ? t("note.error")
                              : invoice.vat_note_status === "warn"
                                ? t("note.warn")
                                : t("note.ok")}
                          </span>
                          <div className="max-w-[220px] text-xs text-xlent-muted" title={invoice.vat_note_text ?? ""}>
                            {shortText(invoice.vat_note_text)}
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <div className="space-y-1">
                          <span
                            className={clsx(
                              "inline-flex rounded border px-1.5 py-0.5 text-[11px] font-medium",
                              noteClass(invoice.email_note_status),
                            )}
                          >
                            {invoice.email_note_status === "error"
                              ? t("note.error")
                              : invoice.email_note_status === "warn"
                                ? t("note.warn")
                                : t("note.ok")}
                          </span>
                          <div className="max-w-[220px] text-xs text-xlent-muted" title={invoice.email_note_text ?? ""}>
                            {shortText(invoice.email_note_text)}
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-2 text-xs text-xlent-muted">
                        <div className="max-w-[260px]" title={invoice.llm_note_full ?? invoice.llm_note_preview ?? ""}>
                          {shortText(invoice.llm_note_preview, 120)}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-xlent-muted text-xs">
                        {invoice.invoice_date ?? "—"}
                      </td>
                      <td className="px-3 py-2 text-xs tabular-nums text-xlent-muted">
                        {invoice.total_amount
                          ? `${invoice.total_amount} ${invoice.currency ?? ""}`
                          : "—"}
                      </td>
                      <td className="px-3 py-2 text-xlent-muted text-xs">
                        {new Date(invoice.created_at).toLocaleString(locale, {
                          dateStyle: "short",
                          timeStyle: "short",
                        })}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          onClick={() => handleDelete(invoice.id, invoice.original_filename)}
                          disabled={deleteInvoice.isPending}
                          className="rounded px-2 py-0.5 text-xs text-traffic-red hover:bg-red-50 disabled:opacity-40"
                          title={t("table.delete_title")}
                        >
                          {t("table.delete")}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-xlent-muted">{t("table.tip")}</p>

            <Pagination
              total={total}
              limit={limit}
              offset={offset}
              onPrev={() => setFilters((f) => ({ ...f, offset: Math.max(0, offset - limit) }))}
              onNext={() => setFilters((f) => ({ ...f, offset: offset + limit }))}
            />
          </>
        )}
      </section>
    </div>
  );
}
