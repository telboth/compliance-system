import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { AxiosError } from "axios";
import { useTranslation } from "react-i18next";

import { Pagination } from "@/components/Pagination";
import { CountryAutocomplete } from "@/components/CountryAutocomplete";
import {
  useInvoiceRAGSearch,
  useInvoiceSearch,
  useReindexInvoiceRAG,
  useReindexInvoiceSearch,
} from "@/hooks/useInvoices";
import { resolveCountryToIso2 } from "@/lib/country";

interface SearchFormState {
  q: string;
  entity_q: string;
  line_q: string;
  serial_number: string;
  destination_country: string;
  date_from: string;
  date_to: string;
}

interface RAGFormState {
  query: string;
  entity_q: string;
  line_q: string;
  serial_number: string;
  destination_country: string;
  date_from: string;
  date_to: string;
  with_answer: boolean;
}

type SearchMode = "classic" | "rag";

const INPUT_CLS =
  "w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-sm text-xlent-ink focus:outline-none focus:ring-1 focus:ring-xlent-primary";

function stripMarkTags(snippet: string): string {
  return snippet.replaceAll("<mark>", "").replaceAll("</mark>", "");
}

function formatRagError(error: unknown, t: (key: string) => string): string {
  const fallback = t("invoice_search.rag_error_generic");
  const ax = error as AxiosError<{
    detail?: unknown;
    message?: string;
  }>;
  const status = ax?.response?.status;
  const data = ax?.response?.data;
  if (status === 422) {
    return t("invoice_search.rag_error_422");
  }
  if (typeof data?.message === "string" && data.message.trim()) {
    return `${fallback} ${data.message.trim()}`;
  }
  if (typeof data?.detail === "string" && data.detail.trim()) {
    return `${fallback} ${data.detail.trim()}`;
  }
  return fallback;
}

