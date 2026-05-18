import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";

import { useAuth } from "@/auth/AuthContext";

import { EditableField } from "@/components/EditableField";
import { StatusBadge } from "@/components/StatusBadge";
import { computeOverallRisk } from "@/components/ComplianceBadge";
import { AuditTimeline } from "@/components/AuditTimeline";
import {
  useDeleteInvoice,
  useExtendedScreeningRun,
  useExtractInvoice,
  useInvoice,
  useReparseInvoice,
  useReviewInvoice,
  useSanctionsStatus,
  useScreeningCandidates,
  useScreeningResults,
  useStartExtendedScreening,
  useStartScreening,
  useUpdateEntity,
  useUpdateInvoiceFields,
  useUpdateInvoiceLine,
} from "@/hooks/useInvoices";
import { getCountryRisk, TIER_LABELS } from "@/data/countryRisk";
import { getSelectedModel } from "@/lib/modelStore";
import { getInvoiceFileUrl } from "@/api/invoices";
import { getInvoiceReportUrl } from "@/api/notifications";
import { classifyHsCode } from "@/api/watchlist";
import type {
  Entity,
  ExtractionConfidence,
  Invoice,
  InvoiceLine,
  MatchStatus,
  ScreeningCandidateDebug,
  ScreeningResult,
} from "@/api/types";

// ── Konfidensindikatorer ──────────────────────────────────────────────────────

function confidenceColor(score: number): string {
  if (score >= 0.9) return "text-traffic-green";
  if (score >= 0.8) return "text-traffic-yellow";
  return "text-traffic-red";
}

function confidenceBg(score: number): string {
  if (score >= 0.9) return "bg-green-50 border-green-200";
  if (score >= 0.8) return "bg-yellow-50 border-yellow-200";
  return "bg-red-50 border-red-100";
}

function ConfidencePip({ score }: { score: number }) {
  return (
    <span
      title={`Konfidens: ${(score * 100).toFixed(0)}%`}
      className={clsx("ml-1 text-xs font-medium tabular-nums", confidenceColor(score))}
    >
      {(score * 100).toFixed(0)}%
    </span>
  );
}

// ── Redigerbar felt-rad i metadata-listen ─────────────────────────────────────

interface EditableFieldRowProps {
  label: string;
  fieldKey: string;
  value: string | null | undefined;
  confidence?: number | null;
  onSave: (key: string, value: string) => Promise<void>;
  editable?: boolean;
  type?: "text" | "date" | "select";
  options?: { value: string; label: string }[];
}

function EditableFieldRow({
  label,
  fieldKey,
  value,
  confidence,
  onSave,
  editable = true,
  type = "text",
  options,
}: EditableFieldRowProps) {
  return (
    <>
      <dt className="text-xlent-muted">{label}</dt>
      <dd className="flex items-center gap-1">
        <EditableField
          value={value}
          onSave={(v) => onSave(fieldKey, v)}
          editable={editable}
          type={type}
          options={options}
        />
        {confidence != null && <ConfidencePip score={confidence} />}
      </dd>
    </>
  );
}

// Ikke-redigerbar felt-rad
function FieldRow({
  label,
  value,
  confidence,
}: {
  label: string;
  value: React.ReactNode;
  confidence?: number | null;
}) {
  return (
    <>
      <dt className="text-xlent-muted">{label}</dt>
      <dd className="flex items-center gap-1">
        <span>{value ?? "—"}</span>
        {confidence != null && <ConfidencePip score={confidence} />}
      </dd>
    </>
  );
}

// ── Dokument-inspektor ───────────────────────────────────────────────────────

function FileViewer({ invoice }: { invoice: Invoice }) {
  const fileUrl = getInvoiceFileUrl(invoice.id);
  const ext = (invoice.original_filename ?? "").split(".").pop()?.toLowerCase() ?? "";

  if (ext === "pdf") {
    return <iframe src={fileUrl} className="h-full w-full border-0" title="Invoice PDF" />;
  }
  if (["png", "jpg", "jpeg"].includes(ext)) {
    return (
      <div className="flex h-full items-start justify-center overflow-auto p-2">
        <img src={fileUrl} alt="Invoice" className="max-w-full object-contain" />
      </div>
    );
  }
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
      <p className="text-sm text-xlent-muted">
        Forhåndsvisning ikke tilgjengelig for{" "}
        <span className="font-medium uppercase">{ext || "denne filtypen"}</span>.
      </p>
      <a
        href={fileUrl}
        download={invoice.original_filename ?? "invoice"}
        className="rounded bg-xlent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-xlent-primary/90"
      >
        Last ned {invoice.original_filename}
      </a>
    </div>
  );
}

