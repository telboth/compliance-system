/**
 * Dashboard — KPI-oversikt for compliance-offiserer.
 *
 * Viser nøkkeltall, score-fordeling, ukentlig trend og sanksjonsstatus.
 * Bruker CSS-baserte visualiseringer (ingen ekstra chart-pakke nødvendig).
 * For produksjon: vurder recharts eller visx for rikere grafer.
 */

import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { getDashboard } from "@/api/dashboard";
import type { WeeklyTrendPoint } from "@/api/dashboard";

// ── KPI-kort ──────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  color?: "default" | "red" | "green" | "yellow" | "blue";
}

function StatCard({ label, value, sub, color = "default" }: StatCardProps) {
  const colorMap = {
    default: "text-xlent-ink",
    red: "text-traffic-red",
    green: "text-traffic-green",
    yellow: "text-yellow-600",
    blue: "text-xlent-primary",
  };
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <p className="text-xs font-medium text-xlent-muted">{label}</p>
      <p className={clsx("mt-1 text-2xl font-semibold tabular-nums", colorMap[color])}>
        {value}
      </p>
      {sub && <p className="mt-0.5 text-xs text-xlent-muted">{sub}</p>}
    </div>
  );
}

// ── Score-fordeling (pie-donut via SVG) ───────────────────────────────────────

interface ScoreDistProps {
  green: number;
  yellow: number;
  red: number;
  unknown: number;
}

