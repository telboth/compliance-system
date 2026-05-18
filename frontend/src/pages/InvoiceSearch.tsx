import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { AxiosError } from "axios";

import { Pagination } from "@/components/Pagination";
import {
  useInvoiceRAGSearch,
  useInvoiceSearch,
  useReindexInvoiceRAG,
  useReindexInvoiceSearch,
} from "@/hooks/useInvoices";

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

function formatRagError(error: unknown): string {
  const fallback = "RAG-søk feilet.";
  const ax = error as AxiosError<{
    detail?: unknown;
    message?: string;
  }>;
  const status = ax?.response?.status;
  const data = ax?.response?.data;
  if (status === 422) {
    return "RAG-request ble avvist (422). Sjekk query/dato-felt.";
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
    setOffset(0);
    setSubmitted({
      q: form.q.trim(),
      entity_q: form.entity_q.trim(),
      line_q: form.line_q.trim(),
      serial_number: form.serial_number.trim(),
      destination_country: form.destination_country.trim().toUpperCase(),
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
  }

  function submitRag() {
    const query = ragForm.query.trim();
    if (!query) {
      setRagValidationError("Spørsmål kan ikke være tomt.");
      return;
    }
    if (query.length < 2) {
      setRagValidationError("Spørsmål må ha minst 2 tegn.");
      return;
    }
    setRagValidationError(null);
    setRagSubmitted({
      query,
      entity_q: ragForm.entity_q.trim(),
      line_q: ragForm.line_q.trim(),
      serial_number: ragForm.serial_number.trim(),
      destination_country: ragForm.destination_country.trim().toUpperCase(),
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
    setRagEvidenceOnly(false);
  }

  const activeReindex = mode === "classic" ? reindexClassic : reindexRag;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-xlent-ink">Søk i invoices</h1>
          <p className="mt-1 text-sm text-xlent-muted">
            Klassisk søk og hybrid RAG over hele invoice-teksten.
          </p>
          <div className="mt-3 inline-flex rounded border border-gray-200 bg-white p-1 text-xs">
            <button
              onClick={() => setMode("classic")}
              className={`rounded px-2 py-1 ${
                mode === "classic" ? "bg-xlent-primary text-white" : "text-xlent-muted"
              }`}
            >
              Klassisk
            </button>
            <button
              onClick={() => setMode("rag")}
              className={`rounded px-2 py-1 ${
                mode === "rag" ? "bg-xlent-primary text-white" : "text-xlent-muted"
              }`}
            >
              Hybrid RAG
            </button>
          </div>
        </div>
        <button
          onClick={() => activeReindex.mutate()}
          disabled={activeReindex.isPending}
          className="rounded border border-gray-200 px-3 py-1.5 text-xs text-xlent-muted hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          title="Bygg søkeindeks på nytt fra databasen"
        >
          {activeReindex.isPending
            ? "Reindekserer …"
            : mode === "classic"
              ? "Reindekser klassisk søk"
              : "Reindekser RAG"}
        </button>
      </header>

      {mode === "classic" && (
        <>
          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
              Søkekriterier
            </h2>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="md:col-span-2">
                <label className="mb-1 block text-xs text-xlent-muted">Globalt søk</label>
                <input
                  className={INPUT_CLS}
                  value={form.q}
                  onChange={(e) => update("q", e.target.value)}
                  placeholder="Entitet, varenavn, notater, dokumenttekst …"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">Entitet (fuzzy)</label>
                <input
                  className={INPUT_CLS}
                  value={form.entity_q}
                  onChange={(e) => update("entity_q", e.target.value)}
                  placeholder="F.eks. Rosneft"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">Varelinje (fuzzy)</label>
                <input
                  className={INPUT_CLS}
                  value={form.line_q}
                  onChange={(e) => update("line_q", e.target.value)}
                  placeholder="F.eks. navigation module"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">Serienummer (eksakt)</label>
                <input
                  className={INPUT_CLS}
                  value={form.serial_number}
                  onChange={(e) => update("serial_number", e.target.value)}
                  placeholder="F.eks. SN-7781-A"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">
                  Destinasjonsland (ISO2)
                </label>
                <input
                  className={INPUT_CLS}
                  value={form.destination_country}
                  onChange={(e) => update("destination_country", e.target.value.toUpperCase())}
                  placeholder="F.eks. FR"
                  maxLength={2}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">Fakturadato fra</label>
                <input
                  type="date"
                  className={INPUT_CLS}
                  value={form.date_from}
                  onChange={(e) => update("date_from", e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">Fakturadato til</label>
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
                Søk
              </button>
              <button
                onClick={resetClassic}
                className="rounded border border-gray-200 px-3 py-1.5 text-sm text-xlent-muted hover:bg-gray-50"
              >
                Nullstill
              </button>
            </div>
            {ragValidationError && (
              <p className="mt-2 text-xs text-traffic-red">{ragValidationError}</p>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                Treff
              </h2>
              {classicSearch.data?.took_ms != null && (
                <span className="text-xs text-xlent-muted">
                  ES tid: {classicSearch.data.took_ms} ms
                </span>
              )}
            </div>

            {!hasClassicQuery && (
              <p className="text-sm text-xlent-muted">Skriv søkekriterier og trykk Søk.</p>
            )}
            {hasClassicQuery && classicSearch.isLoading && (
              <p className="text-sm text-xlent-muted">Søker …</p>
            )}
            {hasClassicQuery && classicSearch.error && (
              <p className="text-sm text-traffic-red">
                Søket feilet. Sjekk at Elasticsearch er oppe og at indeksen finnes.
              </p>
            )}

            {hasClassicQuery && classicSearch.data && (
              <>
                <p className="mb-2 text-xs text-xlent-muted">{classicSearch.data.total} treff</p>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 text-sm">
                    <thead className="bg-xlent-surface text-left text-xs uppercase text-xlent-muted">
                      <tr>
                        <th className="px-3 py-2">Score</th>
                        <th className="px-3 py-2">Invoice</th>
                        <th className="px-3 py-2">Land</th>
                        <th className="px-3 py-2">Dato</th>
                        <th className="px-3 py-2">Hva sendt hvor</th>
                        <th className="px-3 py-2">Treffgrunnlag</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {classicSearch.data.hits.length === 0 && (
                        <tr>
                          <td colSpan={6} className="px-3 py-6 text-center text-xlent-muted">
                            Ingen treff.
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
                              Fra: {hit.shipment_summary?.consignor ?? "—"}
                              {" · "}
                              Til: {hit.shipment_summary?.consignee ?? "—"}
                            </div>
                            <div className="mt-0.5">
                              Sluttbruker: {hit.shipment_summary?.end_user ?? "—"}
                            </div>
                            <div className="mt-0.5">
                              Varer:{" "}
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
              Hybrid RAG-spørring
            </h2>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="md:col-span-2">
                <label className="mb-1 block text-xs text-xlent-muted">Spørsmål / søk</label>
                <input
                  className={INPUT_CLS}
                  value={ragForm.query}
                  onChange={(e) => updateRag("query", e.target.value)}
                  placeholder="F.eks. Er Rosneft involvert i noen invoices?"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">Entitet (fuzzy)</label>
                <input
                  className={INPUT_CLS}
                  value={ragForm.entity_q}
                  onChange={(e) => updateRag("entity_q", e.target.value)}
                  placeholder="Valgfritt"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">Varelinje (fuzzy)</label>
                <input
                  className={INPUT_CLS}
                  value={ragForm.line_q}
                  onChange={(e) => updateRag("line_q", e.target.value)}
                  placeholder="Valgfritt"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">Serienummer (eksakt)</label>
                <input
                  className={INPUT_CLS}
                  value={ragForm.serial_number}
                  onChange={(e) => updateRag("serial_number", e.target.value)}
                  placeholder="Valgfritt"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">
                  Destinasjonsland (ISO2)
                </label>
                <input
                  className={INPUT_CLS}
                  value={ragForm.destination_country}
                  onChange={(e) => updateRag("destination_country", e.target.value.toUpperCase())}
                  placeholder="Valgfritt"
                  maxLength={2}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">Fakturadato fra</label>
                <input
                  type="date"
                  className={INPUT_CLS}
                  value={ragForm.date_from}
                  onChange={(e) => updateRag("date_from", e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-xlent-muted">Fakturadato til</label>
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
              Generer LLM-svar fra toppkilder
            </label>

            <div className="mt-4 flex gap-2">
              <button
                onClick={submitRag}
                className="rounded bg-xlent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-xlent-primary/90"
              >
                Kjør RAG-søk
              </button>
              <button
                onClick={resetRag}
                className="rounded border border-gray-200 px-3 py-1.5 text-sm text-xlent-muted hover:bg-gray-50"
              >
                Nullstill
              </button>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                RAG-treff
              </h2>
              {ragSearch.data?.took_ms != null && (
                <span className="text-xs text-xlent-muted">
                  ES tid: {ragSearch.data.took_ms} ms
                </span>
              )}
            </div>

            {!ragSubmitted && (
              <p className="text-sm text-xlent-muted">Skriv et spørsmål og kjør søk.</p>
            )}
            {ragSubmitted && ragSearch.isLoading && (
              <p className="text-sm text-xlent-muted">Kjører hybrid RAG-søk …</p>
            )}
            {ragSubmitted && ragSearch.error && (
              <p className="text-sm text-traffic-red">{formatRagError(ragSearch.error)}</p>
            )}

            {ragSearch.data && (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-xs text-xlent-muted">
                    {ragSearch.data.total_raw} rå-treff, {ragSearch.data.total_after_dedupe} etter deduplisering (viser {ragVisibleHits.length})
                  </p>
                  <label className="inline-flex items-center gap-2 text-xs text-xlent-muted">
                    <input
                      type="checkbox"
                      checked={ragEvidenceOnly}
                      onChange={(e) => setRagEvidenceOnly(e.target.checked)}
                    />
                    Vis kun evidens-treff
                  </label>
                </div>
                {ragSearch.data.answer && (
                  <div className="rounded border border-gray-200 bg-xlent-surface p-3">
                    <div className="mb-1 text-xs uppercase tracking-wide text-xlent-muted">
                      LLM-svar {ragSearch.data.answer_model ? `(${ragSearch.data.answer_model})` : ""}
                    </div>
                    <p className="text-sm text-xlent-ink whitespace-pre-wrap">
                      {ragSearch.data.answer}
                    </p>
                    <p className="mt-2 text-xs text-xlent-muted">
                      Basert på {ragSearch.data.answer_source_count} kilder.
                    </p>
                  </div>
                )}

                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 text-sm">
                    <thead className="bg-xlent-surface text-left text-xs uppercase text-xlent-muted">
                      <tr>
                        <th className="px-3 py-2">Score</th>
                        <th className="px-3 py-2">Invoice</th>
                        <th className="px-3 py-2">Chunk</th>
                        <th className="px-3 py-2">Evidens</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {ragVisibleHits.length === 0 && (
                        <tr>
                          <td colSpan={4} className="px-3 py-6 text-center text-xlent-muted">
                            {ragEvidenceOnly
                              ? "Ingen evidens-treff for valgt spørsmål."
                              : "Ingen treff."}
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
                                Evidens
                              </span>
                            ) : (
                              <span className="inline-flex rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-600">
                                Svak
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
