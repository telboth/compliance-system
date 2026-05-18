/**
 * AuditTimeline — kronologisk visning av hash-kjedet audit-logg.
 *
 * Viser alle hendelser for en invoice med tidsstempel, handling, aktør og
 * hash-kjede-integritet. Brukes i InvoiceDetail.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { getAuditLog, verifyAuditChain } from "@/api/audit";
import type { AuditLogEntry } from "@/api/audit";

// ── Ikon per handling ─────────────────────────────────────────────────────────

function actionIcon(action: string): string {
  if (action.startsWith("invoice.")) return "📄";
  if (action.startsWith("screening.") || action.startsWith("rule.")) return "🛡️";
  if (action.startsWith("field.")) return "✏️";
  if (action.startsWith("agreement.")) return "📋";
  if (action.startsWith("extraction.")) return "🤖";
  return "📌";
}

function actionColor(action: string): string {
  if (action.includes("blocked") || action.includes("failed")) return "bg-red-100 text-red-800";
  if (action.includes("triggered") || action.includes("potential")) return "bg-orange-100 text-orange-800";
  if (action.includes("approved") || action.includes("completed") || action.includes("compliant")) return "bg-green-100 text-green-800";
  return "bg-blue-100 text-blue-800";
}

// ── Enkelt audit-innslag ───────────────────────────────────────────────────────

function AuditEntry({ entry, showHash }: { entry: AuditLogEntry; showHash: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetails = entry.details && Object.keys(entry.details).length > 0;
  const ts = new Date(entry.created_at);

  return (
    <div className="flex gap-4">
      {/* Tidslinje-linje */}
      <div className="flex flex-col items-center">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-base shadow-sm ring-1 ring-gray-200">
          {actionIcon(entry.action)}
        </div>
        <div className="mt-1 flex-1 border-l border-dashed border-gray-200" />
      </div>

      {/* Innhold */}
      <div className="mb-4 flex-1 min-w-0">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span
            className={clsx(
              "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
              actionColor(entry.action),
            )}
          >
            {entry.action}
          </span>
          <span className="text-xs text-xlent-muted">
            {ts.toLocaleDateString("nb-NO", { day: "numeric", month: "short", year: "numeric" })}
            {" "}
            {ts.toLocaleTimeString("nb-NO", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
          </span>
          <span className="ml-auto text-xs text-xlent-muted">
            av <span className="font-medium text-xlent-ink">{entry.actor}</span>
          </span>
        </div>

        {hasDetails && (
          <button
            onClick={() => setExpanded((e) => !e)}
            className="mt-1 text-xs text-xlent-primary hover:underline"
          >
            {expanded ? "Skjul detaljer ▲" : "Vis detaljer ▼"}
          </button>
        )}

        {expanded && hasDetails && (
          <pre className="mt-2 overflow-x-auto rounded bg-gray-50 p-2 text-xs text-gray-700">
            {JSON.stringify(entry.details, null, 2)}
          </pre>
        )}

        {showHash && (
          <p className="mt-1 font-mono text-xs text-gray-300 truncate">
            #{entry.current_hash.slice(0, 16)}…
          </p>
        )}
      </div>
    </div>
  );
}

// ── Hovedelement ──────────────────────────────────────────────────────────────

interface AuditTimelineProps {
  invoiceId: string;
}

export function AuditTimeline({ invoiceId }: AuditTimelineProps) {
  const [showHashes, setShowHashes] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{ ok: boolean; errors: string[] } | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["audit-log", invoiceId],
    queryFn: () => getAuditLog(invoiceId),
    staleTime: 10_000,
  });

  const handleVerify = async () => {
    setVerifying(true);
    try {
      const result = await verifyAuditChain(invoiceId);
      setVerifyResult(result);
    } catch {
      setVerifyResult({ ok: false, errors: ["Kunne ikke verifisere kjeden"] });
    } finally {
      setVerifying(false);
    }
  };

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-6">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-xlent-ink">Revisjonslogg</h2>
          <p className="text-xs text-xlent-muted">
            Hash-kjedet, append-only sporlogg — alle hendelser for denne fakturaen.
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            onClick={() => setShowHashes((s) => !s)}
            className="rounded border border-gray-200 px-2 py-1 text-xs text-xlent-muted hover:bg-gray-50"
          >
            {showHashes ? "Skjul hashes" : "Vis hashes"}
          </button>
          <button
            onClick={handleVerify}
            disabled={verifying}
            className="rounded border border-gray-200 px-2 py-1 text-xs text-xlent-muted hover:bg-gray-50 disabled:opacity-50"
          >
            {verifying ? "Verifiserer…" : "Verifiser kjede"}
          </button>
        </div>
      </div>

      {verifyResult && (
        <div
          className={clsx(
            "mb-4 rounded border px-3 py-2 text-xs",
            verifyResult.ok
              ? "border-green-200 bg-green-50 text-green-800"
              : "border-red-200 bg-red-50 text-red-800",
          )}
        >
          {verifyResult.ok ? (
            "✓ Hash-kjeden er intakt — ingen innslag har blitt endret."
          ) : (
            <>
              <p className="font-medium">Kjede-brudd oppdaget!</p>
              {verifyResult.errors.map((e, i) => (
                <p key={i} className="mt-0.5">
                  {e}
                </p>
              ))}
            </>
          )}
        </div>
      )}

      {isLoading && (
        <p className="py-8 text-center text-sm text-xlent-muted">Laster revisjonslogg …</p>
      )}
      {error && (
        <p className="py-4 text-center text-sm text-traffic-red">Kunne ikke laste logg.</p>
      )}

      {data && data.items.length === 0 && (
        <p className="py-8 text-center text-sm text-xlent-muted">
          Ingen audit-innslag ennå for denne fakturaen.
        </p>
      )}

      {data && data.items.length > 0 && (
        <div className="pt-2">
          {data.items.map((entry) => (
            <AuditEntry key={entry.id} entry={entry} showHash={showHashes} />
          ))}
          <p className="mt-2 text-xs text-gray-400">
            {data.total} innslag totalt
          </p>
        </div>
      )}
    </section>
  );
}