function ScoreDistribution({ green, yellow, red, unknown }: ScoreDistProps) {
  const total = green + yellow + red + unknown || 1;
  const pct = (n: number) => Math.round((n / total) * 100);

  const bars = [
    { label: "Grønn", count: green, pct: pct(green), color: "bg-green-500" },
    { label: "Gul", count: yellow, pct: pct(yellow), color: "bg-yellow-400" },
    { label: "Rød", count: red, pct: pct(red), color: "bg-red-500" },
    { label: "Ukjent", count: unknown, pct: pct(unknown), color: "bg-gray-300" },
  ];

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <p className="mb-3 text-sm font-semibold text-xlent-ink">Score-fordeling</p>
      <div className="flex h-4 w-full overflow-hidden rounded-full">
        {bars.map((b) => (
          <div
            key={b.label}
            className={b.color}
            style={{ width: `${b.pct}%` }}
            title={`${b.label}: ${b.count}`}
          />
        ))}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1">
        {bars.map((b) => (
          <div key={b.label} className="flex items-center gap-1.5 text-xs">
            <span className={clsx("h-2.5 w-2.5 rounded-full", b.color)} />
            <span className="text-xlent-muted">{b.label}</span>
            <span className="ml-auto font-medium tabular-nums text-xlent-ink">{b.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Ukentlig trend (stacked bar) ──────────────────────────────────────────────

function WeeklyTrend({ data }: { data: WeeklyTrendPoint[] }) {
  if (data.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <p className="text-sm font-semibold text-xlent-ink">Ukentlig trend</p>
        <p className="mt-4 text-center text-sm text-xlent-muted">Ingen data ennå</p>
      </div>
    );
  }

  const maxTotal = Math.max(...data.map((d) => d.total), 1);

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <p className="mb-3 text-sm font-semibold text-xlent-ink">Ukentlig trend (invoices)</p>
      <div className="flex items-end gap-2" style={{ height: "120px" }}>
        {data.map((week, i) => {
          const heightPct = (week.total / maxTotal) * 100;
          const redPct = week.total > 0 ? (week.red_flags / week.total) * 100 : 0;
          const yellowPct = week.total > 0 ? (week.yellow_flags / week.total) * 100 : 0;
          const greenPct = 100 - redPct - yellowPct;
          const label = week.week_start
            ? new Date(week.week_start).toLocaleDateString("nb-NO", { day: "numeric", month: "short" })
            : `Uke ${i + 1}`;
          return (
            <div key={i} className="group flex flex-1 flex-col items-center gap-1">
              <div
                className="relative w-full overflow-hidden rounded-t"
                style={{ height: `${heightPct}%` }}
                title={`${week.total} fakturaer (${week.red_flags} røde, ${week.yellow_flags} gule)`}
              >
                {/* Stacked segments: rød øverst */}
                <div className="absolute bottom-0 left-0 right-0 flex flex-col-reverse" style={{ height: "100%" }}>
                  <div className="bg-green-400" style={{ height: `${greenPct}%` }} />
                  <div className="bg-yellow-400" style={{ height: `${yellowPct}%` }} />
                  <div className="bg-red-500" style={{ height: `${redPct}%` }} />
                </div>
              </div>
              <span className="text-center text-xs text-xlent-muted" style={{ fontSize: "0.6rem" }}>
                {label}
              </span>
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex gap-4 text-xs text-xlent-muted">
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-green-400" /> Grønn</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-yellow-400" /> Gul</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-red-500" /> Rød</span>
      </div>
    </div>
  );
}

// ── Topp-kunder med flagg ─────────────────────────────────────────────────────

function TopCustomers({ customers }: { customers: { customer_name: string; flag_count: number }[] }) {
  const max = Math.max(...customers.map((c) => c.flag_count), 1);
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <p className="mb-3 text-sm font-semibold text-xlent-ink">
        Topp 5 kunder med flagg (siste 30 dager)
      </p>
      {customers.length === 0 ? (
        <p className="text-center text-sm text-xlent-muted">Ingen flaggede kunder</p>
      ) : (
        <div className="space-y-2">
          {customers.map((c, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="w-4 text-right text-xs font-bold text-xlent-muted">{i + 1}.</span>
              <span className="min-w-0 flex-1 truncate text-sm text-xlent-ink">{c.customer_name}</span>
              <div className="flex w-32 items-center gap-1">
                <div className="flex-1 overflow-hidden rounded bg-gray-100" style={{ height: "8px" }}>
                  <div
                    className="h-full rounded bg-orange-400"
                    style={{ width: `${(c.flag_count / max) * 100}%` }}
                  />
                </div>
                <span className="w-6 text-right text-xs font-medium text-xlent-ink tabular-nums">
                  {c.flag_count}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Audit-aktivitet ───────────────────────────────────────────────────────────

function AuditActivity({ actions }: { actions: { action: string; count: number }[] }) {
  const max = Math.max(...actions.map((a) => a.count), 1);
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <p className="mb-3 text-sm font-semibold text-xlent-ink">
        Audit-aktivitet (siste 7 dager)
      </p>
      {actions.length === 0 ? (
        <p className="text-center text-sm text-xlent-muted">Ingen aktivitet</p>
      ) : (
        <div className="space-y-2">
          {actions.map((a, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate font-mono text-xs text-xlent-muted">
                {a.action}
              </span>
              <div className="flex w-24 items-center gap-1">
                <div className="flex-1 overflow-hidden rounded bg-gray-100" style={{ height: "6px" }}>
                  <div
                    className="h-full rounded bg-blue-400"
                    style={{ width: `${(a.count / max) * 100}%` }}
                  />
                </div>
                <span className="w-6 text-right text-xs tabular-nums text-xlent-ink">
                  {a.count}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Hovedelement ──────────────────────────────────────────────────────────────

export function DashboardPage() {
  const { data, isLoading, error, dataUpdatedAt } = useQuery({
    queryKey: ["dashboard"],
    queryFn: getDashboard,
    staleTime: 60_000,
    refetchInterval: 120_000, // Auto-oppdater hvert 2. minutt
  });

  const updatedAt = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString("nb-NO", { hour: "2-digit", minute: "2-digit" })
    : null;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-xlent-ink">Compliance-dashboard</h1>
          <p className="mt-1 text-sm text-xlent-muted">
            Nøkkeltall og trender for compliance-offiseren. Oppdateres automatisk hvert 2. minutt.
          </p>
        </div>
        {updatedAt && (
          <p className="shrink-0 text-xs text-xlent-muted">Sist oppdatert {updatedAt}</p>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-xlent-primary border-t-transparent" />
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-100 bg-red-50 p-4 text-sm text-traffic-red">
          Kunne ikke laste dashboard. Sjekk at backend kjører.
        </div>
      )}

      {data && (
        <>
          {/* KPI-kort */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard
              label="Totalt behandlet"
              value={data.totals.invoices_total.toLocaleString("nb-NO")}
              sub="fakturaer"
              color="blue"
            />
            <StatCard
              label="Siste 7 dager"
              value={data.totals.invoices_this_week}
              sub="nye fakturaer"
            />
            <StatCard
              label="Siste 30 dager"
              value={data.totals.invoices_this_month}
              sub="nye fakturaer"
            />
            <StatCard
              label="Åpne flagg"
              value={data.totals.open_flags}
              sub="krever gjennomgang"
              color={data.totals.open_flags > 0 ? "red" : "green"}
            />
            <StatCard
              label="Snitt behandlingstid"
              value={
                data.totals.avg_processing_seconds < 60
                  ? `${Math.round(data.totals.avg_processing_seconds)}s`
                  : `${Math.round(data.totals.avg_processing_seconds / 60)}min`
              }
              sub="upload → screenet"
            />
          </div>

          {/* Sanksjonsstatistikk */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard
              label="Sanksjonssjekker (30 dager)"
              value={data.sanctions.total_screenings_this_month.toLocaleString("nb-NO")}
              color="blue"
            />
            <StatCard
              label="Bekreftede treff"
              value={data.sanctions.confirmed_matches}
              color={data.sanctions.confirmed_matches > 0 ? "red" : "green"}
            />
            <StatCard
              label="Potensielle treff"
              value={data.sanctions.potential_matches}
              color={data.sanctions.potential_matches > 0 ? "yellow" : "green"}
            />
          </div>

          {/* Grafer */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ScoreDistribution
              green={data.score_distribution.green ?? 0}
              yellow={data.score_distribution.yellow ?? 0}
              red={data.score_distribution.red ?? 0}
              unknown={data.score_distribution.unknown ?? 0}
            />
            <WeeklyTrend data={data.weekly_trend} />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <TopCustomers customers={data.top_customers_with_flags} />
            <AuditActivity actions={data.recent_audit_actions} />
          </div>

          {/* Status-fordeling */}
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <p className="mb-3 text-sm font-semibold text-xlent-ink">Pipeline-status</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(data.status_distribution)
                .sort(([, a], [, b]) => b - a)
                .map(([status, count]) => (
                  <span
                    key={status}
                    className="rounded-full border border-gray-200 px-3 py-1 text-xs"
                  >
                    <span className="font-mono">{status}</span>
                    <span className="ml-1.5 font-semibold text-xlent-ink">{count}</span>
                  </span>
                ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
