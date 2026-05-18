import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import clsx from "clsx";

import {
  useAddExtendedScreenFeedback,
  useExtendedScreenClaims,
  useExtendedScreenFeedback,
  useExtendedScreeningRun,
  useExtendedScreenSources,
} from "@/hooks/useInvoices";
import type { ExtendedScreenClaim, ExtendedScreenSource } from "@/api/types";

type PayloadSection = {
  [key: string]: unknown;
};

type NodeType = "seed" | "company" | "person" | "country" | "location" | "unknown";

type GraphNode = {
  id: string;
  qid: string;
  label: string;
  type: NodeType;
  x: number;
  y: number;
};

type GraphEdge = {
  id: string;
  from: string;
  to: string;
  label: string;
  confidence: number | null;
  sourceQid: string;
  targetQid: string;
};

type AssociationRow = {
  sourceQid: string;
  sourceLabel: string;
  relation: string;
  confidence: number | null;
  targetQid: string;
  targetName: string;
  targetType: NodeType;
  targetDescription: string | null;
};

type CandidateRow = {
  qid: string;
  label: string;
  confidence: number | null;
  selected: boolean;
  reason: string;
  candidateType: string;
  description: string | null;
};

type SanctionHitRow = {
  targetName: string;
  relation: string;
  sourceQid: string;
  dataset: string;
  score: number | null;
  weightedScore: number | null;
  matchedName: string;
};

type ExternalSourceStatusRow = {
  provider: string;
  enabled: boolean;
  status: string;
  recordCount: number | null;
  fetchedAt: string | null;
  error: string | null;
};

function verificationLabel(status: string): string {
  if (status === "verified") return "Verifisert";
  if (status === "conflicting") return "Konflikt";
  return "Uverifisert";
}

function verificationClass(status: string): string {
  if (status === "verified") return "bg-green-100 text-green-800";
  if (status === "conflicting") return "bg-red-100 text-red-800";
  return "bg-amber-100 text-amber-800";
}

function resolverReason(claim: ExtendedScreenClaim): string {
  const resolver = claim.raw_payload?.resolver;
  if (!resolver || typeof resolver !== "object") return "—";
  const reason = (resolver as Record<string, unknown>).reason_code;
  if (typeof reason !== "string" || reason.trim().length === 0) return "—";
  return reason;
}

function statusLabel(status: string): string {
  if (status === "queued") return "Køet";
  if (status === "running") return "Kjører";
  if (status === "completed") return "Fullført";
  if (status === "failed") return "Feilet";
  return status;
}

function statusClass(status: string): string {
  if (status === "completed") return "text-green-700";
  if (status === "failed") return "text-red-700";
  if (status === "running") return "text-amber-700";
  return "text-xlent-muted";
}

function sanitizeLabel(value: unknown, fallback = "Ukjent"): string {
  if (typeof value !== "string") return fallback;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : fallback;
}

