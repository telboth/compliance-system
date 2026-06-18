/**
 * KRI — Key Risk Indicators
 *
 * Gir compliance-offiseren og controlleren et aggregert bilde av risiko:
 * screening hit-rate, false-positive-rate, snittid til beslutning, total
 * risikoeksponering i NOK, topp-land, topp-entiteter og månedlig trendkurve.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import clsx from "clsx";

import { getKRIReport, getKRICSVUrl } from "@/api/kri";
import type { KRITopCountry, KRITopEntity, KRIMonthlyPoint } from "@/api/types";

// ── Hjelp: formattering ───────────────────────────────────────────────────────

function fmtNok(value: number): string {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)} mrd NOK`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)} mill NOK`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k NOK`;
  return `${Math.round(value).toLocaleString("nb-NO")} NOK`;
}

function fmtPct(rate: number): string {
  return `${(rate * 100).toFixed(1)} %`;
}

// ── KPI-kort ──────────────────────────────────────────────────────────────────

function KpiCard({
  label,
  value,
  sub,
  color = "default",
  large = false,
}: {
  label: string;
  value: string | number;
  sub?: string;
  color?: "default" | "red" | "yellow" | "green" | "blue";
  large?: boolean;
}) {
  const colorMap = {
    default: "text-xlent-ink",
    red: "text-red-600",
    yellow: "text-yellow-600",
    green: "text-green-600",
    blue: "text-xlent-primary",
  };
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <p className="text-xs font-medium text-xlent-muted">{label}</p>
      <p
        className={clsx(
          "mt-1 font-semibold tabular-nums",
          large ? "text-3xl" : "text-2xl",
          colorMap[color],
        )}
      >
        {value}
      </p>
      {sub && <p className="mt-0.5 text-xs text-xlent-muted">{sub}</p>}
    </div>
  );
}

// ── Horisontal stacked bar-liste ──────────────────────────────────────────────

function BarList({
  items,
  max,
}: {
  items: { label: string; value: number; confirmed?: number }[];
  max: number;
}) {
  const { t } = useTranslation("pages");
  if (items.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-xlent-muted">{t("kri.no_data")}</p>
    );
  }
  return (
    <div className="space-y-2">
      {items.map((item, i) => {
        const confirmed = item.confirmed ?? 0;
        const potential = item.value - confirmed;
        return (
          <div key={i} className="flex items-center gap-2">
            <span className="w-4 shrink-0 text-right text-xs text-xlent-muted">
              {i + 1}.
            </span>
            <span
              className="w-32 shrink-0 truncate text-sm text-xlent-ink"
              title={item.label}
            >
              {item.label}
            </span>
            <div className="flex flex-1 items-center gap-1">
              <div className="flex h-2 flex-1 overflow-hidden rounded bg-gray-100">
                <div
                  className="h-full bg-red-500"
                  style={{ width: `${(confirmed / max) * 100}%` }}
                />
                <div
                  className="h-full bg-amber-400"
                  style={{ width: `${(potential / max) * 100}%` }}
                />
              </div>
              <span className="w-8 text-right text-xs font-medium tabular-nums text-xlent-ink">
                {item.value}
              </span>
              {confirmed > 0 && (
                <span className="w-14 text-right text-[11px] text-red-600">
                  ({confirmed} ✓)
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Månedlig trend ────────────────────────────────────────────────────────────

function MonthlyTrend({ data }: { data: KRIMonthlyPoint[] }) {
  const { t } = useTranslation("pages");
  if (data.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-xlent-muted">{t("kri.no_data")}</p>
    );
  }
  const maxVal = Math.max(...data.map((d) => d.hit_count), 1);

  return (
    <div className="flex items-end gap-1" style={{ height: "120px" }}>
      {data.map((point, i) => {
        const heightPct = (point.hit_count / maxVal) * 100;
        const confirmedPct =
          point.hit_count > 0
            ? (point.confirmed_count / point.hit_count) * 100
            : 0;
        const label = point.month
          ? new Date(point.month + "-01").toLocaleDateString("nb-NO", {
              month: "short",
            })
          : `${i + 1}`;
        return (
          <div key={i} className="flex flex-1 flex-col items-center gap-0.5">
            <div
              className="relative w-full overflow-hidden rounded-t"
              style={{ height: `${heightPct}%`, minHeight: point.hit_count > 0 ? "4px" : "0" }}
              title={`${point.month}: ${point.hit_count} (${point.confirmed_count} confirmed)`}
            >
              <div
                className="absolute bottom-0 left-0 right-0 flex flex-col-reverse"
                style={{ height: "100%" }}
              >
                <div
                  className="bg-amber-400"
                  style={{ height: `${100 - confirmedPct}%` }}
                />
                <div
                  className="bg-red-500"
                  style={{ height: `${confirmedPct}%` }}
                />
              </div>
            </div>
            <span className="text-[9px] text-xlent-muted">{label}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Periode-velger ────────────────────────────────────────────────────────────

function PeriodButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "rounded-full border px-3 py-1 text-xs font-medium",
        active
          ? "border-xlent-primary bg-xlent-primary text-white"
          : "border-gray-300 bg-white text-xlent-muted hover:bg-gray-50",
      )}
    >
      {children}
    </button>
  );
}

// ── Hovedelement ──────────────────────────────────────────────────────────────

export function KRIPage() {
  const { t, i18n } = useTranslation("pages");
  const [months, setMonths] = useState(12);

  const { data, isLoading, error, dataUpdatedAt } = useQuery({
    queryKey: ["kri", months],
    queryFn: () => getKRIReport(months),
    staleTime: 120_000,
    refetchInterval: 300_000,
  });

  const hitRate = data?.screening_hit_rate;
  const fpRate = data?.false_positive_rate;
  const avgDays = data?.avg_days_to_resolution;
  const exposure = data?.risk_exposure_summary;
  const countries = (data?.top_flagged_countries ?? []) as KRITopCountry[];
  const entities = (data?.top_flagged_entities ?? []) as KRITopEntity[];
  const trend = (data?.monthly_hit_trend ?? []) as KRIMonthlyPoint[];

  const maxCountry = Math.max(...countries.map((c) => c.hit_count), 1);
  const maxEntity = Math.max(...entities.map((e) => e.hit_count), 1);

  const updatedAtStr = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString(
        i18n.language === "en" ? "en-GB" : "nb-NO",
        { hour: "2-digit", minute: "2-digit" },
      )
    : null;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-xlent-ink">{t("kri.title")}</h1>
          <p className="mt-1 text-sm text-xlent-muted">{t("kri.subtitle")}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PeriodButton active={months === 3} onClick={() => setMonths(3)}>
            {t("kri.months", { count: 3 })}
          </PeriodButton>
          <PeriodButton active={months === 6} onClick={() => setMonths(6)}>
            {t("kri.months", { count: 6 })}
          </PeriodButton>
          <PeriodButton active={months === 12} onClick={() => setMonths(12)}>
            {t("kri.months", { count: 12 })}
          </PeriodButton>
          <a
            href={getKRICSVUrl(months)}
            className="rounded border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-xlent-muted hover:bg-gray-50"
            download
          >
            ⬇ CSV
          </a>
        </div>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-xlent-primary border-t-transparent" />
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-100 bg-red-50 p-4 text-sm text-red-700">
          {t("kri.loading_error")}
        </div>
      )}

      {data && (
        <>
          {/* 4 KPI-kort */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <KpiCard
              label={t("kri.hit_rate")}
              value={hitRate ? fmtPct(hitRate.rate) : "—"}
              sub={
                hitRate
                  ? t("kri.hit_rate_sub", {
                      total: hitRate.total_screened,
                      hits: hitRate.with_hits,
                    })
                  : undefined
              }
              color={
                hitRate && hitRate.rate > 0.2
                  ? "red"
                  : hitRate && hitRate.rate > 0.1
                    ? "yellow"
                    : "green"
              }
            />
            <KpiCard
              label={t("kri.false_positive_rate")}
              value={fpRate ? fmtPct(fpRate.rate) : "—"}
              sub={
                fpRate
                  ? t("kri.fp_rate_sub", { reviewed: fpRate.potential_reviewed })
                  : undefined
              }
              color="blue"
            />
            <KpiCard
              label={t("kri.avg_days")}
              value={
                avgDays?.avg_days_to_resolution != null
                  ? `${avgDays.avg_days_to_resolution}d`
                  : "—"
              }
              sub={t("kri.avg_days_sub")}
              color={
                avgDays?.avg_days_to_resolution != null &&
                avgDays.avg_days_to_resolution > 5
                  ? "yellow"
                  : "default"
              }
            />
            <KpiCard
              label={t("kri.risk_exposure")}
              value={exposure ? fmtNok(exposure.total_exposure_nok) : "—"}
              sub={
                exposure
                  ? t("kri.risk_exposure_sub", { count: exposure.invoice_count })
                  : undefined
              }
              color={
                exposure && exposure.total_exposure_nok > 5_000_000 ? "red" : "default"
              }
              large
            />
          </div>

          {/* Topp land + månedlig trend */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <p className="mb-3 text-sm font-semibold text-xlent-ink">
                {t("kri.top_countries", { count: countries.length })}
              </p>
              <BarList
                items={countries.map((c) => ({
                  label: c.country,
                  value: c.hit_count,
                }))}
                max={maxCountry}
              />
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <p className="mb-3 text-sm font-semibold text-xlent-ink">
                {t("kri.monthly_trend")}
              </p>
              <MonthlyTrend data={trend} />
              <div className="mt-2 flex gap-4 text-xs text-xlent-muted">
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-sm bg-red-500" />
                  {t("kri.confirmed")}
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-sm bg-amber-400" />
                  {t("kri.potential")}
                </span>
              </div>
            </div>
          </div>

          {/* Topp flaggede entiteter */}
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <p className="mb-3 text-sm font-semibold text-xlent-ink">
              {t("kri.top_entities", { count: entities.length })}
            </p>
            <BarList
              items={entities.map((e) => ({
                label: e.entity_name,
                value: e.hit_count,
                confirmed: e.confirmed_count,
              }))}
              max={maxEntity}
            />
            {entities.length > 0 && (
              <div className="mt-2 flex gap-4 text-xs text-xlent-muted">
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-sm bg-red-500" />
                  {t("kri.confirmed")}
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-sm bg-amber-400" />
                  {t("kri.potential")}
                </span>
              </div>
            )}
          </div>

          {updatedAtStr && (
            <p className="text-right text-xs text-xlent-muted">
              {t("kri.updated_at", { time: updatedAtStr })}
            </p>
          )}
        </>
      )}
    </div>
  );
}
