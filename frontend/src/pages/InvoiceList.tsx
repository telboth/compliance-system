import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";

import { apiClient } from "@/api/client";

import { useAuth } from "@/auth/AuthContext";
import { InvoiceUploader } from "@/components/InvoiceUploader";
import { Pagination } from "@/components/Pagination";
import { StatusBadge } from "@/components/StatusBadge";
import { ComplianceChip } from "@/components/ComplianceBadge";
import {
  useDeleteInvoice,
  useInvoiceList,
  useSanctionsStatus,
  type InvoiceListFilters,
} from "@/hooks/useInvoices";
import type { ComplianceScore, InvoiceDirection, InvoiceStatus } from "@/api/types";
import { ALL_COUNTRY_RISKS } from "@/data/countryRisk";

type InvoiceTableColumnKey =
  | "signal"
  | "file"
  | "direction"
  | "status"
  | "vat"
  | "email"
  | "llm"
  | "invoice_date"
  | "amount"
  | "created_at"
  | "actions";

const COL_WIDTH_STORAGE_KEY = "invoice_table_col_widths_v2";

const DEFAULT_COL_WIDTHS: Record<InvoiceTableColumnKey, number> = {
  signal: 130,
  file: 220,
  direction: 90,
  status: 130,
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
  vat: 160,
  email: 170,
  llm: 220,
  invoice_date: 100,
  amount: 100,
  created_at: 120,
  actions: 60,
};

function loadSavedColWidths(): Record<InvoiceTableColumnKey, number> {
  if (typeof window === "undefined") {
    return DEFAULT_COL_WIDTHS;
  }
  try {
    const raw = window.localStorage.getItem(COL_WIDTH_STORAGE_KEY);
    if (!raw) return DEFAULT_COL_WIDTHS;
    const parsed = JSON.parse(raw) as Partial<Record<InvoiceTableColumnKey, number>>;
    return {
      signal: Number(parsed.signal) || DEFAULT_COL_WIDTHS.signal,
      file: Number(parsed.file) || DEFAULT_COL_WIDTHS.file,
      direction: Number(parsed.direction) || DEFAULT_COL_WIDTHS.direction,
      status: Number(parsed.status) || DEFAULT_COL_WIDTHS.status,
      vat: Number(parsed.vat) || DEFAULT_COL_WIDTHS.vat,
      email: Number(parsed.email) || DEFAULT_COL_WIDTHS.email,
      llm: Number(parsed.llm) || DEFAULT_COL_WIDTHS.llm,
      invoice_date: Number(parsed.invoice_date) || DEFAULT_COL_WIDTHS.invoice_date,
      amount: Number(parsed.amount) || DEFAULT_COL_WIDTHS.amount,
      created_at: Number(parsed.created_at) || DEFAULT_COL_WIDTHS.created_at,
      actions: Number(parsed.actions) || DEFAULT_COL_WIDTHS.actions,
    };
  } catch {
    return DEFAULT_COL_WIDTHS;
  }
}

type NoteStatus = "ok" | "warn" | "error" | null;

function noteBadge(status: NoteStatus): { label: string; cls: string } {
  if (status === "error") {
    return { label: "Feil", cls: "bg-red-100 text-red-800 border-red-200" };
  }
  if (status === "warn") {
    return { label: "Varsel", cls: "bg-amber-100 text-amber-800 border-amber-200" };
  }
  return { label: "OK", cls: "bg-green-100 text-green-800 border-green-200" };
}