export function InvoiceSearchPage() {
  const { t } = useTranslation("pages");
  const [mode, setMode] = useState<SearchMode>("classic");

  const [form, setForm] = useState<SearchFormState>({
    q: "",
    entity_q: "",
    line_q: "",
    serial_number: "",
    destination_country: "",
    date_from: "",
    date_to: "",
  });
  const [submitted, setSubmitted] = useState<SearchFormState>(form);
  const [offset, setOffset] = useState(0);
  const [classicCountryError, setClassicCountryError] = useState<string | null>(null);
  const limit = 30;
  const reindexClassic = useReindexInvoiceSearch();

  const [ragForm, setRagForm] = useState<RAGFormState>({
    query: "",
    entity_q: "",
    line_q: "",
    serial_number: "",
    destination_country: "",
    date_from: "",
    date_to: "",
    with_answer: true,
  });
  const [ragSubmitted, setRagSubmitted] = useState<RAGFormState | null>(null);
  const [ragValidationError, setRagValidationError] = useState<string | null>(null);
  const [ragCountryError, setRagCountryError] = useState<string | null>(null);
  const [ragEvidenceOnly, setRagEvidenceOnly] = useState<boolean>(false);
  const reindexRag = useReindexInvoiceRAG();

  const searchParams = useMemo(
    () => ({
      ...submitted,
      limit,
      offset,
    }),
    [submitted, limit, offset],
  );

  const hasClassicQuery =
    Boolean(submitted.q) ||
    Boolean(submitted.entity_q) ||
    Boolean(submitted.line_q) ||
    Boolean(submitted.serial_number) ||
    Boolean(submitted.destination_country) ||
    Boolean(submitted.date_from) ||
    Boolean(submitted.date_to);
  const classicSearch = useInvoiceSearch(searchParams, mode === "classic" && hasClassicQuery);
  const total = classicSearch.data?.total ?? 0;

  const ragEnabled = mode === "rag" && Boolean(ragSubmitted);
  const ragSearch = useInvoiceRAGSearch(ragSubmitted, ragEnabled);
  const ragVisibleHits = useMemo(() => {
    const hits = ragSearch.data?.hits ?? [];
    if (!ragEvidenceOnly) return hits;
    return hits.filter((hit) => hit.evidence_hit);
  }, [ragSearch.data?.hits, ragEvidenceOnly]);

  function update<K extends keyof SearchFormState>(key: K, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function updateRag<K extends keyof RAGFormState>(key: K, value: RAGFormState[K]) {
    setRagForm((prev) => ({ ...prev, [key]: value }));
  }

  function submitClassic() {
    const resolvedCountry = resolveCountryToIso2(form.destination_country);
    if (form.destination_country.trim() && !resolvedCountry) {
      setClassicCountryError(t("invoice_search.country_invalid"));
      return;
    }
    setClassicCountryError(null);
    setOffset(0);
    setSubmitted({
      q: form.q.trim(),
      entity_q: form.entity_q.trim(),
      line_q: form.line_q.trim(),
      serial_number: form.serial_number.trim(),
      destination_country: resolvedCountry,
      date_from: form.date_from.trim(),
      date_to: form.date_to.trim(),
    });
  }

  function resetClassic() {
    const empty: SearchFormState = {
      q: "",
      entity_q: "",
      line_q: "",
      serial_number: "",
      destination_country: "",
      date_from: "",
      date_to: "",
    };
    setForm(empty);
    setSubmitted(empty);
    setOffset(0);
    setClassicCountryError(null);
  }

  function submitRag() {
    const query = ragForm.query.trim();
    if (!query) {
      setRagValidationError(t("invoice_search.question_empty"));
      return;
    }
    if (query.length < 2) {
      setRagValidationError(t("invoice_search.question_too_short"));
      return;
    }
    const resolvedCountry = resolveCountryToIso2(ragForm.destination_country);
    if (ragForm.destination_country.trim() && !resolvedCountry) {
      setRagCountryError(t("invoice_search.country_invalid"));
      return;
    }
    setRagValidationError(null);
    setRagCountryError(null);
    setRagSubmitted({
      query,
      entity_q: ragForm.entity_q.trim(),
      line_q: ragForm.line_q.trim(),
      serial_number: ragForm.serial_number.trim(),
      destination_country: resolvedCountry,
      date_from: ragForm.date_from.trim(),
      date_to: ragForm.date_to.trim(),
      with_answer: ragForm.with_answer,
    });
  }

  function resetRag() {
    const empty: RAGFormState = {
      query: "",
      entity_q: "",
      line_q: "",
      serial_number: "",
      destination_country: "",
      date_from: "",
      date_to: "",
      with_answer: true,
    };
    setRagForm(empty);
    setRagSubmitted(null);
    setRagValidationError(null);
    setRagCountryError(null);
    setRagEvidenceOnly(false);
  }

  const activeReindex = mode === "classic" ? reindexClassic : reindexRag;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-xlent-ink">{t("invoice_search.title")}</h1>
          <p className="mt-1 text-sm text-xlent-muted">
            {t("invoice_search.subtitle")}
          </p>
          <div className="mt-3 inline-flex rounded border border-gray-200 bg-white p-1 text-xs">
            <button
              onClick={() => setMode("classic")}
              className={`rounded px-2 py-1 ${
                mode === "classic" ? "bg-xlent-primary text-white" : "text-xlent-muted"
              }`}
            >
              {t("invoice_search.mode_classic")}
            </button>
            <button
              onClick={() => setMode("rag")}
              className={`rounded px-2 py-1 ${
                mode === "rag" ? "bg-xlent-primary text-white" : "text-xlent-muted"
              }`}
            >
              {t("invoice_search.mode_rag")}
            </button>
          </div>
        </div>
        <button
          onClick={() => activeReindex.mutate()}
          disabled={activeReindex.isPending}
          className="rounded border border-gray-200 px-3 py-1.5 text-xs text-xlent-muted hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          title={t("invoice_search.reindex_title")}
        >
          {activeReindex.isPending
            ? t("invoice_search.reindexing")
            : mode === "classic"
              ? t("invoice_search.reindex_classic")
              : t("invoice_search.reindex_rag")}
        </button>
      </header>

      {mode === "classic" && (
        <>
          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
              {t("invoice_search.criteria")}
            </h2>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="md:col-span-2">
                <label className="mb-1 block text-xs text-xlent-muted">{t("invoice_search.global_search")}</label>
                <input
                  className={INPUT_CLS}
                  value={form.q}
                  onChange={(e) => update("q", e.target.value)}
                  placeholder={t("invoice_search.global_placeholder")}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">{t("invoice_search.entity_fuzzy")}</label>
                <input
                  className={INPUT_CLS}
                  value={form.entity_q}
                  onChange={(e) => update("entity_q", e.target.value)}
                  placeholder={t("invoice_search.example_rosneft")}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">{t("invoice_search.line_fuzzy")}</label>
                <input
                  className={INPUT_CLS}
                  value={form.line_q}
                  onChange={(e) => update("line_q", e.target.value)}
                  placeholder={t("invoice_search.example_navigation")}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">{t("invoice_search.serial_exact")}</label>
                <input
                  className={INPUT_CLS}
                  value={form.serial_number}
                  onChange={(e) => update("serial_number", e.target.value)}
                  placeholder={t("invoice_search.example_serial")}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">
                  {t("invoice_search.destination_iso2")}
                </label>
                <CountryAutocomplete
                  value={form.destination_country}
                  onChange={(next) => {
                    update("destination_country", next);
                    setClassicCountryError(null);
                  }}
                  placeholder={t("invoice_search.example_fr")}
                  className={INPUT_CLS}
                  maxLength={32}
                />
                {classicCountryError && (
                  <p className="mt-1 text-xs text-traffic-red">{classicCountryError}</p>
                )}
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">{t("invoice_search.date_from")}</label>
                <input
                  type="date"
                  className={INPUT_CLS}
                  value={form.date_from}
                  onChange={(e) => update("date_from", e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">{t("invoice_search.date_to")}</label>
                <input
                  type="date"
                  className={INPUT_CLS}
                  value={form.date_to}
                  onChange={(e) => update("date_to", e.target.value)}
                />
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <button
                onClick={submitClassic}
                className="rounded bg-xlent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-xlent-primary/90"
              >
                {t("invoice_search.search_button")}
              </button>
              <button
                onClick={resetClassic}
                className="rounded border border-gray-200 px-3 py-1.5 text-sm text-xlent-muted hover:bg-gray-50"
              >
                {t("invoice_search.reset_button")}
              </button>
            </div>
            {ragValidationError && (
              <p className="mt-2 text-xs text-traffic-red">{ragValidationError}</p>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                {t("invoice_search.hits_title")}
              </h2>
              {classicSearch.data?.took_ms != null && (
                <span className="text-xs text-xlent-muted">
                  {t("invoice_search.es_time")}: {classicSearch.data.took_ms} ms
                </span>
              )}
            </div>

            {!hasClassicQuery && (
              <p className="text-sm text-xlent-muted">{t("invoice_search.write_criteria")}</p>
            )}
            {hasClassicQuery && classicSearch.isLoading && (
              <p className="text-sm text-xlent-muted">{t("invoice_search.searching")}</p>
            )}
            {hasClassicQuery && classicSearch.error && (
              <p className="text-sm text-traffic-red">
                {t("invoice_search.search_failed")}
              </p>
            )}

            {hasClassicQuery && classicSearch.data && (
              <>
                <p className="mb-2 text-xs text-xlent-muted">{classicSearch.data.total} {t("invoice_search.hits")}</p>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 text-sm">
                    <thead className="bg-xlent-surface text-left text-xs uppercase text-xlent-muted">
                      <tr>
                        <th className="px-3 py-2">{t("invoice_search.col_score")}</th>
                        <th className="px-3 py-2">{t("invoice_search.col_invoice")}</th>
                        <th className="px-3 py-2">{t("invoice_search.col_country")}</th>
                        <th className="px-3 py-2">{t("invoice_search.col_date")}</th>
                        <th className="px-3 py-2">{t("invoice_search.col_shipment")}</th>
                        <th className="px-3 py-2">{t("invoice_search.col_basis")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {classicSearch.data.hits.length === 0 && (
                        <tr>
                          <td colSpan={6} className="px-3 py-6 text-center text-xlent-muted">
                            {t("invoice_search.no_hits")}
                          </td>
                        </tr>
                      )}
                      {classicSearch.data.hits.map((hit) => (
                        <tr key={`${hit.invoice_id}-${hit.score}`}>
                          <td className="px-3 py-2 text-xs tabular-nums text-xlent-muted">
                            {hit.score.toFixed(2)}
                          </td>
                          <td className="px-3 py-2">
                            <Link
                              to={`/invoices/${hit.invoice_id}`}
                              className="text-xlent-primary hover:underline"
                            >
                              {hit.original_filename ?? hit.invoice_number ?? hit.invoice_id}
                            </Link>
                          </td>
                          <td className="px-3 py-2 text-xs text-xlent-muted">
                            {hit.destination_country ?? "—"}
                          </td>
                          <td className="px-3 py-2 text-xs text-xlent-muted">
                            {hit.invoice_date ?? "—"}
                          </td>
                          <td className="px-3 py-2 text-xs text-xlent-muted">
                            <div>
                              {t("invoice_search.from")}: {hit.shipment_summary?.consignor ?? "—"}
                              {" · "}
                              {t("invoice_search.to")}: {hit.shipment_summary?.consignee ?? "—"}
                            </div>
                            <div className="mt-0.5">
                              {t("invoice_search.end_user")}: {hit.shipment_summary?.end_user ?? "—"}
                            </div>
                            <div className="mt-0.5">
                              {t("invoice_search.items")}:{" "}
                              {(hit.shipment_summary?.top_items ?? []).slice(0, 2).join(", ") || "—"}
                            </div>
                          </td>
                          <td className="px-3 py-2 text-xs text-xlent-muted">
                            {hit.field_matches.length > 0 ? (
                              <div className="space-y-1">
                                {hit.field_matches.slice(0, 2).map((fm, idx) => (
                                  <div key={`${hit.invoice_id}-${fm.field}-${idx}`}>
                                    <span className="font-medium text-xlent-ink">{fm.label}:</span>{" "}
                                    <span>{stripMarkTags(fm.snippets[0] ?? "")}</span>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <span>
                                {hit.matched_entities.slice(0, 2).join(", ") || "—"}
                                {hit.matched_lines.slice(0, 2).length > 0 && (
                                  <span>
                                    {" · "}
                                    {hit.matched_lines.slice(0, 2).join(", ")}
                                  </span>
                                )}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <Pagination
                  total={total}
                  limit={limit}
                  offset={offset}
                  onPrev={() => setOffset((v) => Math.max(0, v - limit))}
                  onNext={() => setOffset((v) => v + limit)}
                />
              </>
            )}
          </section>
        </>
      )}

      {mode === "rag" && (
        <>
          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
              {t("invoice_search.rag_query")}
            </h2>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="md:col-span-2">
                <label className="mb-1 block text-xs text-xlent-muted">{t("invoice_search.question")}</label>
                <input
                  className={INPUT_CLS}
                  value={ragForm.query}
                  onChange={(e) => updateRag("query", e.target.value)}
                  placeholder={t("invoice_search.question_placeholder")}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">{t("invoice_search.entity_fuzzy")}</label>
                <input
                  className={INPUT_CLS}
                  value={ragForm.entity_q}
                  onChange={(e) => updateRag("entity_q", e.target.value)}
                  placeholder={t("invoice_search.optional")}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">{t("invoice_search.line_fuzzy")}</label>
                <input
                  className={INPUT_CLS}
                  value={ragForm.line_q}
                  onChange={(e) => updateRag("line_q", e.target.value)}
                  placeholder={t("invoice_search.optional")}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">{t("invoice_search.serial_exact")}</label>
                <input
                  className={INPUT_CLS}
                  value={ragForm.serial_number}
                  onChange={(e) => updateRag("serial_number", e.target.value)}
                  placeholder={t("invoice_search.optional")}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">
                  {t("invoice_search.destination_iso2")}
                </label>
                <CountryAutocomplete
                  value={ragForm.destination_country}
                  onChange={(next) => {
                    updateRag("destination_country", next);
                    setRagCountryError(null);
                  }}
                  placeholder={t("invoice_search.optional")}
                  className={INPUT_CLS}
                  maxLength={32}
                />
                {ragCountryError && (
                  <p className="mt-1 text-xs text-traffic-red">{ragCountryError}</p>
                )}
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">{t("invoice_search.date_from")}</label>
                <input
                  type="date"
                  className={INPUT_CLS}
                  value={ragForm.date_from}
                  onChange={(e) => updateRag("date_from", e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">{t("invoice_search.date_to")}</label>
                <input
                  type="date"
                  className={INPUT_CLS}
                  value={ragForm.date_to}
                  onChange={(e) => updateRag("date_to", e.target.value)}
                />
              </div>
            </div>

            <label className="mt-3 inline-flex items-center gap-2 text-sm text-xlent-muted">
              <input
                type="checkbox"
                checked={ragForm.with_answer}
                onChange={(e) => updateRag("with_answer", e.target.checked)}
              />
              {t("invoice_search.generate_answer")}
            </label>

            <div className="mt-4 flex gap-2">
              <button
                onClick={submitRag}
                className="rounded bg-xlent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-xlent-primary/90"
              >
                {t("invoice_search.run_rag")}
              </button>
              <button
                onClick={resetRag}
                className="rounded border border-gray-200 px-3 py-1.5 text-sm text-xlent-muted hover:bg-gray-50"
              >
                {t("invoice_search.reset_button")}
              </button>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                {t("invoice_search.rag_hits")}
              </h2>
              {ragSearch.data?.took_ms != null && (
                <span className="text-xs text-xlent-muted">
                  {t("invoice_search.es_time")}: {ragSearch.data.took_ms} ms
                </span>
              )}
            </div>

            {!ragSubmitted && (
              <p className="text-sm text-xlent-muted">{t("invoice_search.write_question")}</p>
            )}
            {ragSubmitted && ragSearch.isLoading && (
              <p className="text-sm text-xlent-muted">{t("invoice_search.running_rag")}</p>
            )}
            {ragSubmitted && ragSearch.error && (
              <p className="text-sm text-traffic-red">{formatRagError(ragSearch.error, t)}</p>
            )}

            {ragSearch.data && (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-xs text-xlent-muted">
                    {ragSearch.data.total_raw} {t("invoice_search.raw_hits")}, {ragSearch.data.total_after_dedupe} {t("invoice_search.after_dedupe")} ({t("invoice_search.showing")} {ragVisibleHits.length})
                  </p>
                  <label className="inline-flex items-center gap-2 text-xs text-xlent-muted">
                    <input
                      type="checkbox"
                      checked={ragEvidenceOnly}
                      onChange={(e) => setRagEvidenceOnly(e.target.checked)}
                    />
                    {t("invoice_search.evidence_only")}
                  </label>
                </div>
                {ragSearch.data.answer && (
                  <div className="rounded border border-gray-200 bg-xlent-surface p-3">
                    <div className="mb-1 text-xs uppercase tracking-wide text-xlent-muted">
                      {t("invoice_search.llm_answer")} {ragSearch.data.answer_model ? `(${ragSearch.data.answer_model})` : ""}
                    </div>
                    <p className="text-sm text-xlent-ink whitespace-pre-wrap">
                      {ragSearch.data.answer}
                    </p>
                    <p className="mt-2 text-xs text-xlent-muted">
                      {t("invoice_search.based_on_sources", { count: ragSearch.data.answer_source_count })}
                    </p>
                  </div>
                )}

                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 text-sm">
                    <thead className="bg-xlent-surface text-left text-xs uppercase text-xlent-muted">
                      <tr>
                        <th className="px-3 py-2">{t("invoice_search.col_score")}</th>
                        <th className="px-3 py-2">{t("invoice_search.col_invoice")}</th>
                        <th className="px-3 py-2">{t("invoice_search.col_chunk")}</th>
                        <th className="px-3 py-2">{t("invoice_search.col_evidence")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {ragVisibleHits.length === 0 && (
                        <tr>
                          <td colSpan={4} className="px-3 py-6 text-center text-xlent-muted">
                            {ragEvidenceOnly
                              ? t("invoice_search.no_evidence_hits")
                              : t("invoice_search.no_hits")}
                          </td>
                        </tr>
                      )}
                      {ragVisibleHits.map((hit) => (
                        <tr key={hit.chunk_id}>
                          <td className="px-3 py-2 text-xs tabular-nums text-xlent-muted">
                            {hit.score.toFixed(2)}
                          </td>
                          <td className="px-3 py-2">
                            <Link
                              to={`/invoices/${hit.invoice_id}`}
                              className="text-xlent-primary hover:underline"
                            >
                              {hit.original_filename ?? hit.invoice_number ?? hit.invoice_id}
                            </Link>
                          </td>
                          <td className="px-3 py-2 text-xs text-xlent-muted">
                            #{hit.chunk_index}
                          </td>
                          <td className="px-3 py-2 text-xs text-xlent-muted">
                            {hit.evidence_hit ? (
                              <span className="inline-flex rounded bg-green-50 px-1.5 py-0.5 text-[11px] text-green-700">
                                {t("invoice_search.evidence")}
                              </span>
                            ) : (
                              <span className="inline-flex rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-600">
                                {t("invoice_search.weak")}
                              </span>
                            )}
                            <div className="mt-1">{stripMarkTags(hit.snippet)}</div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