function shortLabel(value: string, max = 24): string {
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1)}…`;
}

function normalizeType(value: unknown): NodeType {
  if (value === "seed") return "seed";
  if (value === "company") return "company";
  if (value === "person") return "person";
  if (value === "country") return "country";
  if (value === "location") return "location";
  return "unknown";
}

function nodeColor(type: NodeType): string {
  if (type === "seed") return "#2563eb";
  if (type === "company") return "#0891b2";
  if (type === "person") return "#7c3aed";
  if (type === "country") return "#dc2626";
  if (type === "location") return "#f59e0b";
  return "#64748b";
}

function parseAssociations(input: unknown[]): AssociationRow[] {
  const rows: AssociationRow[] = [];
  for (const item of input) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const target = (row.target ?? {}) as Record<string, unknown>;

    const targetQid = sanitizeLabel(target.qid, "");
    if (!targetQid) continue;

    rows.push({
      sourceQid: sanitizeLabel(row.source_qid, ""),
      sourceLabel: sanitizeLabel(row.source_label),
      relation: sanitizeLabel(row.relation, "related_to"),
      confidence: typeof row.edge_confidence === "number" ? row.edge_confidence : null,
      targetQid,
      targetName: sanitizeLabel(target.name),
      targetType: normalizeType(target.type),
      targetDescription: typeof target.description === "string" ? target.description : null,
    });
  }
  return rows;
}

function parseCandidates(input: unknown[]): CandidateRow[] {
  const rows: CandidateRow[] = [];
  for (const item of input) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    rows.push({
      qid: sanitizeLabel(row.qid, ""),
      label: sanitizeLabel(row.label),
      confidence: typeof row.confidence === "number" ? row.confidence : null,
      selected: Boolean(row.selected),
      reason: sanitizeLabel(row.reason, "n/a"),
      candidateType: sanitizeLabel(row.candidate_type, "unknown"),
      description: typeof row.description === "string" ? row.description : null,
    });
  }
  return rows;
}

function parseSanctionHits(input: unknown[]): SanctionHitRow[] {
  const rows: SanctionHitRow[] = [];
  for (const item of input) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    rows.push({
      targetName: sanitizeLabel(row.target_name),
      relation: sanitizeLabel(row.relation, "related_to"),
      sourceQid: sanitizeLabel(row.source_qid, ""),
      dataset: sanitizeLabel(row.dataset),
      score: typeof row.score === "number" ? row.score : null,
      weightedScore: typeof row.weighted_score === "number" ? row.weighted_score : null,
      matchedName: sanitizeLabel(row.matched_name),
    });
  }
  return rows;
}

function parseExternalSourceStatus(input: unknown[]): ExternalSourceStatusRow[] {
  const rows: ExternalSourceStatusRow[] = [];
  for (const item of input) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    rows.push({
      provider: sanitizeLabel(row.provider),
      enabled: Boolean(row.enabled),
      status: sanitizeLabel(row.status, "unknown"),
      recordCount: typeof row.record_count === "number" ? row.record_count : null,
      fetchedAt: typeof row.fetched_at === "string" ? row.fetched_at : null,
      error: typeof row.error === "string" ? row.error : null,
    });
  }
  return rows;
}

function buildGraph(
  seed: PayloadSection | null,
  associations: AssociationRow[],
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const width = 900;
  const height = 420;
  const centerX = width / 2;
  const centerY = height / 2;

  const seedEntityId = sanitizeLabel(seed?.entity_id, "seed");
  const seedName = sanitizeLabel(seed?.name, "Seed");

  const nodes: GraphNode[] = [
    {
      id: seedEntityId,
      qid: seedEntityId,
      label: seedName,
      type: "seed",
      x: centerX,
      y: centerY,
    },
  ];

  const targetMap = new Map<string, { label: string; type: NodeType }>();
  for (const assoc of associations) {
    targetMap.set(assoc.targetQid, {
      label: assoc.targetName,
      type: assoc.targetType,
    });
  }

  const targetIds = Array.from(targetMap.keys());
  const radius = 145;
  const step = targetIds.length > 0 ? (Math.PI * 2) / targetIds.length : 0;
  targetIds.forEach((targetId, index) => {
    const target = targetMap.get(targetId);
    if (!target) return;
    const angle = step * index - Math.PI / 2;
    nodes.push({
      id: targetId,
      qid: targetId,
      label: target.label,
      type: target.type,
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    });
  });

  const edges: GraphEdge[] = associations.map((assoc, index) => ({
    id: `edge-${index}-${assoc.sourceQid}-${assoc.targetQid}-${assoc.relation}`,
    from: seedEntityId,
    to: assoc.targetQid,
    label: assoc.relation,
    confidence: assoc.confidence,
    sourceQid: assoc.sourceQid,
    targetQid: assoc.targetQid,
  }));

  return { nodes, edges };
}

export function ExtendedScreeningRunPage() {
  const params = useParams<{
    invoiceId: string;
    entityId: string;
    runId: string;
  }>();
  const invoiceId = params.invoiceId ?? "";
  const entityId = params.entityId ?? "";
  const runId = params.runId ?? "";

  const { data, isLoading, error } = useExtendedScreeningRun(
    invoiceId,
    entityId,
    runId || null,
    Boolean(invoiceId && entityId && runId),
  );
  const feedbackQuery = useExtendedScreenFeedback(
    invoiceId,
    entityId,
    runId || null,
    Boolean(invoiceId && entityId && runId),
  );
  const sourcesQuery = useExtendedScreenSources(
    invoiceId,
    entityId,
    runId || null,
    Boolean(invoiceId && entityId && runId),
  );
  const claimsQuery = useExtendedScreenClaims(
    invoiceId,
    entityId,
    runId || null,
    Boolean(invoiceId && entityId && runId),
  );
  const addFeedback = useAddExtendedScreenFeedback(invoiceId, entityId, runId);

  const payload = (data?.result_payload ?? null) as PayloadSection | null;
  const summary = (payload?.summary ?? null) as PayloadSection | null;
  const summaryCounts =
    summary && summary.counts && typeof summary.counts === "object"
      ? (summary.counts as Record<string, unknown>)
      : null;
  const seed = (payload?.seed ?? null) as PayloadSection | null;
  const meta = (payload?.meta ?? null) as PayloadSection | null;
  const rawAssociations = Array.isArray(payload?.associations) ? payload?.associations : [];
  const rawHits = Array.isArray(payload?.sanctions_hits) ? payload?.sanctions_hits : [];
  const countryExposure = Array.isArray(payload?.country_exposure) ? payload?.country_exposure : [];
  const rawCandidates = Array.isArray(payload?.wikidata_candidates) ? payload?.wikidata_candidates : [];
  const relationDecisions = Array.isArray(payload?.relation_decisions) ? payload?.relation_decisions : [];
  const websiteFindings = Array.isArray(payload?.website_findings) ? payload?.website_findings : [];
  const rawExternalSourceStatus = Array.isArray(payload?.external_source_status)
    ? payload?.external_source_status
    : [];
  const ownership = (payload?.ownership_management ?? {}) as Record<string, unknown>;
  const ownershipParent =
    ownership.ultimate_parent && typeof ownership.ultimate_parent === "object"
      ? (ownership.ultimate_parent as Record<string, unknown>)
      : null;
  const ownershipDirectOwners = Array.isArray(ownership.direct_owners)
    ? ownership.direct_owners
    : [];
  const ownershipBeneficialOwners = Array.isArray(ownership.beneficial_owners)
    ? ownership.beneficial_owners
    : [];
  const ownershipBoardMembers = Array.isArray(ownership.board_members)
    ? ownership.board_members
    : [];
  const ownershipExecutives = Array.isArray(ownership.executives)
    ? ownership.executives
    : [];
  const ownershipEvidence = Array.isArray(ownership.source_evidence)
    ? ownership.source_evidence
    : [];
  const ownershipHits = Array.isArray(ownership.screening_hits)
    ? ownership.screening_hits
    : [];
  const ownershipDiagnostics = Array.isArray(ownership.diagnostics)
    ? ownership.diagnostics
    : [];
  const ownershipAiWebSummary =
    typeof ownership.ai_web_summary === "string" ? ownership.ai_web_summary : null;
  const ownershipAiWebClaims = Array.isArray(ownership.ai_web_claims)
    ? ownership.ai_web_claims
    : [];
  const ownershipWebResearch =
    ownership.web_research && typeof ownership.web_research === "object"
      ? (ownership.web_research as Record<string, unknown>)
      : {};
  const websiteSignalCount = websiteFindings.reduce((acc, item) => {
    const row = (item ?? {}) as Record<string, unknown>;
    const signals = Array.isArray(row.owner_board_management_signals)
      ? row.owner_board_management_signals
      : [];
    return acc + signals.length;
  }, 0);
  const webStats = {
    queriesPlanned: Number(
      ownershipWebResearch.queries_planned ?? summaryCounts?.web_queries_planned ?? 0,
    ),
    queriesExecuted: Number(
      ownershipWebResearch.queries_executed ?? summaryCounts?.web_queries_executed ?? 0,
    ),
    resultsFound: Number(
      ownershipWebResearch.results_found ?? summaryCounts?.web_results_found ?? 0,
    ),
    pagesFetched: Number(
      ownershipWebResearch.pages_fetched ?? summaryCounts?.web_pages_fetched ?? 0,
    ),
    pagesWithSignal: Number(
      ownershipWebResearch.pages_with_signal ?? summaryCounts?.web_pages_with_signal ?? 0,
    ),
    fetchErrors: Number(
      ownershipWebResearch.fetch_errors ?? summaryCounts?.web_fetch_errors ?? 0,
    ),
  };
  const webSearchRan = webStats.queriesExecuted > 0;

  const associations = useMemo(() => parseAssociations(rawAssociations), [rawAssociations]);
  const sanctionHits = useMemo(() => parseSanctionHits(rawHits), [rawHits]);
  const candidates = useMemo(() => parseCandidates(rawCandidates), [rawCandidates]);
  const externalSourceStatus = useMemo(
    () => parseExternalSourceStatus(rawExternalSourceStatus),
    [rawExternalSourceStatus],
  );
  const sourceRows: ExtendedScreenSource[] = sourcesQuery.data ?? [];
  const claimRows: ExtendedScreenClaim[] = claimsQuery.data ?? [];
  const verifiedClaims = useMemo(
    () => claimRows.filter((row) => row.verification_status === "verified"),
    [claimRows],
  );
  const conflictingClaims = useMemo(
    () => claimRows.filter((row) => row.verification_status === "conflicting"),
    [claimRows],
  );
  const unverifiedClaims = useMemo(
    () =>
      claimRows.filter(
        (row) =>
          row.verification_status !== "verified" &&
          row.verification_status !== "conflicting",
      ),
    [claimRows],
  );

  const [selectedOnly, setSelectedOnly] = useState(true);
  const [sanctionsOnly, setSanctionsOnly] = useState(false);
  const [minConfidence, setMinConfidence] = useState(0.6);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [feedbackNote, setFeedbackNote] = useState("");

  const selectedCandidateQids = useMemo(
    () => new Set(candidates.filter((row) => row.selected).map((row) => row.qid)),
    [candidates],
  );
  const hitTargetNames = useMemo(
    () => new Set(sanctionHits.map((row) => row.targetName.toLowerCase())),
    [sanctionHits],
  );
  const hitSourceQids = useMemo(
    () => new Set(sanctionHits.map((row) => row.sourceQid)),
    [sanctionHits],
  );

  const filteredAssociations = useMemo(() => {
    return associations.filter((assoc) => {
      if (selectedOnly && assoc.sourceQid && !selectedCandidateQids.has(assoc.sourceQid)) {
        return false;
      }
      if (
        typeof assoc.confidence === "number" &&
        assoc.confidence < minConfidence
      ) {
        return false;
      }
      if (sanctionsOnly) {
        const inTarget = hitTargetNames.has(assoc.targetName.toLowerCase());
        const inSource = hitSourceQids.has(assoc.sourceQid);
        if (!inTarget && !inSource) {
          return false;
        }
      }
      return true;
    });
  }, [
    associations,
    selectedOnly,
    minConfidence,
    sanctionsOnly,
    selectedCandidateQids,
    hitTargetNames,
    hitSourceQids,
  ]);

  const graph = useMemo(() => buildGraph(seed, filteredAssociations), [seed, filteredAssociations]);
  const nodeById = useMemo(
    () => new Map(graph.nodes.map((node) => [node.id, node])),
    [graph.nodes],
  );
  const edgeById = useMemo(
    () => new Map(graph.edges.map((edge) => [edge.id, edge])),
    [graph.edges],
  );

  const selectedNode = selectedNodeId ? nodeById.get(selectedNodeId) ?? null : null;
  const selectedEdge = selectedEdgeId ? edgeById.get(selectedEdgeId) ?? null : null;

  const feedbackTarget = (() => {
    if (selectedNode) {
      return { qid: selectedNode.qid, name: selectedNode.label };
    }
    if (selectedEdge) {
      const targetNode = nodeById.get(selectedEdge.to);
      return {
        qid: selectedEdge.targetQid,
        name: targetNode?.label ?? selectedEdge.targetQid,
      };
    }
    return null;
  })();

  async function submitFeedback(label: "false_positive" | "good_hit") {
    await addFeedback.mutateAsync({
      feedback_label: label,
      target_qid: feedbackTarget?.qid ?? null,
      target_name: feedbackTarget?.name ?? null,
      note: feedbackNote.trim() || null,
    });
    setFeedbackNote("");
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <Link to={`/invoices/${invoiceId}`} className="text-sm text-xlent-primary hover:underline">
          ← Tilbake til invoice
        </Link>
        {data && (
          <span className={clsx("inline-flex items-center gap-1 text-sm font-medium", statusClass(data.status))}>
            {data.status === "running" && (
              <span
                aria-hidden="true"
                className="inline-block h-3 w-3 animate-spin rounded-full border border-current border-t-transparent"
              />
            )}
            {statusLabel(data.status)}
          </span>
        )}
      </div>

      <header className="rounded-lg border border-gray-200 bg-white p-4">
        <h1 className="text-xl font-semibold text-xlent-ink">Utvidet screening</h1>
        <p className="mt-1 text-sm text-xlent-muted">
          Viser hvordan eksterne signaler brukes i due diligence-vurderingen.
        </p>
        <div className="mt-3 grid gap-2 text-xs text-xlent-muted sm:grid-cols-2">
          <div>
            Run-ID: <code>{runId || "mangler"}</code>
          </div>
          <div>
            Aggressivitet:{" "}
            <span className="font-medium text-xlent-ink">{data?.aggressiveness ?? "—"}</span>
          </div>
          <div>
            Opprettet:{" "}
            <span className="font-medium text-xlent-ink">
              {data?.created_at ? new Date(data.created_at).toLocaleString("nb-NO") : "—"}
            </span>
          </div>
          <div>
            Ferdig:{" "}
            <span className="font-medium text-xlent-ink">
              {data?.finished_at ? new Date(data.finished_at).toLocaleString("nb-NO") : "—"}
            </span>
          </div>
        </div>
      </header>

      {isLoading && (
        <section className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-xlent-muted">
          Laster utvidet screening …
        </section>
      )}

      {error && (
        <section className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-traffic-red">
          Kunne ikke hente utvidet screening-run.
        </section>
      )}

      {data && (
        <>
          {data.summary_text && (
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                Sammendrag
              </h2>
              <p className="text-sm text-xlent-ink">{data.summary_text}</p>
            </section>
          )}

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
              Kilder, Verifisering og Websøk
            </h2>
            <div className="grid gap-2 text-xs text-xlent-muted sm:grid-cols-4">
              <div>
                Kilder: <span className="font-medium text-xlent-ink">{sourceRows.length}</span>
              </div>
              <div>
                Claims: <span className="font-medium text-xlent-ink">{claimRows.length}</span>
              </div>
              <div>
                Verifisert:{" "}
                <span className="font-medium text-green-700">{verifiedClaims.length}</span>
              </div>
              <div>
                Konflikt/Uverifisert:{" "}
                <span className="font-medium text-red-700">
                  {conflictingClaims.length + unverifiedClaims.length}
                </span>
              </div>
            </div>
            <div className="mt-3 rounded border border-gray-200 bg-gray-50 p-2 text-[11px] text-xlent-muted">
              <div className="font-medium text-xlent-ink">Web ingest</div>
              <div className="mt-1">
                Queries planlagt: {webStats.queriesPlanned} | kjørt:{" "}
                {webStats.queriesExecuted} | resultater: {webStats.resultsFound} | sider
                hentet: {webStats.pagesFetched} | sider med signal: {webStats.pagesWithSignal} |
                fetch-feil: {webStats.fetchErrors}
              </div>
              <div className="mt-1">
                {webSearchRan
                  ? webStats.resultsFound > 0
                    ? "Websøk kjørte og fant treff."
                    : "Websøk kjørte, men ga 0 treff i denne kjøringen."
                  : "Websøk er ikke kjørt ennå i denne kjøringen."}
              </div>
              <div className="mt-1">
                Selskapsnettside-crawl: {websiteFindings.length} nettsider, {websiteSignalCount} signaler.
              </div>
            </div>
            {ownershipDiagnostics.length > 0 && (
              <div className="mt-2 rounded border border-amber-200 bg-amber-50 p-2 text-[11px] text-amber-900">
                {ownershipDiagnostics.slice(0, 2).map((row, index) => (
                  <div key={`diag-top-${index}`}>• {String(row)}</div>
                ))}
              </div>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
              Eierskap og Ledelse
            </h2>
            <div className="grid gap-2 text-xs text-xlent-muted sm:grid-cols-4">
              <div>
                Ultimate parent:{" "}
                <span className="font-medium text-xlent-ink">
                  {ownershipParent ? "Ja" : "Nei"}
                </span>
              </div>
              <div>
                Direkte eiere:{" "}
                <span className="font-medium text-xlent-ink">{ownershipDirectOwners.length}</span>
              </div>
              <div>
                Styre + ledelse:{" "}
                <span className="font-medium text-xlent-ink">
                  {ownershipBoardMembers.length + ownershipExecutives.length}
                </span>
              </div>
              <div>
                Eierskapstreff sanksjon:{" "}
                <span className="font-medium text-red-700">{ownershipHits.length}</span>
              </div>
            </div>

            {ownershipParent && (
              <div className="mt-3 rounded border border-gray-200 bg-gray-50 p-3 text-xs">
                <div className="font-medium text-xlent-ink">
                  Ultimate parent: {sanitizeLabel(ownershipParent.name)}
                </div>
                <div className="mt-1 text-xlent-muted">
                  Kilde: {sanitizeLabel(ownershipParent.source_provider)}{" "}
                  {ownershipParent.source_url && typeof ownershipParent.source_url === "string" ? (
                    <a
                      href={ownershipParent.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xlent-primary hover:underline"
                    >
                      lenke
                    </a>
                  ) : null}
                </div>
              </div>
            )}

            {(ownershipDirectOwners.length > 0 ||
              ownershipBeneficialOwners.length > 0 ||
              ownershipBoardMembers.length > 0 ||
              ownershipExecutives.length > 0) && (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[980px] text-left text-sm">
                  <thead className="text-xs uppercase tracking-wide text-xlent-muted">
                    <tr>
                      <th className="px-2 py-2">Kategori</th>
                      <th className="px-2 py-2">Navn</th>
                      <th className="px-2 py-2">Rolle</th>
                      <th className="px-2 py-2">Kilde</th>
                      <th className="px-2 py-2">Confidence</th>
                      <th className="px-2 py-2">Evidens</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ...ownershipDirectOwners.map((row) => ({ category: "Direct owner", row })),
                      ...ownershipBeneficialOwners.map((row) => ({
                        category: "Beneficial owner",
                        row,
                      })),
                      ...ownershipBoardMembers.map((row) => ({ category: "Board member", row })),
                      ...ownershipExecutives.map((row) => ({ category: "Executive", row })),
                    ].map((item, index) => {
                      const row =
                        item.row && typeof item.row === "object"
                          ? (item.row as Record<string, unknown>)
                          : {};
                      return (
                        <tr key={`ownership-row-${index}`} className="border-t border-gray-100">
                          <td className="px-2 py-2 text-xs text-xlent-muted">{item.category}</td>
                          <td className="px-2 py-2 text-xs text-xlent-ink">
                            {sanitizeLabel(row.name)}
                          </td>
                          <td className="px-2 py-2 text-xs text-xlent-muted">
                            {sanitizeLabel(row.role, "—")}
                          </td>
                          <td className="px-2 py-2 text-xs text-xlent-muted">
                            {sanitizeLabel(row.source_provider, "—")}
                            {row.source_url && typeof row.source_url === "string" ? (
                              <>
                                {" "}
                                <a
                                  href={row.source_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-xlent-primary hover:underline"
                                >
                                  lenke
                                </a>
                              </>
                            ) : null}
                          </td>
                          <td className="px-2 py-2 text-xs text-xlent-muted">
                            {typeof row.confidence === "number" ? row.confidence.toFixed(2) : "—"}
                          </td>
                          <td className="max-w-[380px] px-2 py-2 text-xs text-xlent-muted">
                            {sanitizeLabel(row.evidence_excerpt, "—")}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {ownershipHits.length > 0 && (
              <div className="mt-3 rounded border border-red-200 bg-red-50 p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-red-800">
                  Sanksjonstreff via eierskap/ledelse
                </div>
                <ul className="mt-1 space-y-1 text-xs text-red-900">
                  {ownershipHits.slice(0, 8).map((hit, index) => {
                    const row = (hit ?? {}) as Record<string, unknown>;
                    return (
                      <li key={`ownership-hit-${index}`}>
                        {sanitizeLabel(row.target_name)} → {sanitizeLabel(row.matched_name)} (
                        {sanitizeLabel(row.dataset)}) score{" "}
                        {typeof row.score === "number" ? row.score.toFixed(2) : "—"}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {ownershipEvidence.length > 0 && (
              <div className="mt-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                  Kildeevidens
                </div>
                <ul className="mt-1 space-y-1 text-xs text-xlent-muted">
                  {ownershipEvidence.slice(0, 10).map((row, index) => {
                    const item =
                      row && typeof row === "object" ? (row as Record<string, unknown>) : {};
                    return (
                      <li key={`ownership-evidence-${index}`}>
                        {sanitizeLabel(item.source_provider)}: {sanitizeLabel(item.evidence_excerpt)}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {ownershipDiagnostics.length > 0 && (
              <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-amber-900">
                  Diagnostikk
                </div>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-amber-900">
                  {ownershipDiagnostics.slice(0, 6).map((row, index) => (
                    <li key={`ownership-diag-${index}`}>{String(row)}</li>
                  ))}
                </ul>
              </div>
            )}

            {ownershipAiWebSummary && (
              <div className="mt-3 rounded border border-indigo-200 bg-indigo-50 p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-indigo-900">
                  AI Web-sammendrag
                </div>
                <p className="mt-1 text-xs text-indigo-900">{ownershipAiWebSummary}</p>
              </div>
            )}

            {ownershipAiWebClaims.length > 0 && (
              <div className="mt-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                  AI web-claims
                </div>
                <ul className="mt-1 space-y-2 text-xs text-xlent-muted">
                  {ownershipAiWebClaims.slice(0, 8).map((claim, index) => {
                    const row =
                      claim && typeof claim === "object"
                        ? (claim as Record<string, unknown>)
                        : {};
                    return (
                      <li key={`ai-web-claim-${index}`} className="rounded border border-gray-200 bg-gray-50 p-2">
                        <div className="font-medium text-xlent-ink">
                          {sanitizeLabel(row.claim, "—")}
                        </div>
                        <div className="mt-1">
                          confidence:{" "}
                          {typeof row.confidence === "number" ? row.confidence.toFixed(2) : "—"}
                        </div>
                        <div className="mt-1">{sanitizeLabel(row.quote, "—")}</div>
                        {typeof row.source_url === "string" && row.source_url.trim().length > 0 && (
                          <div className="mt-1">
                            <a
                              href={row.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-xlent-primary hover:underline"
                            >
                              Kilde
                            </a>
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
              Claim-Evidens
            </h2>
            {claimsQuery.isLoading ? (
              <p className="text-sm text-xlent-muted">Laster claims …</p>
            ) : claimRows.length === 0 ? (
              <p className="text-sm text-xlent-muted">Ingen persisted claims for denne run-en.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[980px] text-left text-sm">
                  <thead className="text-xs uppercase tracking-wide text-xlent-muted">
                    <tr>
                      <th className="px-2 py-2">Type</th>
                      <th className="px-2 py-2">Subject</th>
                      <th className="px-2 py-2">Object</th>
                      <th className="px-2 py-2">Kilde</th>
                      <th className="px-2 py-2">Confidence</th>
                      <th className="px-2 py-2">Status</th>
                      <th className="px-2 py-2">Resolver</th>
                      <th className="px-2 py-2">Evidens</th>
                    </tr>
                  </thead>
                  <tbody>
                    {claimRows.map((row) => (
                      <tr key={row.id} className="border-t border-gray-100">
                        <td className="px-2 py-2 text-xs text-xlent-muted">{row.claim_type}</td>
                        <td className="px-2 py-2 text-xs text-xlent-muted">{row.claim_subject}</td>
                        <td className="px-2 py-2 text-xs text-xlent-muted">{row.claim_object}</td>
                        <td className="px-2 py-2 text-xs text-xlent-muted">
                          {row.source_provider}
                          {row.source_url ? (
                            <>
                              {" "}
                              <a
                                href={row.source_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-xlent-primary hover:underline"
                              >
                                lenke
                              </a>
                            </>
                          ) : null}
                        </td>
                        <td className="px-2 py-2 text-xs text-xlent-muted">
                          {typeof row.confidence === "number" ? row.confidence.toFixed(2) : "—"}
                        </td>
                        <td className="px-2 py-2">
                          <span
                            className={clsx(
                              "rounded px-2 py-1 text-xs font-medium",
                              verificationClass(row.verification_status),
                            )}
                          >
                            {verificationLabel(row.verification_status)}
                          </span>
                        </td>
                        <td className="px-2 py-2 text-xs text-xlent-muted">
                          {resolverReason(row)}
                        </td>
                        <td className="max-w-[380px] px-2 py-2 text-xs text-xlent-muted">
                          {row.quoted_text ? row.quoted_text : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
              Kildelog
            </h2>
            {sourcesQuery.isLoading ? (
              <p className="text-sm text-xlent-muted">Laster kilder …</p>
            ) : sourceRows.length === 0 ? (
              <p className="text-sm text-xlent-muted">Ingen persisted kilder for denne run-en.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[860px] text-left text-sm">
                  <thead className="text-xs uppercase tracking-wide text-xlent-muted">
                    <tr>
                      <th className="px-2 py-2">Provider</th>
                      <th className="px-2 py-2">Tittel</th>
                      <th className="px-2 py-2">Domene</th>
                      <th className="px-2 py-2">Hentet</th>
                      <th className="px-2 py-2">URL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sourceRows.map((row) => (
                      <tr key={row.id} className="border-t border-gray-100">
                        <td className="px-2 py-2 text-xs text-xlent-muted">{row.provider}</td>
                        <td className="px-2 py-2 text-xs text-xlent-muted">
                          {row.source_title ?? "—"}
                        </td>
                        <td className="px-2 py-2 text-xs text-xlent-muted">
                          {row.source_domain ?? "—"}
                        </td>
                        <td className="px-2 py-2 text-xs text-xlent-muted">
                          {new Date(row.fetched_at).toLocaleString("nb-NO")}
                        </td>
                        <td className="px-2 py-2 text-xs text-xlent-muted">
                          <a
                            href={row.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xlent-primary hover:underline"
                          >
                            åpne
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
              Grunnlag
            </h2>
            <div className="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <div className="text-xs text-xlent-muted">Seed-entitet</div>
                <div className="font-medium text-xlent-ink">{sanitizeLabel(seed?.name, "—")}</div>
              </div>
              <div>
                <div className="text-xs text-xlent-muted">Seed-land</div>
                <div className="font-medium text-xlent-ink">{sanitizeLabel(seed?.country, "—")}</div>
              </div>
              <div>
                <div className="text-xs text-xlent-muted">Maks hopp</div>
                <div className="font-medium text-xlent-ink">
                  {typeof meta?.max_hops === "number" ? meta.max_hops : "—"}
                </div>
              </div>
              <div>
                <div className="text-xs text-xlent-muted">Min edge-confidence (backend)</div>
                <div className="font-medium text-xlent-ink">
                  {typeof meta?.min_edge_confidence === "number"
                    ? meta.min_edge_confidence
                    : "—"}
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
              Filter (Presisjon)
            </h2>
            <div className="grid gap-3 text-sm md:grid-cols-3">
              <label className="inline-flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={selectedOnly}
                  onChange={(event) => setSelectedOnly(event.target.checked)}
                />
                <span>Kun valgte kandidater</span>
              </label>
              <label className="inline-flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={sanctionsOnly}
                  onChange={(event) => setSanctionsOnly(event.target.checked)}
                />
                <span>Kun sanksjonsnære relasjoner</span>
              </label>
              <label className="space-y-1">
                <div className="text-xs text-xlent-muted">
                  Min edge confidence: <span className="font-medium text-xlent-ink">{minConfidence.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min={0.4}
                  max={1}
                  step={0.02}
                  value={minConfidence}
                  onChange={(event) => setMinConfidence(Number(event.target.value))}
                  className="w-full"
                />
              </label>
            </div>
            <div className="mt-2 text-xs text-xlent-muted">
              Viser {filteredAssociations.length} av {associations.length} relasjoner etter filter.
            </div>
            <div className="mt-1 text-xs text-xlent-muted">
              Kjøringskonfig: selected_only=
              {String(data?.run_config?.selected_only ?? true)}, sanctions_near_only=
              {String(data?.run_config?.sanctions_near_only ?? false)}, min_edge_confidence=
              {(data?.run_config?.min_edge_confidence ?? 0.6).toFixed(2)},
              brreg={String(data?.run_config?.enable_brreg ?? true)},
              uk_sanctions={String(data?.run_config?.enable_uk_sanctions ?? true)},
              world_bank={String(data?.run_config?.enable_world_bank_debarred ?? true)},
              ai_entity_research={String(data?.run_config?.enable_ai_entity_research ?? true)},
              ai_web_search={String(data?.run_config?.enable_ai_web_search ?? true)}
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
              Eksterne Kilder Status
            </h2>
            {externalSourceStatus.length === 0 ? (
              <p className="text-sm text-xlent-muted">Ingen ekstern status registrert.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[860px] text-left text-sm">
                  <thead className="text-xs uppercase tracking-wide text-xlent-muted">
                    <tr>
                      <th className="px-2 py-2">Kilde</th>
                      <th className="px-2 py-2">Enabled</th>
                      <th className="px-2 py-2">Status</th>
                      <th className="px-2 py-2">Records</th>
                      <th className="px-2 py-2">Sist Hentet</th>
                      <th className="px-2 py-2">Feil</th>
                    </tr>
                  </thead>
                  <tbody>
                    {externalSourceStatus.map((row, index) => (
                      <tr key={`ext-src-${index}`} className="border-t border-gray-100">
                        <td className="px-2 py-2 text-xs text-xlent-muted">{row.provider}</td>
                        <td className="px-2 py-2 text-xs text-xlent-muted">
                          {row.enabled ? "Ja" : "Nei"}
                        </td>
                        <td className="px-2 py-2 text-xs text-xlent-muted">{row.status}</td>
                        <td className="px-2 py-2 text-xs text-xlent-muted">
                          {row.recordCount != null ? row.recordCount.toLocaleString("nb-NO") : "—"}
                        </td>
                        <td className="px-2 py-2 text-xs text-xlent-muted">
                          {row.fetchedAt ? new Date(row.fetchedAt).toLocaleString("nb-NO") : "—"}
                        </td>
                        <td className="px-2 py-2 text-xs text-traffic-red">
                          {row.error ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
              Nettverksvisualisering
            </h2>
            {graph.nodes.length <= 1 ? (
              <div className="rounded border border-dashed border-gray-300 bg-gray-50 p-4 text-sm text-xlent-muted">
                Ingen relasjoner å visualisere med nåværende filter.
              </div>
            ) : (
              <div className="overflow-x-auto rounded border border-gray-200 bg-gray-50 p-2">
                <svg viewBox="0 0 900 420" className="h-[420px] w-full min-w-[900px]">
                  {graph.edges.map((edge) => {
                    const fromNode = nodeById.get(edge.from);
                    const toNode = nodeById.get(edge.to);
                    if (!fromNode || !toNode) return null;
                    const isSelected = selectedEdgeId === edge.id;
                    return (
                      <g key={edge.id}>
                        <line
                          x1={fromNode.x}
                          y1={fromNode.y}
                          x2={toNode.x}
                          y2={toNode.y}
                          stroke={isSelected ? "#0f172a" : "#cbd5e1"}
                          strokeWidth={isSelected ? 2.5 : 1.6}
                          className="cursor-pointer"
                          onClick={() => {
                            setSelectedEdgeId(edge.id);
                            setSelectedNodeId(null);
                          }}
                        />
                        <text
                          x={(fromNode.x + toNode.x) / 2}
                          y={(fromNode.y + toNode.y) / 2}
                          textAnchor="middle"
                          fill={isSelected ? "#0f172a" : "#475569"}
                          fontSize={10}
                          className="cursor-pointer select-none"
                          onClick={() => {
                            setSelectedEdgeId(edge.id);
                            setSelectedNodeId(null);
                          }}
                        >
                          {shortLabel(edge.label, 18)}
                        </text>
                      </g>
                    );
                  })}

                  {graph.nodes.map((node) => {
                    const isSelected = selectedNodeId === node.id;
                    return (
                      <g
                        key={node.id}
                        className="cursor-pointer"
                        onClick={() => {
                          setSelectedNodeId(node.id);
                          setSelectedEdgeId(null);
                        }}
                      >
                        <circle
                          cx={node.x}
                          cy={node.y}
                          r={node.type === "seed" ? 24 : 18}
                          fill={nodeColor(node.type)}
                          stroke={isSelected ? "#0f172a" : "none"}
                          strokeWidth={isSelected ? 2 : 0}
                          opacity={0.92}
                        />
                        <text
                          x={node.x}
                          y={node.y + (node.type === "seed" ? 38 : 32)}
                          textAnchor="middle"
                          fill="#0f172a"
                          fontSize={12}
                          fontWeight={500}
                        >
                          {shortLabel(node.label)}
                        </text>
                      </g>
                    );
                  })}
                </svg>
              </div>
            )}

            <div className="mt-2 flex flex-wrap gap-3 text-xs text-xlent-muted">
              <span className="inline-flex items-center gap-1">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-blue-600" />
                Seed
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-cyan-600" />
                Selskap
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-violet-600" />
                Person
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-red-600" />
                Land
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-500" />
                Lokasjon
              </span>
            </div>

            {(selectedNode || selectedEdge) && (
              <div className="mt-3 rounded border border-gray-200 bg-gray-50 p-3 text-sm">
                {selectedNode && (
                  <>
                    <div className="font-semibold text-xlent-ink">Valgt node</div>
                    <div className="mt-1 text-xs text-xlent-muted">
                      Navn: {selectedNode.label} | Type: {selectedNode.type} | ID:{" "}
                      <code>{selectedNode.qid}</code>
                    </div>
                    <div className="mt-2 text-xs text-xlent-muted">
                      Relasjoner:{" "}
                      {
                        filteredAssociations.filter((assoc) => assoc.targetQid === selectedNode.qid)
                          .length
                      }
                    </div>
                  </>
                )}
                {selectedEdge && (
                  <>
                    <div className="font-semibold text-xlent-ink">Valgt relasjon</div>
                    <div className="mt-1 text-xs text-xlent-muted">
                      Relasjon: {selectedEdge.label} | Confidence:{" "}
                      {typeof selectedEdge.confidence === "number"
                        ? selectedEdge.confidence.toFixed(2)
                        : "—"}
                    </div>
                    <div className="mt-1 text-xs text-xlent-muted">
                      Fra <code>{selectedEdge.sourceQid || "seed"}</code> til{" "}
                      <code>{selectedEdge.targetQid}</code>
                    </div>
                  </>
                )}
                <div className="mt-3 border-t border-gray-200 pt-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                    Analyst Feedback
                  </div>
                  <div className="mt-1 text-xs text-xlent-muted">
                    Target: {feedbackTarget?.name ?? "Ingen valgt"}
                    {feedbackTarget?.qid ? (
                      <>
                        {" "}
                        (<code>{feedbackTarget.qid}</code>)
                      </>
                    ) : null}
                  </div>
                  <textarea
                    value={feedbackNote}
                    onChange={(event) => setFeedbackNote(event.target.value)}
                    placeholder="Kort notat (valgfritt)"
                    className="mt-2 w-full rounded border border-gray-300 px-2 py-1 text-xs"
                    rows={2}
                  />
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={() => {
                        void submitFeedback("false_positive");
                      }}
                      disabled={addFeedback.isPending || !feedbackTarget}
                      className={clsx(
                        "rounded border px-2 py-1 text-xs font-medium",
                        addFeedback.isPending || !feedbackTarget
                          ? "cursor-not-allowed border-gray-200 text-xlent-muted"
                          : "border-red-300 bg-red-50 text-red-700 hover:bg-red-100",
                      )}
                    >
                      Mark false positive
                    </button>
                    <button
                      onClick={() => {
                        void submitFeedback("good_hit");
                      }}
                      disabled={addFeedback.isPending || !feedbackTarget}
                      className={clsx(
                        "rounded border px-2 py-1 text-xs font-medium",
                        addFeedback.isPending || !feedbackTarget
                          ? "cursor-not-allowed border-gray-200 text-xlent-muted"
                          : "border-green-300 bg-green-50 text-green-700 hover:bg-green-100",
                      )}
                    >
                      Mark good hit
                    </button>
                  </div>
                </div>
              </div>
            )}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <details>
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                Kandidater (Wikidata) ({candidates.length})
              </summary>
              <div className="mt-3">
                {candidates.length === 0 ? (
                  <p className="text-sm text-xlent-muted">Ingen kandidater i denne kjøringen.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[760px] text-left text-sm">
                      <thead className="text-xs uppercase tracking-wide text-xlent-muted">
                        <tr>
                          <th className="px-2 py-2">Navn</th>
                          <th className="px-2 py-2">QID</th>
                          <th className="px-2 py-2">Type</th>
                          <th className="px-2 py-2">Confidence</th>
                          <th className="px-2 py-2">Valg</th>
                          <th className="px-2 py-2">Årsak</th>
                        </tr>
                      </thead>
                      <tbody>
                        {candidates.map((row, index) => (
                          <tr key={`${row.qid}-${index}`} className="border-t border-gray-100">
                            <td className="px-2 py-2 text-xlent-ink">{row.label}</td>
                            <td className="px-2 py-2 text-xs text-xlent-muted">{row.qid || "—"}</td>
                            <td className="px-2 py-2 text-xs text-xlent-muted">{row.candidateType}</td>
                            <td className="px-2 py-2 text-xs text-xlent-muted">
                              {typeof row.confidence === "number" ? row.confidence.toFixed(2) : "—"}
                            </td>
                            <td className="px-2 py-2">
                              <span
                                className={clsx(
                                  "rounded px-2 py-1 text-xs font-medium",
                                  row.selected
                                    ? "bg-green-100 text-green-800"
                                    : "bg-gray-100 text-gray-700",
                                )}
                              >
                                {row.selected ? "Valgt" : "Avvist"}
                              </span>
                            </td>
                            <td className="px-2 py-2 text-xs text-xlent-muted">{row.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </details>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
              Risikofunn
            </h2>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                  Sanksjonstreff
                </div>
                {sanctionHits.length === 0 ? (
                  <p className="text-sm text-xlent-muted">Ingen kvalifiserte treff i denne kjøringen.</p>
                ) : (
                  <ul className="space-y-2 text-sm text-xlent-ink">
                    {sanctionHits.map((hit, index) => (
                      <li key={`hit-${index}`} className="rounded border border-amber-200 bg-amber-50 p-3">
                        <div className="font-medium">
                          {hit.targetName} → {hit.matchedName}
                        </div>
                        <div className="mt-1 text-xs text-amber-900">
                          Dataset: {hit.dataset} | Score:{" "}
                          {typeof hit.score === "number" ? hit.score.toFixed(2) : "—"} | Vektet:{" "}
                          {typeof hit.weightedScore === "number" ? hit.weightedScore.toFixed(2) : "—"} | Relasjon:{" "}
                          {hit.relation}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                  Landeksponering
                </div>
                {countryExposure.length === 0 ? (
                  <p className="text-sm text-xlent-muted">Ingen landeksponeringer registrert.</p>
                ) : (
                  <ul className="space-y-2 text-sm text-xlent-ink">
                    {countryExposure.map((item, index) => {
                      const row = (item ?? {}) as Record<string, unknown>;
                      return (
                        <li key={`country-${index}`} className="rounded border border-red-200 bg-red-50 p-3">
                          <div className="font-medium">{sanitizeLabel(row.country)}</div>
                          <div className="mt-1 text-xs text-red-900">
                            {sanitizeLabel(row.reason)} | Kilde: {sanitizeLabel(row.source)}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <details>
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                Decision Trace (Relasjoner) ({relationDecisions.length})
              </summary>
              <div className="mt-3">
                {relationDecisions.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[820px] text-left text-sm">
                      <thead className="text-xs uppercase tracking-wide text-xlent-muted">
                        <tr>
                          <th className="px-2 py-2">Source</th>
                          <th className="px-2 py-2">Relasjon</th>
                          <th className="px-2 py-2">Target</th>
                          <th className="px-2 py-2">Confidence</th>
                          <th className="px-2 py-2">Inkludert</th>
                          <th className="px-2 py-2">Årsak</th>
                        </tr>
                      </thead>
                      <tbody>
                        {relationDecisions.map((item, index) => {
                          const row = (item ?? {}) as Record<string, unknown>;
                          const included = Boolean(row.included);
                          return (
                            <tr key={`decision-${index}`} className="border-t border-gray-100">
                              <td className="px-2 py-2 text-xs text-xlent-muted">
                                {sanitizeLabel(row.source_qid, "—")}
                              </td>
                              <td className="px-2 py-2 text-xs text-xlent-muted">
                                {sanitizeLabel(row.relation)}
                              </td>
                              <td className="px-2 py-2 text-xs text-xlent-muted">
                                {sanitizeLabel(row.target_name)}
                              </td>
                              <td className="px-2 py-2 text-xs text-xlent-muted">
                                {typeof row.edge_confidence === "number"
                                  ? row.edge_confidence.toFixed(2)
                                  : "—"}
                              </td>
                              <td className="px-2 py-2">
                                <span
                                  className={clsx(
                                    "rounded px-2 py-1 text-xs font-medium",
                                    included
                                      ? "bg-green-100 text-green-800"
                                      : "bg-gray-100 text-gray-700",
                                  )}
                                >
                                  {included ? "Ja" : "Nei"}
                                </span>
                              </td>
                              <td className="px-2 py-2 text-xs text-xlent-muted">
                                {sanitizeLabel(row.excluded_reason, included ? "ok" : "filtered")}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-xlent-muted">Ingen relasjonsbeslutninger tilgjengelig.</p>
                )}
              </div>
            </details>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
              Analyst Feedback Historikk
            </h2>
            {feedbackQuery.isLoading ? (
              <p className="text-sm text-xlent-muted">Laster feedback …</p>
            ) : feedbackQuery.data && feedbackQuery.data.length > 0 ? (
              <ul className="space-y-2 text-sm text-xlent-ink">
                {feedbackQuery.data.map((row) => (
                  <li key={row.id} className="rounded border border-gray-200 bg-gray-50 p-3">
                    <div className="font-medium">
                      {row.feedback_label === "false_positive" ? "False positive" : "Good hit"}
                    </div>
                    <div className="mt-1 text-xs text-xlent-muted">
                      Target: {row.target_name ?? "—"} {row.target_qid ? `(${row.target_qid})` : ""}
                    </div>
                    {row.note && <div className="mt-1 text-xs text-xlent-muted">Note: {row.note}</div>}
                    <div className="mt-1 text-xs text-xlent-muted">
                      {new Date(row.created_at).toLocaleString("nb-NO")}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-xlent-muted">Ingen feedback registrert ennå.</p>
            )}
          </section>

          {data.error_message && (
            <section className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-traffic-red">
              {data.error_message}
            </section>
          )}

          {summary?.notes && Array.isArray(summary.notes) && (
            <section className="rounded-lg border border-gray-200 bg-white p-4">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                Notater
              </h2>
              <ul className="space-y-1 text-sm text-xlent-muted">
                {summary.notes.map((note, index) => (
                  <li key={index}>• {String(note)}</li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