function shortText(value: string | null | undefined, max = 90): string {
  const text = (value ?? "").trim();
  if (!text) return "—";
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

// ── CSV-eksport ───────────────────────────────────────────────────────────────

function CsvExportButton({ filters }: { filters: InvoiceListFilters }) {
  const [busy, setBusy] = useState(false);

  async function handleExport() {
    setBusy(true);
    try {
      const params = new URLSearchParams();
      if (filters.status) params.set("status_filter", filters.status);
      if (filters.direction) params.set("direction", filters.direction);
      if (filters.compliance_score) params.set("compliance_score", filters.compliance_score);
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
      alert("Kunne ikke eksportere CSV. Prøv igjen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      onClick={handleExport}
      disabled={busy}
      className="flex items-center gap-1.5 rounded border border-gray-200 bg-white px-3 py-1.5 text-xs text-xlent-muted hover:bg-gray-50 hover:text-xlent-ink disabled:opacity-50"
      title="Eksporter fakturaliste som CSV (åpnes i Excel)"
    >
      {busy ? "⏳ Eksporterer…" : "⬇ CSV"}
    </button>
  );
}

// ── Filterrad ─────────────────────────────────────────────────────────────────

const STATUS_OPTIONS: { value: InvoiceStatus; label: string }[] = [
  { value: "uploaded", label: "Lastet opp" },
  { value: "parsing", label: "Parser" },
  { value: "parsed", label: "Parset" },
  { value: "parsing_failed", label: "Parsing feilet" },
  { value: "not_invoice", label: "⚠️ Ikke faktura" },
  { value: "extracting", label: "Ekstraherer" },
  { value: "extraction_failed", label: "Ekstraksjon feilet" },
  { value: "extracted", label: "Ekstrahert" },
  { value: "screening_failed", label: "Screening feilet" },
];

const selectCls =
  "rounded border border-gray-200 bg-white px-2 py-1 text-xs text-xlent-ink focus:outline-none focus:ring-1 focus:ring-xlent-primary";

interface FilterBarProps {
  filters: InvoiceListFilters;
  onChange: (f: InvoiceListFilters) => void;
}

function _normalizeCountryName(raw: string): string {
  return raw
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z]/g, "");
}

function _buildCountryNameLookup(): Map<string, string> {
  const codes = new Set<string>(Object.keys(ALL_COUNTRY_RISKS));
  const lookup = new Map<string, string>();
  const locales = ["en", "nb", "no"] as const;

  for (const code of codes) {
    lookup.set(code.toLowerCase(), code);
    for (const locale of locales) {
      try {
        const dn = new Intl.DisplayNames([locale], { type: "region" });
        const name = dn.of(code);
        if (!name) continue;
        const key = _normalizeCountryName(name);
        if (key) lookup.set(key, code);
      } catch {
        // Ignorer locale-feil i eldre nettlesere.
      }
    }
  }

  // Vanlige alias og skrivemåter.
  lookup.set("usa", "US");
  lookup.set("unitedstates", "US");
  lookup.set("uk", "GB");
  lookup.set("greatbritain", "GB");
  lookup.set("storbritannia", "GB");
  lookup.set("england", "GB");
  lookup.set("northkorea", "KP");
  lookup.set("nordkorea", "KP");
  lookup.set("russia", "RU");
  lookup.set("russland", "RU");
  lookup.set("frankrike", "FR");
  lookup.set("frankriket", "FR");
  lookup.set("france", "FR");

  return lookup;
}

function resolveCountryFilter(raw: string, lookup: Map<string, string>): string {
  const trimmed = raw.trim();
  if (!trimmed) return "";

  const isoCandidate = trimmed.toUpperCase().replace(/[^A-Z]/g, "");
  if (isoCandidate.length === 2) return isoCandidate;

  const norm = _normalizeCountryName(trimmed);
  if (!norm) return "";

  const direct = lookup.get(norm);
  if (direct) return direct;

  // Norsk bestemt form/endinger ("-et", "-en", "-a") og enkel plural.
  const suffixCandidates = [norm];
  if (norm.endsWith("et") && norm.length > 4) suffixCandidates.push(norm.slice(0, -2));
  if (norm.endsWith("en") && norm.length > 4) suffixCandidates.push(norm.slice(0, -2));
  if (norm.endsWith("a") && norm.length > 4) suffixCandidates.push(norm.slice(0, -1));
  if (norm.endsWith("s") && norm.length > 4) suffixCandidates.push(norm.slice(0, -1));

  for (const key of suffixCandidates) {
    const match = lookup.get(key);
    if (match) return match;
  }
  return "";
}

function FilterBar({ filters, onChange }: FilterBarProps) {
  const countryLookup = useMemo(_buildCountryNameLookup, []);

  function set<K extends keyof InvoiceListFilters>(
    key: K,
    value: InvoiceListFilters[K] | "",
  ) {
    onChange({ ...filters, offset: 0, [key]: value || null });
  }

  const hasFilters =
    filters.status || filters.direction || filters.compliance_score ||
    filters.vat_note_status || filters.email_note_status ||
    filters.destination_country || filters.date_from || filters.date_to;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Status */}
      <select
        value={filters.status ?? ""}
        onChange={(e) => set("status", e.target.value as InvoiceStatus)}
        className={selectCls}
        aria-label="Filtrer status"
      >
        <option value="">Alle statuser</option>
        {STATUS_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      {/* Retning */}
      <select
        value={filters.direction ?? ""}
        onChange={(e) => set("direction", e.target.value as InvoiceDirection)}
        className={selectCls}
        aria-label="Filtrer retning"
      >
        <option value="">Innkommende + utgående</option>
        <option value="incoming">Innkommende</option>
        <option value="outgoing">Utgående</option>
      </select>

      {/* Compliance */}
      <select
        value={filters.compliance_score ?? ""}
        onChange={(e) => set("compliance_score", e.target.value as ComplianceScore)}
        className={selectCls}
        aria-label="Filtrer compliance"
      >
        <option value="">Alle compliance-statuser</option>
        <option value="green">🟢 Grønt</option>
        <option value="yellow">🟡 Gult</option>
        <option value="red">🔴 Rødt</option>
      </select>

      {/* Moms-merknad */}
      <select
        value={filters.vat_note_status ?? ""}
        onChange={(e) => set("vat_note_status", e.target.value as "ok" | "warn" | "error")}
        className={selectCls}
        aria-label="Filtrer moms-merknad"
      >
        <option value="">Alle moms-merknader</option>
        <option value="ok">OK</option>
        <option value="warn">Varsel</option>
        <option value="error">Feil</option>
      </select>

      {/* Epost-merknad */}
      <select
        value={filters.email_note_status ?? ""}
        onChange={(e) => set("email_note_status", e.target.value as "ok" | "warn" | "error")}
        className={selectCls}
        aria-label="Filtrer epost-merknad"
      >
        <option value="">Alle epost-merknader</option>
        <option value="ok">OK</option>
        <option value="warn">Varsel</option>
        <option value="error">Feil</option>
      </select>

      {/* Land */}
      <input
        type="text"
        value={filters.destination_country ?? ""}
        onChange={(e) => set("destination_country", resolveCountryFilter(e.target.value, countryLookup))}
        placeholder="Land (FR / France / Frankrike)"
        className={clsx(selectCls, "w-48")}
        aria-label="Filtrer destinasjonsland"
      />

      {/* Dato fra */}
      <input
        type="date"
        value={filters.date_from ?? ""}
        onChange={(e) => set("date_from", e.target.value)}
        className={selectCls}
        aria-label="Fakturadato fra"
        title="Fakturadato fra og med"
      />

      {/* Dato til */}
      <input
        type="date"
        value={filters.date_to ?? ""}
        onChange={(e) => set("date_to", e.target.value)}
        className={selectCls}
        aria-label="Fakturadato til"
        title="Fakturadato til og med"
      />

      {/* Nullstill */}
      {hasFilters && (
        <button
          onClick={() =>
            onChange({
              limit: filters.limit,
              offset: 0,
              sort_by: filters.sort_by ?? "created_at",
              sort_dir: filters.sort_dir ?? "desc",
            })
          }
          className="rounded px-2 py-1 text-xs text-xlent-muted underline hover:text-xlent-ink"
        >
          Nullstill
        </button>
      )}

      {/* Sortering */}
      <select
        value={filters.sort_by ?? "created_at"}
        onChange={(e) => set("sort_by", e.target.value)}
        className={selectCls}
        aria-label="Sorter etter"
      >
        <option value="created_at">Sorter: Opprettet</option>
        <option value="invoice_date">Sorter: Fakturadato</option>
        <option value="total_amount">Sorter: Beløp</option>
        <option value="status">Sorter: Status</option>
        <option value="compliance_score">Sorter: Compliance</option>
        <option value="vat_note_status">Sorter: Moms-merknad</option>
        <option value="email_note_status">Sorter: Epost-merknad</option>
        <option value="llm_note_preview">Sorter: LLM-merknad</option>
        <option value="original_filename">Sorter: Filnavn</option>
      </select>
      <select
        value={filters.sort_dir ?? "desc"}
        onChange={(e) => set("sort_dir", e.target.value as "asc" | "desc")}
        className={selectCls}
        aria-label="Sorteringsretning"
      >
        <option value="desc">Nyeste først</option>
        <option value="asc">Eldste først</option>
      </select>
    </div>
  );
}

