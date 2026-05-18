import { useMemo, useState } from "react";
import clsx from "clsx";
import { Link } from "react-router-dom";

import {
  usePipelineMetrics,
  usePipelineRecovery,
  useRetryPipelineInvoice,
} from "@/hooks/useInvoices";

const selectCls =
  "rounded border border-gray-200 bg-white px-2 py-1 text-xs text-xlent-ink focus:outline-none focus:ring-1 focus:ring-xlent-primary";

function fmtSeconds(value: number | null): string {
  if (value == null || Number.isNaN(value)) return "—";
  if (value < 60) return `${Math.round(value)}s`;
  return `${Math.round(value / 60)}m`;
}

function statusClass(status: string): string {
  if (status.includes("failed")) return "text-red-700";
  if (status === "screening" || status === "extracting" || status === "parsing") return "text-amber-700";
  if (status === "screened") return "text-green-700";
  return "text-xlent-muted";
}

export function PipelineOpsPage() {
  const [lookback, setLookback] = useState(24);
  const [staleMinutes, setStaleMinutes] = useState(10);
  const [limit, setLimit] = useState(100);

  const metrics = usePipelineMetrics(lookback, true);
  const recovery = usePipelineRecovery(staleMinutes, limit, true);
  const retryMutation = useRetryPipelineInvoice();

  const screeningLatency = useMemo(
    () => metrics.data?.latencies.find((row) => row.metric === "screening_seconds") ?? null,
    [metrics.data],
  );
  const e2eLatency = useMemo(
    () => metrics.data?.latencies.find((row) => row.metric === "end_to_end_seconds") ?? null,
    [metrics.data],
  );

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-xlent-ink">Pipeline drift</h1>
        <p className="mt-1 text-sm text-xlent-muted">
          SLA-metrikk, stuck-kø og recovery-actions for parsing/ekstraksjon/screening.
        </p>
      </header>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <label className="text-xs text-xlent-muted">Vindu (timer)</label>
          <select
            className={selectCls}
            value={lookback}
            onChange={(e) => setLookback(Number(e.target.value))}
          >
            <option value={6}>6</option>
            <option value={12}>12</option>
            <option value={24}>24</option>
            <option value={48}>48</option>
            <option value={72}>72</option>
          </select>
          <label className="ml-3 text-xs text-xlent-muted">Stale-grense (min)</label>
          <input
            type="number"
            min={1}
            max={180}
            className={clsx(selectCls, "w-20")}
            value={staleMinutes}
            onChange={(e) => setStaleMinutes(Math.max(1, Number(e.target.value || 10)))}
          />
          <label className="ml-3 text-xs text-xlent-muted">Recovery-limit</label>
          <input
            type="number"
            min={10}
            max={500}
            className={clsx(selectCls, "w-24")}
            value={limit}
            onChange={(e) => setLimit(Math.max(10, Number(e.target.value || 100)))}
          />
        </div>

        {metrics.isLoading && <p className="text-sm text-xlent-muted">Laster metrikk …</p>}
        {metrics.error && <p className="text-sm text-traffic-red">Kunne ikke hente pipeline-metrikk.</p>}

        {metrics.data && (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
              <div className="rounded border border-gray-200 bg-gray-50 p-3">
                <div className="text-xs text-xlent-muted">Invoices totalt</div>
                <div className="text-lg font-semibold text-xlent-ink">{metrics.data.total_invoices}</div>
              </div>
              <div className="rounded border border-gray-200 bg-gray-50 p-3">
                <div className="text-xs text-xlent-muted">Nye i vindu</div>
                <div className="text-lg font-semibold text-xlent-ink">{metrics.data.total_invoices_last_window}</div>
              </div>
              <div className="rounded border border-gray-200 bg-gray-50 p-3">
                <div className="text-xs text-xlent-muted">Screening p95</div>
                <div className="text-lg font-semibold text-xlent-ink">{fmtSeconds(screeningLatency?.p95_seconds ?? null)}</div>
              </div>
              <div className="rounded border border-gray-200 bg-gray-50 p-3">
                <div className="text-xs text-xlent-muted">End-to-end p95</div>
                <div className="text-lg font-semibold text-xlent-ink">{fmtSeconds(e2eLatency?.p95_seconds ?? null)}</div>
              </div>
            </div>

            <div className="mt-4 overflow-x-auto rounded border border-gray-200">
              <table className="w-full min-w-[680px] text-left text-xs">
                <thead className="bg-gray-50 text-xlent-muted">
                  <tr>
                    <th className="px-2 py-1.5">Steg</th>
                    <th className="px-2 py-1.5">In progress</th>
                    <th className="px-2 py-1.5">Stuck</th>
                    <th className="px-2 py-1.5">Failed</th>
                    <th className="px-2 py-1.5">Completed (vindu)</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.data.staged.map((row) => (
                    <tr key={row.stage} className="border-t border-gray-100 text-xlent-ink">
                      <td className="px-2 py-1.5 font-medium">{row.stage}</td>
                      <td className="px-2 py-1.5">{row.in_progress}</td>
                      <td className={clsx("px-2 py-1.5", row.stuck > 0 ? "text-red-700" : "text-xlent-ink")}>
                        {row.stuck}
                      </td>
                      <td className={clsx("px-2 py-1.5", row.failed > 0 ? "text-red-700" : "text-xlent-ink")}>
                        {row.failed}
                      </td>
                      <td className="px-2 py-1.5">{row.completed_last_window}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {metrics.data.alerts.length > 0 && (
              <div className="mt-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                <div className="font-medium">Varsler</div>
                <ul className="mt-1 space-y-1">
                  {metrics.data.alerts.map((alert) => (
                    <li key={alert}>• {alert}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </section>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-xlent-muted">
          Recovery-kø
        </h2>
        {recovery.isLoading && <p className="mt-2 text-sm text-xlent-muted">Laster recovery-kø …</p>}
        {recovery.error && <p className="mt-2 text-sm text-traffic-red">Kunne ikke hente recovery-kø.</p>}

        {recovery.data && (
          <>
            <p className="mt-2 text-xs text-xlent-muted">
              {recovery.data.total} kandidater (stale-grense {recovery.data.stale_minutes} min)
            </p>
            <div className="mt-3 overflow-x-auto rounded border border-gray-200">
              <table className="w-full min-w-[980px] text-left text-xs">
                <thead className="bg-gray-50 text-xlent-muted">
                  <tr>
                    <th className="px-2 py-1.5">Invoice</th>
                    <th className="px-2 py-1.5">Status</th>
                    <th className="px-2 py-1.5">Alder</th>
                    <th className="px-2 py-1.5">Reason</th>
                    <th className="px-2 py-1.5">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {recovery.data.items.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-2 py-4 text-center text-xlent-muted">
                        Ingen stale/failed invoices nå.
                      </td>
                    </tr>
                  )}
                  {recovery.data.items.map((row) => (
                    <tr key={row.invoice_id} className="border-t border-gray-100 text-xlent-ink">
                      <td className="px-2 py-1.5">
                        <Link to={`/invoices/${row.invoice_id}`} className="text-xlent-primary hover:underline">
                          {row.original_filename ?? row.invoice_number ?? row.invoice_id}
                        </Link>
                      </td>
                      <td className={clsx("px-2 py-1.5 font-medium", statusClass(row.status))}>{row.status}</td>
                      <td className="px-2 py-1.5">{row.minutes_in_status} min</td>
                      <td className="px-2 py-1.5 text-xlent-muted">{row.reason ?? "—"}</td>
                      <td className="px-2 py-1.5">
                        <div className="flex flex-wrap gap-1">
                          {(["parse", "extract", "screen"] as const).map((target) => (
                            <button
                              key={`${row.invoice_id}-${target}`}
                              onClick={() => retryMutation.mutate({ invoiceId: row.invoice_id, target })}
                              disabled={retryMutation.isPending}
                              className={clsx(
                                "rounded border px-2 py-0.5 text-[11px]",
                                retryMutation.isPending
                                  ? "cursor-not-allowed border-gray-200 text-gray-400"
                                  : "border-gray-300 text-xlent-muted hover:bg-gray-50 hover:text-xlent-ink",
                              )}
                            >
                              Re-{target}
                            </button>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