function DocumentInspector({ invoice }: { invoice: Invoice }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="rounded-lg border border-gray-200 bg-white">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-xlent-muted hover:bg-xlent-surface"
      >
        <span>Dokument-inspektor</span>
        <span className="ml-2 font-mono text-base leading-none">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div
          className="grid border-t border-gray-200"
          style={{ gridTemplateColumns: "1fr 1fr", height: "70vh" }}
        >
          <div className="flex flex-col overflow-hidden border-r border-gray-200">
            <div className="shrink-0 border-b border-gray-100 px-3 py-2 text-xs font-medium text-xlent-muted">
              Originalfil — {invoice.original_filename ?? invoice.id}
            </div>
            <div className="min-h-0 flex-1">
              <FileViewer invoice={invoice} />
            </div>
          </div>
          <div className="flex flex-col overflow-hidden">
            <div className="shrink-0 border-b border-gray-100 px-3 py-2 text-xs font-medium text-xlent-muted">
              Parsert tekst (Vision OCR / Docling)
            </div>
            <div className="min-h-0 flex-1 overflow-auto">
              <pre className="p-4 font-mono text-xs leading-relaxed text-xlent-ink whitespace-pre-wrap break-words">
                {invoice.raw_text ?? "Ingen parsert tekst ennå."}
              </pre>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

// ── Ekstraher / Re-parse knapper ─────────────────────────────────────────────

function ActionButtons({
  invoiceId,
  canExtract,
  canScreen,
  isProcessing,
  isExtracted,
}: {
  invoiceId: string;
  canExtract: boolean;
  canScreen: boolean;
  isProcessing: boolean;
  isExtracted: boolean;
}) {
  const extract = useExtractInvoice(invoiceId);
  const reparse = useReparseInvoice(invoiceId);
  const screen = useStartScreening(invoiceId);
  const { data: sanctionsStatus, isLoading: sanctionsLoading, error: sanctionsError } =
    useSanctionsStatus(canScreen);
  const screeningInfraReady = Boolean(
    sanctionsStatus?.yente_available && sanctionsStatus?.elasticsearch_available,
  );
  const screenDisabled = screen.isPending || !screeningInfraReady;
  const showActionMenu = !isProcessing;

  return (
    <div className="flex flex-col items-end gap-1.5">
      {canScreen && (
        <div
          className={clsx(
            "rounded border px-2 py-1 text-[11px]",
            sanctionsLoading
              ? "border-gray-200 bg-gray-50 text-xlent-muted"
              : screeningInfraReady
                ? "border-green-200 bg-green-50 text-green-700"
                : "border-red-200 bg-red-50 text-red-700",
          )}
          title={
            sanctionsStatus?.elasticsearch_error ??
            "Status for Yente og Elasticsearch"
          }
        >
          {sanctionsLoading
            ? "Sanksjonsmotor: sjekker …"
            : screeningInfraReady
              ? "Sanksjonsmotor: Yente + Elasticsearch oppe"
              : "Sanksjonsmotor: ikke klar"}
        </div>
      )}

      {showActionMenu && (
        <details className="relative">
          <summary
            className="list-none cursor-pointer rounded border border-gray-200 px-2 py-1 text-sm text-xlent-muted hover:bg-gray-50 hover:text-xlent-ink"
            aria-label="Vis handlinger"
            title="Vis handlinger"
          >
            ⋯
          </summary>
          <div className="absolute right-0 z-20 mt-2 w-56 rounded border border-gray-200 bg-white p-2 shadow-lg">
            <div className="flex flex-col gap-2">
              <button
                onClick={() => reparse.mutate()}
                disabled={reparse.isPending}
                title="Re-parser dokumentet med forbedret Vision OCR"
                className={clsx(
                  "rounded border px-3 py-1.5 text-left text-xs font-medium transition-colors",
                  reparse.isPending
                    ? "cursor-not-allowed border-gray-200 text-xlent-muted"
                    : "border-xlent-primary/40 text-xlent-primary hover:bg-xlent-primary/5",
                )}
              >
                {reparse.isPending ? "Re-parser …" : "Re-parse"}
              </button>

              {canExtract && (
                <button
                  onClick={() => extract.mutate({ model_id: getSelectedModel().model_id })}
                  disabled={extract.isPending}
                  className={clsx(
                    "rounded px-3 py-1.5 text-left text-xs font-medium transition-colors",
                    !extract.isPending
                      ? "bg-xlent-primary text-white hover:bg-xlent-primary/90"
                      : "cursor-not-allowed bg-gray-100 text-xlent-muted",
                  )}
                >
                  {extract.isPending
                    ? "Ekstraherer …"
                    : isExtracted
                      ? "Re-ekstraher"
                      : "Ekstraher med LLM"}
                </button>
              )}

              {canScreen && (
                <button
                  onClick={() => screen.mutate()}
                  disabled={screenDisabled}
                  title={
                    screeningInfraReady
                      ? "Kjør sanksjonsscreening på nytt for alle parter"
                      : "Yente/Elasticsearch må være oppe før screening kan kjøres"
                  }
                  className={clsx(
                    "rounded border px-3 py-1.5 text-left text-xs font-medium transition-colors",
                    screenDisabled
                      ? "cursor-not-allowed border-gray-200 text-xlent-muted"
                      : "border-orange-300 bg-orange-50 text-orange-700 hover:bg-orange-100",
                  )}
                >
                  {screen.isPending ? "Re-screener …" : "Re-screen sanksjoner"}
                </button>
              )}
            </div>
          </div>
        </details>
      )}

      {extract.isError && (
        <p className="text-xs text-traffic-red">
          {(extract.error as { response?: { data?: { detail?: string } } })
            ?.response?.data?.detail ?? "Ekstraksjon feilet."}
        </p>
      )}
      {reparse.isError && <p className="text-xs text-traffic-red">Re-parsing feilet.</p>}
      {screen.isError && <p className="text-xs text-traffic-red">Screening feilet.</p>}
      {sanctionsError && canScreen && (
        <p className="text-xs text-traffic-red">
          Kunne ikke hente status for sanksjonsmotor.
        </p>
      )}
    </div>
  );
}

// ── Linjetabell med inline-redigering ────────────────────────────────────────

const TRANSPORT_OPTIONS = [
  { value: "sea", label: "Sjø" },
  { value: "air", label: "Luft" },
  { value: "road", label: "Vei" },
  { value: "rail", label: "Rail" },
  { value: "courier", label: "Kurer" },
  { value: "unknown", label: "Ukjent" },
];

// ── HS-kode risikobadge ───────────────────────────────────────────────────────

function HsRiskBadge({ code }: { code: string | null }) {
  const { data } = useQuery({
    queryKey: ["hs-classify", code],
    queryFn: () => classifyHsCode(code!),
    enabled: Boolean(code && code.trim().length >= 2),
    staleTime: Infinity,    // statisk tabell — aldri utdatert
  });

  if (!data || !data.risk_level) return null;

  const colors: Record<string, string> = {
    high: "bg-red-100 text-red-800 border-red-200",
    medium: "bg-amber-100 text-amber-800 border-amber-200",
    low: "bg-green-100 text-green-700 border-green-200",
  };

  const icons: Record<string, string> = {
    high: "🔴",
    medium: "🟡",
    low: "🟢",
  };

  const cls = colors[data.risk_level] ?? "bg-gray-100 text-gray-700";
  const icon = icons[data.risk_level] ?? "";

  return (
    <span
      title={[
        data.heading_description ?? data.chapter_description,
        data.risk_reason,
        data.is_controlled ? "Eksportkontroll" : null,
        data.dual_use_flag ? "Dual-use" : null,
      ].filter(Boolean).join(" · ")}
      className={clsx(
        "mt-0.5 inline-flex items-center gap-0.5 rounded border px-1 py-px text-[10px] font-medium",
        cls,
      )}
    >
      {icon} {data.risk_level}
      {data.dual_use_flag && " · DU"}
    </span>
  );
}

// ── Ikke-faktura-avvisningsbanner ─────────────────────────────────────────────

function NotInvoiceBanner({ invoice }: { invoice: Invoice }) {
  const navigate = useNavigate();
  const deleteMutation = useDeleteInvoice();

  const reason = invoice.parsing_error ?? invoice.extraction_error;

  async function handleDelete() {
    if (!window.confirm(`Slett «${invoice.original_filename ?? invoice.id}»?\n\nFilen og alle data fjernes permanent.`)) return;
    await deleteMutation.mutateAsync(invoice.id);
    navigate("/");
  }

  return (
    <section className="rounded-lg border border-orange-300 bg-orange-50 p-5">
      <div className="flex items-start gap-3">
        <span className="text-2xl" aria-hidden>⚠️</span>
        <div className="flex-1 min-w-0">
          <h2 className="text-base font-semibold text-orange-800">
            Dokumentet er ikke en faktura
          </h2>
          {reason && (
            <p className="mt-1 text-sm text-orange-700">{reason}</p>
          )}
          <p className="mt-2 text-xs text-orange-600">
            Systemet har stoppet behandlingen. Last opp riktig fil (PDF eller bilde av en faktura) for å starte på nytt.
          </p>
        </div>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <button
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
          className="rounded border border-orange-300 bg-white px-4 py-1.5 text-sm font-medium text-orange-800 hover:bg-orange-100 disabled:opacity-50"
        >
          {deleteMutation.isPending ? "Sletter…" : "🗑 Slett filen"}
        </button>
        <span className="text-xs text-orange-500">
          eller gå tilbake og last opp en annen fil
        </span>
      </div>
    </section>
  );
}

function LinesSection({
  invoice,
  canEdit,
}: {
  invoice: Invoice;
  canEdit: boolean;
}) {
  const updateLine = useUpdateInvoiceLine(invoice.id);

  async function saveLineField(lineId: string, field: string, value: string) {
    await updateLine.mutateAsync({ lineId, update: { [field]: value } });
  }

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
        Linjer ({invoice.lines.length})
        {canEdit && (
          <span className="ml-2 font-normal normal-case text-xlent-muted/60">
            — klikk en celle for å redigere
          </span>
        )}
      </h2>
      {invoice.lines.length === 0 ? (
        <p className="text-sm text-xlent-muted">
          {canEdit
            ? "Ingen linjer ennå — auto-ekstraksjon pågår eller ga tomt resultat."
            : "Ingen linjer ekstrahert."}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-xlent-muted">
                <th className="px-2 py-1">#</th>
                <th className="px-2 py-1">Beskrivelse</th>
                <th className="px-2 py-1">Modell</th>
                <th className="px-2 py-1">Serienr</th>
                <th className="px-2 py-1">HS-kode</th>
                <th className="px-2 py-1">ECCN</th>
                <th className="px-2 py-1">Oppr.land</th>
                <th className="px-2 py-1 text-right">Antall</th>
                <th className="px-2 py-1 text-right">Enhetspris</th>
                <th className="px-2 py-1 text-right">Sum</th>
                <th className="px-2 py-1">Valuta</th>
              </tr>
            </thead>
            <tbody>
              {invoice.lines.map((line: InvoiceLine) => (
                <tr key={line.id} className="border-t border-gray-100">
                  <td className="px-2 py-1 text-xlent-muted">{line.line_number}</td>

                  <td className="px-2 py-1">
                    <EditableField
                      value={line.description}
                      onSave={(v) => saveLineField(line.id, "description", v)}
                      editable={canEdit}
                    />
                    {line.product_code && (
                      <div className="mt-0.5">
                        <EditableField
                          value={line.product_code}
                          onSave={(v) => saveLineField(line.id, "product_code", v)}
                          editable={canEdit}
                          className="font-mono text-xs text-xlent-muted"
                        />
                      </div>
                    )}
                  </td>

                  <td className="px-2 py-1 font-mono text-xs">
                    <EditableField
                      value={line.model_number}
                      onSave={(v) => saveLineField(line.id, "model_number", v)}
                      editable={canEdit}
                    />
                  </td>

                  <td className="px-2 py-1 font-mono text-xs">
                    <EditableField
                      value={line.serial_number}
                      onSave={(v) => saveLineField(line.id, "serial_number", v)}
                      editable={canEdit}
                    />
                  </td>

                  <td className="px-2 py-1 font-mono text-xs">
                    <EditableField
                      value={line.hs_code}
                      onSave={(v) => saveLineField(line.id, "hs_code", v)}
                      editable={canEdit}
                    />
                    <HsRiskBadge code={line.hs_code} />
                  </td>

                  <td className="px-2 py-1 font-mono text-xs">
                    <EditableField
                      value={line.eccn}
                      onSave={(v) => saveLineField(line.id, "eccn", v)}
                      editable={canEdit}
                    />
                  </td>

                  <td className="px-2 py-1 font-mono text-xs uppercase">
                    <EditableField
                      value={line.country_of_origin}
                      onSave={(v) => saveLineField(line.id, "country_of_origin", v)}
                      editable={canEdit}
                    />
                  </td>

                  <td className="px-2 py-1 text-right tabular-nums">
                    <EditableField
                      value={
                        line.quantity
                          ? `${line.quantity}${line.unit_of_measure ? " " + line.unit_of_measure : ""}`
                          : null
                      }
                      onSave={(v) => saveLineField(line.id, "quantity", v)}
                      editable={canEdit}
                    />
                  </td>

                  <td className="px-2 py-1 text-right tabular-nums">
                    <EditableField
                      value={line.unit_price}
                      onSave={(v) => saveLineField(line.id, "unit_price", v)}
                      editable={canEdit}
                    />
                  </td>

                  <td className="px-2 py-1 text-right tabular-nums">
                    <EditableField
                      value={line.total_price}
                      onSave={(v) => saveLineField(line.id, "total_price", v)}
                      editable={canEdit}
                    />
                  </td>

                  <td className="px-2 py-1 font-mono text-xs font-medium text-xlent-muted">
                    <EditableField
                      value={line.currency}
                      onSave={(v) => saveLineField(line.id, "currency", v.toUpperCase())}
                      editable={canEdit}
                      placeholder="—"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// ── Entitetskort med inline-redigering ───────────────────────────────────────

const ENTITY_ROLE_OPTIONS = [
  { value: "seller", label: "Selger" },
  { value: "buyer", label: "Kjøper" },
  { value: "consignor", label: "Avsender" },
  { value: "consignee", label: "Mottaker" },
  { value: "end_user", label: "Sluttbruker" },
  { value: "delivery_address", label: "Leveringsadresse" },
  { value: "signatory", label: "Signatar" },
  { value: "other", label: "Annet" },
];

const ENTITY_ROLE_LABELS: Record<string, string> = {
  seller: "Selger",
  buyer: "Kjøper",
  consignor: "Avsender",
  consignee: "Mottaker",
  end_user: "Sluttbruker",
  delivery_address: "Leveringsadresse",
  signatory: "Signatar",
  other: "Annet",
};

function EntityCard({
  entity,
  invoiceId,
  canEdit,
  canRunExtended,
}: {
  entity: Entity;
  invoiceId: string;
  canEdit: boolean;
  canRunExtended: boolean;
}) {
  const navigate = useNavigate();
  const updateEntityMutation = useUpdateEntity(invoiceId);
  const [aggressiveness, setAggressiveness] = useState(70);
  const [minEdgeConfidence, setMinEdgeConfidence] = useState(0.6);
  const [selectedOnly, setSelectedOnly] = useState(true);
  const [sanctionsNearOnly, setSanctionsNearOnly] = useState(false);
  const [enableBrreg, setEnableBrreg] = useState(true);
  const [enableUkSanctions, setEnableUkSanctions] = useState(true);
  const [enableWorldBankDebarred, setEnableWorldBankDebarred] = useState(true);
  const [enableAiEntityResearch, setEnableAiEntityResearch] = useState(true);
  const [enableAiWebSearch, setEnableAiWebSearch] = useState(true);
  const [latestRunId, setLatestRunId] = useState<string | null>(null);
  const externalStatus = useSanctionsStatus(canRunExtended);
  const startExtended = useStartExtendedScreening(invoiceId, entity.id);
  const { data: extendedRun } = useExtendedScreeningRun(
    invoiceId,
    entity.id,
    latestRunId,
    Boolean(latestRunId),
  );

  async function save(field: string, value: string) {
    await updateEntityMutation.mutateAsync({ entityId: entity.id, update: { [field]: value } });
  }

  async function triggerExtendedScreening() {
    const run = await startExtended.mutateAsync({
      aggressiveness,
      min_edge_confidence: minEdgeConfidence,
      selected_only: selectedOnly,
      sanctions_near_only: sanctionsNearOnly,
      enable_brreg: enableBrreg,
      enable_uk_sanctions: enableUkSanctions,
      enable_world_bank_debarred: enableWorldBankDebarred,
      enable_ai_entity_research: enableAiEntityResearch,
      enable_ai_web_search: enableAiWebSearch,
    });
    setLatestRunId(run.id);
    void navigate(
      `/invoices/${invoiceId}/entities/${entity.id}/extended-screen/${run.id}`,
    );
  }

  const runTone =
    extendedRun?.status === "failed"
      ? "text-red-700"
      : extendedRun?.status === "completed"
        ? extendedRun.summary_risk === "high"
          ? "text-red-700"
          : extendedRun.summary_risk === "medium"
            ? "text-amber-700"
            : "text-green-700"
        : "text-xlent-muted";
  const externalIssues = (externalStatus.data?.external_sources ?? []).filter(
    (row) => row.status !== "ok" || row.stale || row.error_message,
  );

  return (
    <li className="rounded border border-gray-200 bg-xlent-surface p-3 text-sm">
      <div className="font-medium text-xlent-ink">
        <EditableField
          value={entity.name}
          onSave={(v) => save("name", v)}
          editable={canEdit}
          className="font-medium"
        />
      </div>
      <div className="mt-1 flex flex-wrap gap-2 text-xs text-xlent-muted">
        <EditableField
          value={ENTITY_ROLE_LABELS[entity.role] ?? entity.role}
          onSave={(v) => save("role", v)}
          editable={canEdit}
          type="select"
          options={ENTITY_ROLE_OPTIONS}
          className="font-medium"
        />
        <span>·</span>
        <span className="capitalize">{entity.entity_type === "person" ? "Person" : entity.entity_type === "company" ? "Selskap" : entity.entity_type}</span>
        {entity.country && (
          <>
            <span>·</span>
            <EditableField
              value={entity.country}
              onSave={(v) => save("country", v.toUpperCase())}
              editable={canEdit}
              className="font-mono uppercase"
            />
          </>
        )}
      </div>
      {(entity.address || canEdit) && (
        <div className="mt-1 text-xs text-xlent-muted">
          <EditableField
            value={entity.address}
            onSave={(v) => save("address", v)}
            editable={canEdit}
            placeholder="Adresse…"
          />
        </div>
      )}
      {(entity.phone || entity.email || canEdit) && (
        <div className="mt-1 flex flex-wrap gap-3 text-xs text-xlent-muted">
          {(entity.phone || canEdit) && (
            <EditableField
              value={entity.phone}
              onSave={(v) => save("phone", v)}
              editable={canEdit}
              placeholder="Telefon…"
            />
          )}
          {(entity.email || canEdit) && (
            <EditableField
              value={entity.email}
              onSave={(v) => save("email", v)}
              editable={canEdit}
              placeholder="E-post…"
            />
          )}
        </div>
      )}

      {canRunExtended && (
        <div className="mt-3 rounded border border-gray-200 bg-white p-2">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-xlent-muted">
              Utvidet screening (MVP)
            </span>
            <span className="text-[11px] text-xlent-muted">{aggressiveness}</span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={aggressiveness}
            onChange={(e) => setAggressiveness(Number(e.target.value))}
            className="w-full"
            aria-label="Aggressivitet for utvidet screening"
          />
          <div className="mt-2 text-[11px] text-xlent-muted">
            Min edge confidence: <span className="font-medium">{minEdgeConfidence.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={0.4}
            max={1}
            step={0.02}
            value={minEdgeConfidence}
            onChange={(e) => setMinEdgeConfidence(Number(e.target.value))}
            className="w-full"
            aria-label="Min edge confidence"
          />
          <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-xlent-muted">
            <label className="inline-flex items-center gap-1">
              <input
                type="checkbox"
                checked={selectedOnly}
                onChange={(event) => setSelectedOnly(event.target.checked)}
              />
              Kun valgte kandidater
            </label>
            <label className="inline-flex items-center gap-1">
              <input
                type="checkbox"
                checked={sanctionsNearOnly}
                onChange={(event) => setSanctionsNearOnly(event.target.checked)}
              />
              Kun sanksjonsnære relasjoner
            </label>
          </div>
          <div className="mt-2 rounded border border-gray-200 bg-gray-50 p-2 text-[11px] text-xlent-muted">
            <div className="mb-1 font-medium text-xlent-ink">Kilder (på/av)</div>
            <div className="flex flex-wrap items-center gap-3">
              <label className="inline-flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={enableBrreg}
                  onChange={(event) => setEnableBrreg(event.target.checked)}
                />
                Brreg
              </label>
              <label className="inline-flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={enableUkSanctions}
                  onChange={(event) => setEnableUkSanctions(event.target.checked)}
                />
                UK sanctions
              </label>
              <label className="inline-flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={enableWorldBankDebarred}
                  onChange={(event) => setEnableWorldBankDebarred(event.target.checked)}
                />
                World Bank debarred
              </label>
              <label className="inline-flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={enableAiEntityResearch}
                  onChange={(event) => setEnableAiEntityResearch(event.target.checked)}
                />
                AI entity research
              </label>
              <label className="inline-flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={enableAiWebSearch}
                  onChange={(event) => setEnableAiWebSearch(event.target.checked)}
                />
                AI web search
              </label>
            </div>
          </div>
          {externalIssues.length > 0 && (
            <div className="mt-2 rounded border border-amber-200 bg-amber-50 p-2 text-[11px] text-amber-900">
              <div className="font-medium">Kildevarsel</div>
              <ul className="mt-1 space-y-1">
                {externalIssues.slice(0, 3).map((row) => (
                  <li key={row.source}>
                    {row.source}: {row.status}
                    {row.stale ? " (stale)" : ""}
                    {row.error_message ? ` - ${row.error_message}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="mt-2 flex items-center justify-between gap-2">
            <button
              onClick={() => {
                void triggerExtendedScreening();
              }}
              disabled={startExtended.isPending}
              className={clsx(
                "rounded border px-2 py-1 text-xs font-medium transition-colors",
                startExtended.isPending
                  ? "cursor-not-allowed border-gray-200 text-xlent-muted"
                  : "border-indigo-300 bg-indigo-50 text-indigo-700 hover:bg-indigo-100",
              )}
            >
              {startExtended.isPending ? "Starter …" : "Utvidet screening"}
            </button>
            {extendedRun && (
              <span className={clsx("inline-flex items-center gap-1 text-xs font-medium", runTone)}>
                {extendedRun.status === "running" && (
                  <span
                    aria-hidden="true"
                    className="inline-block h-3 w-3 animate-spin rounded-full border border-current border-t-transparent"
                  />
                )}
                {extendedRun.status === "queued"
                  ? "Køet"
                  : extendedRun.status === "running"
                    ? "Kjører"
                    : extendedRun.status === "failed"
                      ? "Feilet"
                      : `Ferdig (${extendedRun.summary_risk ?? "ukjent"})`}
              </span>
            )}
          </div>
          {extendedRun?.summary_text && (
            <p className="mt-2 text-xs text-xlent-muted">{extendedRun.summary_text}</p>
          )}
          {extendedRun?.error_message && (
            <p className="mt-2 text-xs text-traffic-red">{extendedRun.error_message}</p>
          )}
        </div>
      )}
    </li>
  );
}

function EntitiesSection({
  invoice,
  canEdit,
  canRunExtended,
}: {
  invoice: Invoice;
  canEdit: boolean;
  canRunExtended: boolean;
}) {
  const signatories = invoice.entities.filter((e) => e.role === "signatory");
  const otherEntities = invoice.entities.filter((e) => e.role !== "signatory");

  return (
    <>
      {/* Parter */}
      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
          Parter ({otherEntities.length})
          {canEdit && (
            <span className="ml-2 font-normal normal-case text-xlent-muted/60">
              — klikk et felt for å redigere
            </span>
          )}
        </h2>
        {otherEntities.length === 0 ? (
          <p className="text-sm text-xlent-muted">
            {canEdit
              ? "Ingen parter ennå — auto-ekstraksjon pågår eller ga tomt resultat."
              : "Ingen parter ekstrahert."}
          </p>
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2">
            {otherEntities.map((entity: Entity) => (
              <EntityCard
                key={entity.id}
                entity={entity}
                invoiceId={invoice.id}
                canEdit={canEdit}
                canRunExtended={canRunExtended}
              />
            ))}
          </ul>
        )}
      </section>

      {/* Signatarer */}
      {(signatories.length > 0 || canEdit) && (
        <section className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
            Signatarer ({signatories.length})
          </h2>
          {signatories.length === 0 ? (
            <p className="text-sm text-xlent-muted">Ingen signatarer funnet i dokumentet.</p>
          ) : (
            <ul className="grid gap-2 sm:grid-cols-2">
              {signatories.map((entity: Entity) => (
                <EntityCard
                  key={entity.id}
                  entity={entity}
                  invoiceId={invoice.id}
                  canEdit={canEdit}
                  canRunExtended={canRunExtended}
                />
              ))}
            </ul>
          )}
        </section>
      )}
    </>
  );
}

// ── Sanksjonsscreening-seksjon ────────────────────────────────────────────────

const MATCH_STATUS_LABELS: Record<MatchStatus, string> = {
  clear: "Klar",
  potential_match: "Potensielt treff",
  confirmed_match: "Bekreftet treff",
};

const MATCH_STATUS_COLORS: Record<MatchStatus, string> = {
  clear: "bg-green-50 text-green-700 border-green-200",
  potential_match: "bg-yellow-50 text-yellow-700 border-yellow-200",
  confirmed_match: "bg-red-50 text-red-700 border-red-200",
};

const DATASET_NAMES: Record<string, string> = {
  un_sc_sanctions: "FN Sikkerhedsrad",
  eu_fsf: "EU Financial Sanctions",
  us_ofac_sdn: "US OFAC SDN",
  us_ofac_cons: "US OFAC Consolidated",
  no_un_sanctions: "Norsk FN-sanksjoner",
  no_legacies: "Norge legacies",
  all: "Alle lister",
};

const CANDIDATE_SOURCE_LABELS: Record<string, string> = {
  entity_name: "Entitetsnavn",
  entity_name_fallback: "Entitetsnavn (fallback)",
  entity_email: "E-post på entitet",
  raw_text_email: "E-post i dokumenttekst",
  raw_text_label: "Label/overskrift i dokument",
};

function screeningMood(score: number): { icon: string; cls: string; label: string } {
  if (score >= 0.8) return { icon: "☹", cls: "text-traffic-red", label: "Høy risiko" };
  if (score >= 0.7) return { icon: "😐", cls: "text-traffic-yellow", label: "Potensiell risiko" };
  return { icon: "🙂", cls: "text-traffic-green", label: "Lav risiko" };
}

function ScreeningResultRow({ result }: { result: ScreeningResult }) {
  const score = parseFloat(result.score);
  const pct = (score * 100).toFixed(1);
  const mood = screeningMood(score);

  return (
    <tr className="border-t border-gray-100 text-sm">
      <td className="px-3 py-2 font-medium text-xlent-ink">
        {result.entity_name ?? "—"}
        {result.entity_role && (
          <span className="ml-1 text-xs text-xlent-muted">
            ({result.entity_role})
          </span>
        )}
      </td>
      <td className="px-3 py-2 text-xs text-xlent-muted">
        {DATASET_NAMES[result.dataset] ?? result.dataset}
      </td>
      <td className="px-3 py-2">
        {result.matched_name ?? <span className="text-xlent-muted">—</span>}
      </td>
      <td className="px-3 py-2 text-right tabular-nums">
        <span className="inline-flex items-center gap-1">
          <span className={clsx("text-base leading-none", mood.cls)} title={mood.label}>
            {mood.icon}
          </span>
          <span className={clsx("font-medium", mood.cls)}>{pct}%</span>
        </span>
      </td>
      <td className="px-3 py-2">
        <span
          className={clsx(
            "rounded border px-2 py-0.5 text-xs font-medium",
            MATCH_STATUS_COLORS[result.status],
          )}
        >
          {MATCH_STATUS_LABELS[result.status]}
        </span>
      </td>
      <td className="px-3 py-2 text-xs text-xlent-ink">
        {result.match_explanation ?? <span className="text-xlent-muted">—</span>}
      </td>
      <td className="px-3 py-2 text-xs text-xlent-muted">
        {result.listed_on ?? "—"}
      </td>
    </tr>
  );
}

function ScreeningSection({
  invoiceId,
  embedded = false,
}: {
  invoiceId: string;
  embedded?: boolean;
}) {
  const { data, isLoading, error } = useScreeningResults(invoiceId);
  const {
    data: candidateData,
    isLoading: candidateLoading,
    error: candidateError,
  } = useScreeningCandidates(invoiceId);

  if (isLoading) {
    if (embedded) {
      return <p className="text-sm text-xlent-muted">Laster screeningresultater …</p>;
    }
    return (
      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
          Sanksjonsscreening
        </h2>
        <p className="text-sm text-xlent-muted">Laster screeningresultater …</p>
      </section>
    );
  }

  if (error || !data) {
    return null; // Ikke vist nar screening ikke er kjort enda
  }

  const hasHits = data.confirmed_matches > 0 || data.potential_matches > 0;
  const summaryBg = data.confirmed_matches > 0
    ? "bg-red-50 border-red-200"
    : data.potential_matches > 0
      ? "bg-yellow-50 border-yellow-200"
      : "bg-green-50 border-green-200";

  const significantResults = data.results.filter(
    (r) => r.status !== "clear",
  );
  const clearResults = data.results.filter((r) => r.status === "clear");
  const candidates = candidateData?.items ?? [];

  const content = (
    <>
      {/* Oppsummering */}
      <div className={clsx("mb-4 rounded-lg border p-3", summaryBg)}>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <div>
            <span className="text-xlent-muted">Entiteter sjekket: </span>
            <span className="font-semibold">{data.total_entities}</span>
          </div>
          {data.confirmed_matches > 0 && (
            <div>
              <span className="font-semibold text-traffic-red">
                {data.confirmed_matches} bekreftet treff
              </span>
            </div>
          )}
          {data.potential_matches > 0 && (
            <div>
              <span className="font-semibold text-yellow-700">
                {data.potential_matches} potensielle treff
              </span>
            </div>
          )}
          {!hasHits && (
            <div>
              <span className="font-medium text-green-700">Ingen treff — alle klar</span>
            </div>
          )}
          {data.screened_at && (
            <div className="ml-auto text-xs text-xlent-muted">
              Screenet: {new Date(data.screened_at).toLocaleString("nb-NO")}
            </div>
          )}
        </div>
      </div>

      {/* Treff-tabell */}
      {significantResults.length > 0 && (
        <div className="mb-4 overflow-x-auto">
          <p className="mb-2 text-xs font-medium text-xlent-muted">
            Treff som krever oppfolging:
          </p>
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-xlent-muted">
                <th className="px-3 py-1">Entitet</th>
                <th className="px-3 py-1">Liste</th>
                <th className="px-3 py-1">Matchet navn</th>
                <th className="px-3 py-1 text-right">Score</th>
                <th className="px-3 py-1">Status</th>
                <th className="px-3 py-1">Hvorfor</th>
                <th className="px-3 py-1">Opptatt siden</th>
              </tr>
            </thead>
            <tbody>
              {significantResults.map((r) => (
                <ScreeningResultRow key={r.id} result={r} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Klar-entiteter (sammenfoldet) */}
      {clearResults.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-xlent-muted hover:text-xlent-ink">
            {clearResults.length} entitet(er) uten treff (vis)
          </summary>
          <div className="mt-2 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-xlent-muted">
                  <th className="px-3 py-1">Entitet</th>
                  <th className="px-3 py-1">Liste</th>
                  <th className="px-3 py-1">Matchet navn</th>
                  <th className="px-3 py-1 text-right">Score</th>
                  <th className="px-3 py-1">Status</th>
                  <th className="px-3 py-1">Hvorfor</th>
                  <th className="px-3 py-1">Opptatt siden</th>
                </tr>
              </thead>
              <tbody>
                {clearResults.map((r) => (
                  <ScreeningResultRow key={r.id} result={r} />
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      {/* Debug: kandidater sendt til screeningmotoren */}
      <details className="mt-3 rounded border border-gray-200 bg-gray-50 p-2">
        <summary className="cursor-pointer text-xs font-medium text-xlent-muted hover:text-xlent-ink">
          Screeningkandidater (debug) {candidateData ? `(${candidateData.total})` : ""}
        </summary>
        <div className="mt-2">
          {candidateData && (
            <p className="mb-2 text-[11px] text-xlent-muted">
              Kilde: {candidateData.mode === "snapshot" ? "Snapshot fra siste screening-kjoring" : "Live preview"}
              {candidateData.run_status ? ` | status: ${candidateData.run_status}` : ""}
              {candidateData.run_started_at
                ? ` | startet: ${new Date(candidateData.run_started_at).toLocaleString("nb-NO")}`
                : ""}
              {candidateData.run_finished_at
                ? ` | ferdig: ${new Date(candidateData.run_finished_at).toLocaleString("nb-NO")}`
                : ""}
            </p>
          )}
          {candidateLoading && (
            <p className="text-xs text-xlent-muted">Laster kandidater …</p>
          )}
          {candidateError && (
            <p className="text-xs text-traffic-red">
              Kunne ikke hente kandidater for screening-debug.
            </p>
          )}
          {!candidateLoading && !candidateError && candidates.length === 0 && (
            <p className="text-xs text-xlent-muted">Ingen kandidater tilgjengelig.</p>
          )}
          {!candidateLoading && !candidateError && candidates.length > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead>
                  <tr className="text-left uppercase text-xlent-muted">
                    <th className="px-2 py-1">Entitet</th>
                    <th className="px-2 py-1">Kandidat</th>
                    <th className="px-2 py-1">Kilde</th>
                    <th className="px-2 py-1">E-post</th>
                    <th className="px-2 py-1">Primær</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((candidate: ScreeningCandidateDebug) => (
                    <tr key={candidate.key} className="border-t border-gray-200">
                      <td className="px-2 py-1 text-xlent-ink">
                        {candidate.entity_name ?? "—"}
                        {candidate.entity_role && (
                          <span className="ml-1 text-[11px] text-xlent-muted">
                            ({candidate.entity_role})
                          </span>
                        )}
                      </td>
                      <td className="px-2 py-1 font-medium text-xlent-ink">
                        {candidate.candidate_name}
                      </td>
                      <td className="px-2 py-1 text-xlent-muted">
                        {CANDIDATE_SOURCE_LABELS[candidate.source] ?? candidate.source}
                      </td>
                      <td className="px-2 py-1 text-xlent-muted">
                        {candidate.source_email ?? "—"}
                      </td>
                      <td className="px-2 py-1 text-xlent-muted">
                        {candidate.primary ? "Ja" : "Nei"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </details>
    </>
  );

  if (embedded) {
    return (
      <div className="mt-4 border-t border-gray-200 pt-4">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
          Sanksjonsscreening
        </h3>
        {content}
      </div>
    );
  }

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
        Sanksjonsscreening
      </h2>
      {content}
    </section>
  );
}

function RiskAndScreeningSection({
  invoice,
  hasBeenScreened,
}: {
  invoice: Invoice;
  hasBeenScreened: boolean;
}) {
  const { data: screeningData, isLoading: screeningLoading } = useScreeningResults(invoice.id);
  const { risk, reasons } = computeOverallRisk(invoice);
  const countryInfo = getCountryRisk(invoice.destination_country);
  const screeningPending = invoice.status === "extracted" || invoice.status === "screening";
  const maxScreeningScore = screeningData
    ? screeningData.results.reduce((max, row) => Math.max(max, Number.parseFloat(row.score)), 0)
    : null;

  const screeningSignal = (() => {
    if (invoice.status === "screening") {
      return {
        text: "Screening pågår",
        detail: "Sjekker alle identifiserte parter mot sanksjonslister …",
        cls: "text-blue-700",
      };
    }
    if (invoice.status === "extracted") {
      return {
        text: "Venter på auto-screening",
        detail: "Screening starter normalt automatisk rett etter ekstraksjon.",
        cls: "text-amber-700",
      };
    }
    if (screeningLoading) {
      return {
        text: "Laster screeningresultat",
        detail: "Henter status fra backend …",
        cls: "text-xlent-muted",
      };
    }
    if (!screeningData) {
      return {
        text: "Ingen screeningdata",
        detail: "Ingen resultater ble funnet for denne invoicen.",
        cls: "text-xlent-muted",
      };
    }
    if (screeningData.confirmed_matches > 0) {
      return {
        text: `${screeningData.confirmed_matches} bekreftet treff`,
        detail: `${screeningData.potential_matches} potensielle treff`,
        cls: "text-traffic-red",
      };
    }
    if (screeningData.potential_matches > 0) {
      return {
        text: `${screeningData.potential_matches} potensielle treff`,
        detail: "Ingen bekreftede treff",
        cls: "text-yellow-700",
      };
    }
    return {
      text: "Ingen sanksjonstreff",
      detail: "Alle screenede entiteter er klar.",
      cls: "text-green-700",
    };
  })();

  const strongestScreeningMatch = screeningData?.results.find(
    (row) => Number.parseFloat(row.score) === maxScreeningScore,
  );

  const conclusion = (() => {
    if (
      (maxScreeningScore != null && maxScreeningScore >= 0.8) ||
      (screeningData?.confirmed_matches ?? 0) > 0
    ) {
      return {
        label: "Svært høy risiko",
        icon: "☹",
        cls: "text-traffic-red",
        boxCls: "border-red-200 bg-red-50",
        detail:
          maxScreeningScore != null
            ? `Høyeste screening-score er ${(maxScreeningScore * 100).toFixed(1)}%.`
            : "Bekreftet sanksjonsmatch er funnet.",
      };
    }
    if (
      (maxScreeningScore != null && maxScreeningScore >= 0.7) ||
      (screeningData?.potential_matches ?? 0) > 0 ||
      risk === "orange"
    ) {
      return {
        label: "Høy risiko",
        icon: "😐",
        cls: "text-yellow-700",
        boxCls: "border-yellow-200 bg-yellow-50",
        detail:
          maxScreeningScore != null
            ? `Høyeste screening-score er ${(maxScreeningScore * 100).toFixed(1)}%.`
            : "Potensielle sanksjonstreff krever manuell vurdering.",
      };
    }
    if (risk === "yellow") {
      return {
        label: "Moderat risiko",
        icon: "🙂",
        cls: "text-yellow-700",
        boxCls: "border-yellow-200 bg-yellow-50",
        detail: "Ingen sterke sanksjonssignaler, men normal aktsomhet kreves.",
      };
    }
    return {
      label: "Lav risiko",
      icon: "🙂",
      cls: "text-green-700",
      boxCls: "border-green-200 bg-green-50",
      detail: "Ingen kritiske risikosignaler identifisert.",
    };
  })();

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
        Risiko og screening
      </h2>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
            LLM og landrisiko
          </h3>
          <p className="mt-1 text-sm font-medium text-xlent-ink">
            Destinasjonsland: {invoice.destination_country ?? "ukjent"}
          </p>
          <p className="text-xs text-xlent-muted">
            {TIER_LABELS[countryInfo.tier]} (tier {countryInfo.tier})
          </p>
          <p className="mt-2 text-xs text-xlent-muted">
            LLM-notater: {invoice.comments ? "registrert" : "ingen spesielle notater"}
          </p>
        </div>

        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
            Sanksjonsscreening
          </h3>
          <div className="mt-1 flex items-center gap-2">
            {invoice.status === "screening" && (
              <span className="inline-block h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
            )}
            <p className={clsx("text-sm font-medium", screeningSignal.cls)}>{screeningSignal.text}</p>
          </div>
          <p className="text-xs text-xlent-muted">{screeningSignal.detail}</p>
          {screeningData && (
            <p className="mt-2 text-xs text-xlent-muted">
              Entiteter sjekket: {screeningData.total_entities}
            </p>
          )}
        </div>
      </div>

      {screeningPending && (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
          <h3 className="text-sm font-semibold text-amber-900">
            Sanksjonsscreening ikke fullført
          </h3>
          <p className="mt-1 text-sm text-amber-800">
            Screening skjer normalt automatisk etter ekstraksjon. Hvis den ikke er gjennomført, klikk{" "}
            <span className="font-medium">«Re-screen sanksjoner»</span> øverst til høyre.
          </p>
        </div>
      )}

      {hasBeenScreened && <ScreeningSection invoiceId={invoice.id} embedded />}

      <div className="mt-4 border-t border-gray-200 pt-4">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
          Samlet konklusjon
        </h3>
        {screeningPending ? (
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
            <p className="text-sm font-semibold text-xlent-ink">
              Avventer screening
            </p>
            <p className="mt-1 text-xs text-xlent-muted">
              Samlet konklusjon vises når sanksjonsscreening er ferdig.
            </p>
          </div>
        ) : (
          <div className={clsx("rounded-lg border p-3", conclusion.boxCls)}>
            <div className="flex items-center gap-2">
              <span className={clsx("text-2xl leading-none", conclusion.cls)}>{conclusion.icon}</span>
              <p className={clsx("text-sm font-semibold", conclusion.cls)}>{conclusion.label}</p>
            </div>
            <p className="mt-1 text-xs text-xlent-ink">{conclusion.detail}</p>
            {strongestScreeningMatch && (
              <p className="mt-1 text-xs text-xlent-muted">
                Sterkeste treff: {strongestScreeningMatch.matched_name ?? "ukjent navn"} (
                {strongestScreeningMatch.dataset}, score {(
                  Number.parseFloat(strongestScreeningMatch.score) * 100
                ).toFixed(1)}
                %)
              </p>
            )}
          </div>
        )}
        {reasons.length > 0 && (
          <ul className="mt-2 space-y-1 text-xs text-xlent-muted">
            {reasons.map((reason, idx) => (
              <li key={idx}>• {reason}</li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

// ── Review-beslutningspanel ───────────────────────────────────────────────────

/**
 * Viser gjeldende beslutning (readonly) eller beslutningsgrensesnittet
 * (Godkjenn / Blokker + begrunnelsesfelt) avhengig av invoice-status.
 *
 * Synlig bare for brukere med invoices:review-rettighet og kun når invoice
 * er i status screened, approved eller blocked.
 */
function ReviewDecisionPanel({ invoice }: { invoice: Invoice }) {
  const { user, can } = useAuth();
  const [decision, setDecision] = useState<"approved" | "blocked" | null>(null);
  const [reason, setReason] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const reviewMutation = useReviewInvoice(invoice.id);

  const canReview = can("invoices:review");
  const isReviewable =
    invoice.status === "screened" ||
    invoice.status === "approved" ||
    invoice.status === "blocked";

  if (!canReview || !isReviewable) return null;

  const hasDecision = invoice.status === "approved" || invoice.status === "blocked";

  async function handleSubmit() {
    if (!decision) return;
    if (reason.trim().length < 10) {
      setSubmitError("Begrunnelse må være minst 10 tegn.");
      return;
    }
    setSubmitError(null);
    try {
      await reviewMutation.mutateAsync({
        decision,
        reason: reason.trim(),
        actor: user.name,
      });
      setDecision(null);
      setReason("");
    } catch {
      setSubmitError("Kunne ikke lagre beslutning. Prøv igjen.");
    }
  }

  // ── Readonly-visning av allerede fattet beslutning ──────────────────────────
  if (hasDecision) {
    const isApproved = invoice.status === "approved";
    return (
      <section
        className={clsx(
          "rounded-lg border p-4",
          isApproved
            ? "border-green-200 bg-green-50"
            : "border-red-200 bg-red-50",
        )}
      >
        <h2
          className={clsx(
            "mb-2 text-sm font-semibold",
            isApproved ? "text-green-800" : "text-red-800",
          )}
        >
          {isApproved ? "✓ Faktura godkjent" : "🔒 Faktura blokkert"}
        </h2>
        <dl className="grid grid-cols-2 gap-y-1 text-xs">
          <dt className="text-xlent-muted">Besluttet av</dt>
          <dd className="font-medium text-xlent-ink">
            {invoice.reviewed_by ?? "—"}
          </dd>
          <dt className="text-xlent-muted">Tidspunkt</dt>
          <dd className="text-xlent-ink">
            {invoice.reviewed_at
              ? new Date(invoice.reviewed_at).toLocaleString("nb-NO")
              : "—"}
          </dd>
          <dt className="text-xlent-muted">Begrunnelse</dt>
          <dd className="col-span-1 text-xlent-ink">
            {invoice.review_reason ?? "—"}
          </dd>
        </dl>
        {/* La compliance_officer/admin omgjøre beslutning */}
        <div className="mt-3 border-t border-current/20 pt-3">
          <p className="mb-2 text-xs text-xlent-muted">
            Omgjør beslutning:
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setDecision("approved")}
              className={clsx(
                "rounded border px-3 py-1.5 text-xs font-medium transition-colors",
                decision === "approved"
                  ? "border-green-600 bg-green-600 text-white"
                  : "border-green-300 bg-white text-green-700 hover:bg-green-50",
              )}
            >
              ✓ Godkjenn
            </button>
            <button
              onClick={() => setDecision("blocked")}
              className={clsx(
                "rounded border px-3 py-1.5 text-xs font-medium transition-colors",
                decision === "blocked"
                  ? "border-red-600 bg-red-600 text-white"
                  : "border-red-300 bg-white text-red-700 hover:bg-red-50",
              )}
            >
              🔒 Blokker
            </button>
          </div>
          {decision && (
            <ReviewReasonForm
              decision={decision}
              reason={reason}
              onReasonChange={setReason}
              onSubmit={handleSubmit}
              onCancel={() => { setDecision(null); setReason(""); }}
              isLoading={reviewMutation.isPending}
              error={submitError}
            />
          )}
        </div>
      </section>
    );
  }

  // ── Beslutningsgrensesnitt for ubehandlet faktura ──────────────────────────
  return (
    <section className="rounded-lg border border-amber-200 bg-amber-50 p-4">
      <h2 className="mb-1 text-sm font-semibold text-amber-900">
        Manuell review kreves
      </h2>
      <p className="mb-3 text-xs text-amber-800">
        Faktura med forhøyet compliance-risiko. Godkjenn eller blokker etter
        gjennomgang.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setDecision("approved")}
          className={clsx(
            "rounded border px-3 py-1.5 text-xs font-medium transition-colors",
            decision === "approved"
              ? "border-green-600 bg-green-600 text-white"
              : "border-green-300 bg-white text-green-700 hover:bg-green-50",
          )}
        >
          ✓ Godkjenn
        </button>
        <button
          onClick={() => setDecision("blocked")}
          className={clsx(
            "rounded border px-3 py-1.5 text-xs font-medium transition-colors",
            decision === "blocked"
              ? "border-red-600 bg-red-600 text-white"
              : "border-red-300 bg-white text-red-700 hover:bg-red-50",
          )}
        >
          🔒 Blokker
        </button>
      </div>
      {decision && (
        <ReviewReasonForm
          decision={decision}
          reason={reason}
          onReasonChange={setReason}
          onSubmit={handleSubmit}
          onCancel={() => { setDecision(null); setReason(""); }}
          isLoading={reviewMutation.isPending}
          error={submitError}
        />
      )}
    </section>
  );
}

/** Delt begrunnelsesskjema brukt av begge states. */
function ReviewReasonForm({
  decision,
  reason,
  onReasonChange,
  onSubmit,
  onCancel,
  isLoading,
  error,
}: {
  decision: "approved" | "blocked";
  reason: string;
  onReasonChange: (v: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
  isLoading: boolean;
  error: string | null;
}) {
  const remainingChars = Math.max(0, 10 - reason.trim().length);
  return (
    <div className="mt-3">
      <label className="mb-1 block text-xs font-medium text-xlent-ink">
        Begrunnelse{" "}
        <span className="font-normal text-xlent-muted">(obligatorisk, min. 10 tegn)</span>
      </label>
      <textarea
        value={reason}
        onChange={(e) => onReasonChange(e.target.value)}
        rows={3}
        placeholder="Forklar beslutningen…"
        className="w-full rounded border border-gray-300 px-3 py-2 text-sm text-xlent-ink placeholder-gray-400 focus:border-xlent-primary focus:outline-none focus:ring-1 focus:ring-xlent-primary"
      />
      {remainingChars > 0 && (
        <p className="mt-0.5 text-[11px] text-xlent-muted">
          Skriv {remainingChars} tegn til…
        </p>
      )}
      {error && (
        <p className="mt-1 text-xs text-traffic-red">{error}</p>
      )}
      <div className="mt-2 flex gap-2">
        <button
          onClick={onSubmit}
          disabled={isLoading || reason.trim().length < 10}
          className={clsx(
            "rounded px-3 py-1.5 text-xs font-medium text-white transition-colors",
            decision === "approved"
              ? "bg-green-600 hover:bg-green-700 disabled:bg-green-300"
              : "bg-red-600 hover:bg-red-700 disabled:bg-red-300",
            "disabled:cursor-not-allowed",
          )}
        >
          {isLoading ? "Lagrer…" : decision === "approved" ? "Bekreft godkjenning" : "Bekreft blokkering"}
        </button>
        <button
          onClick={onCancel}
          disabled={isLoading}
          className="rounded border border-gray-300 px-3 py-1.5 text-xs font-medium text-xlent-muted hover:bg-gray-50 disabled:cursor-not-allowed"
        >
          Avbryt
        </button>
      </div>
    </div>
  );
}

function ReviewDataExpander({
  invoice,
  conf,
  canEdit,
}: {
  invoice: Invoice;
  conf: ExtractionConfidence | null | undefined;
  canEdit: boolean;
}) {
  return (
    <details className="rounded-lg border border-gray-200 bg-white">
      <summary className="cursor-pointer px-4 py-3 text-xs font-semibold uppercase tracking-wide text-xlent-muted hover:bg-xlent-surface">
        Metadata og linjer
        <span className="ml-2 normal-case text-xlent-muted/80">
          ({invoice.lines.length} linjer)
        </span>
      </summary>
      <div className="space-y-4 border-t border-gray-200 p-4">
        <MetadataSection invoice={invoice} conf={conf} canEdit={canEdit} />
        <LinesSection invoice={invoice} canEdit={canEdit} />
      </div>
    </details>
  );
}

// ── Metadata med inline-redigering ───────────────────────────────────────────

function MetadataSection({
  invoice,
  conf,
  canEdit,
}: {
  invoice: Invoice;
  conf: ExtractionConfidence | null | undefined;
  canEdit: boolean;
}) {
  const updateFields = useUpdateInvoiceFields(invoice.id);

  async function save(field: string, value: string) {
    await updateFields.mutateAsync({ [field]: value });
  }

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4 text-sm">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
        Metadata
        {canEdit && (
          <span className="ml-2 font-normal normal-case text-xlent-muted/60">
            — klikk et felt for å redigere
          </span>
        )}
      </h2>
      <dl className="grid grid-cols-2 gap-y-2 gap-x-6 text-sm">
        <FieldRow label="Retning" value={<span className="capitalize">{invoice.direction}</span>} />

        <EditableFieldRow
          label="Faktura-nr"
          fieldKey="invoice_number"
          value={invoice.invoice_number}
          confidence={conf?.invoice_number}
          onSave={save}
          editable={canEdit}
        />

        <EditableFieldRow
          label="Beløp"
          fieldKey="total_amount"
          value={
            invoice.total_amount
              ? `${invoice.total_amount}${invoice.currency ? " " + invoice.currency : ""}`
              : null
          }
          confidence={conf?.total_amount}
          onSave={save}
          editable={canEdit}
        />

        <EditableFieldRow
          label="Valuta"
          fieldKey="currency"
          value={invoice.currency}
          confidence={conf?.currency}
          onSave={save}
          editable={canEdit}
        />

        <EditableFieldRow
          label="Faktura-dato"
          fieldKey="invoice_date"
          value={invoice.invoice_date}
          confidence={conf?.invoice_date}
          onSave={save}
          editable={canEdit}
          type="date"
        />

        <EditableFieldRow
          label="Incoterms"
          fieldKey="incoterms"
          value={invoice.incoterms}
          confidence={conf?.incoterms}
          onSave={save}
          editable={canEdit}
        />

        <EditableFieldRow
          label="Transportmåte"
          fieldKey="transport_mode"
          value={invoice.transport_mode}
          confidence={conf?.transport_mode}
          onSave={save}
          editable={canEdit}
          type="select"
          options={TRANSPORT_OPTIONS}
        />

        <EditableFieldRow
          label="Destinasjonsland"
          fieldKey="destination_country"
          value={invoice.destination_country}
          confidence={conf?.destination_country}
          onSave={save}
          editable={canEdit}
        />

        <EditableFieldRow
          label="PO-nummer"
          fieldKey="po_number"
          value={invoice.po_number}
          onSave={save}
          editable={canEdit}
        />

        <EditableFieldRow
          label="MVA-beløp"
          fieldKey="vat_amount"
          value={invoice.vat_amount}
          confidence={conf?.vat_amount}
          onSave={save}
          editable={canEdit}
        />

        <EditableFieldRow
          label="MVA-sats"
          fieldKey="vat_rate"
          value={invoice.vat_rate}
          confidence={conf?.vat_rate}
          onSave={save}
          editable={canEdit}
        />

        <FieldRow
          label="Filstørrelse"
          value={
            invoice.file_size_bytes
              ? `${(invoice.file_size_bytes / 1024).toFixed(1)} kB`
              : null
          }
        />
        <FieldRow
          label="Opprettet"
          value={new Date(invoice.created_at).toLocaleString("nb-NO")}
        />
        {(invoice.input_tokens != null || invoice.output_tokens != null) && (
          <FieldRow
            label="Token-forbruk"
            value={
              `${invoice.input_tokens?.toLocaleString("nb-NO") ?? "?"} inn` +
              ` / ${invoice.output_tokens?.toLocaleString("nb-NO") ?? "?"} ut`
            }
          />
        )}
      </dl>

      {invoice.vat_mismatch_check?.flagged && (
        <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <div className="font-semibold">Mulig feilregistrert MVA ved eksport</div>
          <p className="mt-1 text-xs">
            {invoice.vat_mismatch_check.reason ??
              "Avsenderland og mottakerland avviker, men VAT/MVA er satt. Verifiser manuelt."}
          </p>
        </div>
      )}

      {/* Instruksjoner fra dokumentet — verbatim */}
      {(invoice.instructions || canEdit) && (
        <div className="mt-3">
          <div className="mb-1 flex items-center gap-2 text-xs text-xlent-muted">
            <span>Instruksjoner / notater fra dokumentet</span>
            {conf?.instructions != null && conf.instructions > 0 && (
              <ConfidencePip score={conf.instructions} />
            )}
          </div>
          <div className="rounded border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-xlent-ink">
            <EditableField
              value={invoice.instructions}
              onSave={(v) => save("instructions", v)}
              editable={canEdit}
              placeholder="Ingen instruksjoner funnet…"
              className="w-full whitespace-pre-wrap"
            />
          </div>
        </div>
      )}

      {/* LLM-analyse / compliance-kommentar */}
      {(invoice.comments || canEdit) && (
        <div className="mt-3">
          <div className="mb-1 text-xs text-xlent-muted">LLM-analyse og compliance-notater</div>
          <div className="rounded border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-xlent-ink">
            <EditableField
              value={invoice.comments}
              onSave={(v) => save("comments", v)}
              editable={canEdit}
              placeholder="Ingen compliance-notater…"
              className="w-full"
            />
          </div>
        </div>
      )}
    </section>
  );
}

// ── Hovedside ─────────────────────────────────────────────────────────────────

export function InvoiceDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: invoice, isLoading, error } = useInvoice(id);
  const { can } = useAuth();

  if (isLoading) return <p className="p-6 text-sm text-xlent-muted">Laster …</p>;
  if (error || !invoice) {
    return (
      <div className="p-6">
        <p className="text-sm text-traffic-red">Invoice ikke funnet.</p>
        <Link to="/" className="mt-2 inline-block text-sm text-xlent-primary hover:underline">
          ← Tilbake til oversikten
        </Link>
      </div>
    );
  }

  // Upload-flyten parser og ekstraherer automatisk i bakgrunnen.
  const isProcessing =
    invoice.status === "uploaded" ||
    invoice.status === "parsing" ||
    invoice.status === "extracting" ||
    invoice.status === "screening";
  const canExtract =
    can("invoices:extract") &&
    (invoice.status === "extracted" ||
      invoice.status === "screened" ||
      invoice.status === "extraction_failed");
  const canScreen =
    can("invoices:screen") &&
    (invoice.status === "extracted" ||
      invoice.status === "screened" ||
      invoice.status === "reviewed" ||
      invoice.status === "approved" ||
      invoice.status === "blocked");
  // Redigering er tilgjengelig etter ekstraksjon (og ved feilet ekstraksjon for å korrigere manuelt)
  const canEdit =
    can("invoices:edit") &&
    (invoice.status === "extracted" ||
      invoice.status === "screened" ||
      invoice.status === "extraction_failed");
  const hasBeenScreened =
    invoice.status === "screened" ||
    invoice.status === "reviewed" ||
    invoice.status === "approved" ||
    invoice.status === "blocked";
  const conf = invoice.extraction_confidence;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div>
        <Link to="/" className="text-sm text-xlent-primary hover:underline">
          ← Tilbake
        </Link>
      </div>

      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-xlent-ink">
            {invoice.original_filename ?? "Invoice"}
          </h1>
          {invoice.extraction_model && (
            <p className="mt-1 text-sm text-xlent-muted">
              <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">
                {invoice.extraction_model}
              </span>
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-2">
          {invoice.status !== "screened" && (
            <StatusBadge status={invoice.status} score={invoice.compliance_score} />
          )}
          <div className="flex flex-wrap items-center gap-2">
            {/* Rapport-knapp — tilgjengelig for screened/approved/blocked */}
            {(invoice.status === "screened" ||
              invoice.status === "approved" ||
              invoice.status === "blocked" ||
              invoice.status === "reviewed") && (
              <a
                href={getInvoiceReportUrl(invoice.id)}
                target="_blank"
                rel="noopener noreferrer"
                title="Åpne compliance-rapport i ny fane — bruk Ctrl+P / Cmd+P for å lagre som PDF"
                className="inline-flex items-center gap-1.5 rounded border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-xlent-ink hover:bg-gray-50"
              >
                📄 Rapport
              </a>
            )}
            <ActionButtons
              invoiceId={invoice.id}
              canExtract={canExtract}
              canScreen={canScreen}
              isProcessing={isProcessing}
              isExtracted={
                invoice.status === "extracted" ||
                invoice.status === "screened"
              }
            />
          </div>
        </div>
      </header>

      {/* Prosessering pågår */}
      {isProcessing && (
        <div className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-xlent-ink">
          <span className="inline-block h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-xlent-primary border-t-transparent" />
          <span>
            <span className="font-medium">
              {invoice.status === "extracting"
                ? "Ekstraherer med LLM …"
                : invoice.status === "screening"
                  ? "Screener mot sanksjonslister …"
                  : "Parser dokumentet …"}
            </span>
            <span className="ml-2 text-xlent-muted">
              {invoice.status === "extracting"
                ? "Claude leser fakturaen og henter ut felter."
                : invoice.status === "screening"
                  ? "Sjekker alle parter mot UN, EU, OFAC og norske lister."
                  : invoice.status === "parsing"
                    ? "Vision OCR / Docling kjorer."
                    : "Venter pa bakgrunnsprosessen."}
            </span>
          </span>
        </div>
      )}

      {/* Dokument-inspektor */}
      <DocumentInspector invoice={invoice} />

      {/* Samlet risikovurdering + sanksjonsscreening (ikke for avviste dok.) */}
      {canEdit && invoice.status !== "not_invoice" && (
        <RiskAndScreeningSection
          invoice={invoice}
          hasBeenScreened={hasBeenScreened}
        />
      )}

      {/* Ikke-faktura-avvisning */}
      {invoice.status === "not_invoice" && (
        <NotInvoiceBanner invoice={invoice} />
      )}

      {/* Feilmeldinger (vises ikke for not_invoice — de har eget banner) */}
      {invoice.parsing_error && invoice.status !== "not_invoice" && (
        <section className="rounded-lg border border-traffic-red/50 bg-red-50 p-4">
          <h2 className="mb-1 text-sm font-semibold text-traffic-red">Parsing feilet</h2>
          <pre className="whitespace-pre-wrap text-xs text-traffic-red">{invoice.parsing_error}</pre>
        </section>
      )}
      {invoice.extraction_error && invoice.status !== "not_invoice" && (
        <section className="rounded-lg border border-traffic-red/50 bg-red-50 p-4">
          <h2 className="mb-1 text-sm font-semibold text-traffic-red">Ekstraksjon feilet</h2>
          <pre className="whitespace-pre-wrap text-xs text-traffic-red">{invoice.extraction_error}</pre>
        </section>
      )}

      {/* Review-beslutning (godkjenn/blokker) — vises for compliance_officer og admin */}
      <ReviewDecisionPanel invoice={invoice} />

      {/* Parter og signatarer — alltid synlig */}
      <EntitiesSection invoice={invoice} canEdit={canEdit} canRunExtended={true} />

      {/* Metadata og linjer (lukket som standard) */}
      <ReviewDataExpander invoice={invoice} conf={conf} canEdit={canEdit} />

      {/* Hash-kjedet revisjonslogg */}
      <AuditTimeline invoiceId={invoice.id} />
    </div>
  );
}