// ── Hoved-komponent ───────────────────────────────────────────────────────────

export function InvoiceList() {
  const { can } = useAuth();
  const [filters, setFilters] = useState<InvoiceListFilters>({
    limit: 50,
    offset: 0,
    sort_by: "created_at",
    sort_dir: "desc",
  });
  const { data, isLoading, error } = useInvoiceList(filters);
  const { data: sanctionsStatus, isLoading: sanctionsStatusLoading } = useSanctionsStatus(true);
  const deleteInvoice = useDeleteInvoice();
  const tableScrollerRef = useRef<HTMLDivElement | null>(null);
  const [fixedScrollbarVisible, setFixedScrollbarVisible] = useState(false);
  const [tableScrollLeft, setTableScrollLeft] = useState(0);
  const [tableMaxScroll, setTableMaxScroll] = useState(0);
  const [colWidths, setColWidths] = useState<Record<InvoiceTableColumnKey, number>>(
    loadSavedColWidths,
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(COL_WIDTH_STORAGE_KEY, JSON.stringify(colWidths));
  }, [colWidths]);

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

  function handleDelete(id: string, filename: string | null) {
    const label = filename ?? id;
    if (!window.confirm(`Slett «${label}»?\n\nFilen og alle ekstraherte data fjernes permanent.`)) {
      return;
    }
    deleteInvoice.mutate(id);
  }

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
        <h1 className="text-2xl font-semibold text-xlent-ink">Invoices</h1>
        <p className="mt-1 text-sm text-xlent-muted">
          Last opp en PDF, XLSX eller PNG. Parsing og LLM-ekstraksjon skjer automatisk
          i bakgrunnen — du sendes til detaljsiden og ser status oppdatere seg løpende.
        </p>
      </header>

      <section className="rounded-lg border border-gray-200 bg-white p-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
            Ingest drift
          </h2>
          <details className="relative">
            <summary
              className="list-none cursor-pointer rounded border border-gray-200 px-2 py-1 text-sm text-xlent-muted hover:bg-gray-50 hover:text-xlent-ink"
              aria-label="Vis ingest drift detaljer"
              title="Vis ingest drift"
            >
              ⋯
            </summary>
            <div className="absolute right-0 z-20 mt-2 w-[360px] rounded border border-gray-200 bg-white p-3 shadow-lg">
              <p className="text-xs text-xlent-muted">
                Eksterne kilder:{" "}
                <span className={driftSources.length === 0 ? "text-green-700" : "text-amber-700"}>
                  {sanctionsStatusLoading
                    ? "Sjekker …"
                    : `${okSources}/${externalSources.length || 0} ok`}
                </span>
                {" · "}
                Plan: {sanctionsStatus?.external_refresh_schedule_time ?? "07:45"}{" "}
                {sanctionsStatus?.refresh_schedule_timezone ?? "Europe/Oslo"}
              </p>
              <p className="mt-1 text-xs text-xlent-muted">
                Sist oppdatert:{" "}
                {latestExternalUpdate ? latestExternalUpdate.toLocaleString("nb-NO") : "Ukjent"}
              </p>
              {driftSources.length > 0 && (
                <p className="mt-1 text-xs text-amber-800">
                  Varsel: {driftSources.map((row) => row.source).join(", ")}
                </p>
              )}
              <div className="mt-2">
                <Link
                  to="/sanctioned-entities"
                  className="rounded border border-gray-200 px-2 py-1 text-xs text-xlent-muted hover:bg-gray-50 hover:text-xlent-ink"
                >
                  Åpne detaljer
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
          Last opp invoice
          {!can("invoices:upload") && (
            <span
              className="ml-2 font-normal normal-case text-gray-400"
              title="Du har ikke tilgang til å laste opp fakturaer med din nåværende rolle"
            >
              (ikke tilgjengelig for din rolle)
            </span>
          )}
        </h2>
        {can("invoices:upload") ? (
          <InvoiceUploader />
        ) : (
          <p className="text-sm text-gray-400">
            Bytt til controller-rollen eller høyere for å laste opp fakturaer.
          </p>
        )}
      </section>

      <section>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-xlent-muted">
            Alle invoices
            {total > 0 && (
              <span className="ml-2 font-normal normal-case text-xlent-muted/60">
                ({total} totalt)
              </span>
            )}
          </h2>
          <CsvExportButton filters={filters} />
        </div>

        {/* Filter-rad */}
        <div className="mb-3">
          <FilterBar filters={filters} onChange={setFilters} />
        </div>

        {isLoading && <p className="text-sm text-xlent-muted">Laster …</p>}
        {error && (
          <p className="text-sm text-traffic-red">
            Kunne ikke laste invoices. Sjekk at API-et kjører.
          </p>
        )}

        {data && (
          <>
            {fixedScrollbarVisible && tableMaxScroll > 0 && (
              <div className="sticky top-2 z-20 mb-2 rounded border border-gray-200 bg-white/95 px-3 py-2 shadow-sm backdrop-blur">
                <label className="mb-1 block text-[11px] text-xlent-muted">
                  Horisontal tabellscroll
                </label>
                <input
                  type="range"
                  min={0}
                  max={tableMaxScroll}
                  value={tableScrollLeft}
                  onChange={(e) => handleFixedSliderChange(Number(e.target.value))}
                  className="w-full"
                  aria-label="Horisontal tabellscroll"
                />
              </div>
            )}
            <div
              ref={tableScrollerRef}
              onScroll={handleTableScroll}
              className="overflow-x-auto overflow-y-hidden rounded-lg border border-gray-200 bg-white"
            >
              <table className="min-w-[1760px] divide-y divide-gray-200 text-sm">
                <colgroup>
                  <col style={{ width: `${colWidths.signal}px` }} />
                  <col style={{ width: `${colWidths.file}px` }} />
                  <col style={{ width: `${colWidths.direction}px` }} />
                  <col style={{ width: `${colWidths.status}px` }} />
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
                    <th className="group relative px-3 py-2" title="Compliance-score">
                      <button
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          startColumnResize("signal", e.clientX);
                        }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label="Juster bredde: compliance"
                      />
                    </th>
                    <th className="group relative px-3 py-2">
                      Fil
                      <button
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          startColumnResize("file", e.clientX);
                        }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label="Juster bredde: fil"
                      />
                    </th>
                    <th className="group relative px-3 py-2">
                      Retning
                      <button
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          startColumnResize("direction", e.clientX);
                        }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label="Juster bredde: retning"
                      />
                    </th>
                    <th className="group relative px-3 py-2">
                      Status
                      <button
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          startColumnResize("status", e.clientX);
                        }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label="Juster bredde: status"
                      />
                    </th>
                    <th className="group relative px-3 py-2">
                      Moms-merknad
                      <button
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          startColumnResize("vat", e.clientX);
                        }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label="Juster bredde: moms-merknad"
                      />
                    </th>
                    <th className="group relative px-3 py-2">
                      Epost-merknad
                      <button
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          startColumnResize("email", e.clientX);
                        }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label="Juster bredde: epost-merknad"
                      />
                    </th>
                    <th className="group relative px-3 py-2">
                      LLM-merknad
                      <button
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          startColumnResize("llm", e.clientX);
                        }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label="Juster bredde: LLM-merknad"
                      />
                    </th>
                    <th className="group relative px-3 py-2">
                      Fakturadato
                      <button
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          startColumnResize("invoice_date", e.clientX);
                        }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label="Juster bredde: fakturadato"
                      />
                    </th>
                    <th className="group relative px-3 py-2">
                      Beløp
                      <button
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          startColumnResize("amount", e.clientX);
                        }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label="Juster bredde: beløp"
                      />
                    </th>
                    <th className="group relative px-3 py-2">
                      Opprettet
                      <button
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          startColumnResize("created_at", e.clientX);
                        }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label="Juster bredde: opprettet"
                      />
                    </th>
                    <th className="group relative px-3 py-2">
                      <button
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          startColumnResize("actions", e.clientX);
                        }}
                        className="absolute top-0 right-0 h-full w-2 cursor-col-resize bg-gray-300/60 hover:bg-xlent-primary/40"
                        aria-label="Juster bredde: handlinger"
                      />
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data.items.length === 0 && (
                    <tr>
                      <td colSpan={11} className="px-3 py-6 text-center text-xlent-muted">
                        Ingen invoices matcher filteret. Last opp en PDF, XLSX eller PNG for å komme i gang.
                      </td>
                    </tr>
                  )}
                  {data.items.map((invoice) => (
                    <tr key={invoice.id} className="hover:bg-xlent-surface">
                      {/* Compliance-chip */}
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
                        {invoice.direction === "incoming" ? "Inn" : "Ut"}
                      </td>
                      <td className="px-3 py-2">
                        <StatusBadge status={invoice.status} score={invoice.compliance_score} />
                      </td>
                      <td className="px-3 py-2">
                        <div className="space-y-1">
                          <span
                            className={clsx(
                              "inline-flex rounded border px-1.5 py-0.5 text-[11px] font-medium",
                              noteBadge(invoice.vat_note_status).cls,
                            )}
                          >
                            {noteBadge(invoice.vat_note_status).label}
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
                              noteBadge(invoice.email_note_status).cls,
                            )}
                          >
                            {noteBadge(invoice.email_note_status).label}
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
                        {new Date(invoice.created_at).toLocaleString("nb-NO", {
                          dateStyle: "short",
                          timeStyle: "short",
                        })}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          onClick={() => handleDelete(invoice.id, invoice.original_filename)}
                          disabled={deleteInvoice.isPending}
                          className="rounded px-2 py-0.5 text-xs text-traffic-red hover:bg-red-50 disabled:opacity-40"
                          title="Slett invoice"
                        >
                          Slett
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-xlent-muted">
              Tips: tabellen er bred. Bruk horisontal scrollbar nederst for å se alle kolonner.
            </p>

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
