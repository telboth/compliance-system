/**
 * RegulatoryRadar — sanntidsstrøm av regulatoriske varsler.
 *
 * Viser aktive og inaktive regulatoriske kilder, henter varsler fra de kildene
 * backend faktisk kan nå, og lar brukeren filtrere på kilde og alvorlighetsgrad.
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import clsx from "clsx";

import {
  getRegulatoryAlerts,
  getRegulatorySourcesList,
  refreshRegulatoryFeeds,
} from "@/api/regulatory";
import type { RegulatoryAlert, RegulatorySource } from "@/api/types";

// ── Badges ────────────────────────────────────────────────────────────────────

function SeverityBadge({ severity }: { severity: string }) {
  const isCritical = severity === "critical";
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        isCritical ? "bg-red-100 text-red-700" : "bg-blue-100 text-blue-700",
      )}
    >
      {isCritical ? "⚠ Kritisk" : "ℹ Info"}
    </span>
  );
}

function SourceBadge({ source }: { source: string }) {
  const colorMap: Record<string, string> = {
    OFAC: "bg-amber-100 text-amber-700",
    "EUR-Lex": "bg-blue-100 text-blue-700",
    "HM Treasury": "bg-purple-100 text-purple-700",
    "UN SC": "bg-gray-100 text-gray-600",
    DEKSA: "bg-emerald-100 text-emerald-700",
  };
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium",
        colorMap[source] ?? "bg-gray-100 text-gray-600",
      )}
    >
      {source}
    </span>
  );
}

function CategoryBadge({ category }: { category: string | null }) {
  if (!category) return null;
  return (
    <span className="inline-flex items-center rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-500">
      {category === "sanctions" ? "Sanksjoner" : "Eksportkontroll"}
    </span>
  );
}

function SourceStatusBadge({ status }: { status: string }) {
  const { t } = useTranslation("pages");
  const colorMap: Record<string, string> = {
    active: "bg-emerald-100 text-emerald-700",
    empty: "bg-amber-100 text-amber-700",
    disabled: "bg-gray-100 text-gray-600",
    error: "bg-red-100 text-red-700",
  };
  const labelMap: Record<string, string> = {
    active: t("regulatory_radar.source_status_active"),
    empty: t("regulatory_radar.source_status_empty"),
    disabled: t("regulatory_radar.source_status_disabled"),
    error: t("regulatory_radar.source_status_error"),
  };

  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        colorMap[status] ?? "bg-gray-100 text-gray-600",
      )}
    >
      {labelMap[status] ?? status}
    </span>
  );
}

function SourceStatusTable({ sources }: { sources: RegulatorySource[] }) {
  const { t, i18n } = useTranslation("pages");
  const locale = i18n.language === "en" ? "en-GB" : "nb-NO";

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-xlent-ink">
            {t("regulatory_radar.sources_title")}
          </h2>
          <p className="mt-1 text-xs text-xlent-muted">
            {t("regulatory_radar.sources_subtitle")}
          </p>
        </div>
        <div className="text-xs text-xlent-muted">
          {t("regulatory_radar.sources_count", { count: sources.length })}
        </div>
      </div>

      <div className="mt-3 overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-3 py-2">{t("regulatory_radar.col_source")}</th>
              <th className="px-3 py-2">{t("regulatory_radar.col_status")}</th>
              <th className="px-3 py-2">{t("regulatory_radar.col_alerts")}</th>
              <th className="px-3 py-2">{t("regulatory_radar.col_last_alert")}</th>
              <th className="px-3 py-2">{t("regulatory_radar.col_note")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {sources.map((source) => {
              const latestAlert = source.latest_alert_at
                ? new Date(source.latest_alert_at).toLocaleDateString(locale, {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })
                : "—";
              return (
                <tr key={source.name} className="align-top">
                  <td className="px-3 py-3">
                    <div className="font-medium text-xlent-ink">{source.name}</div>
                    <div className="mt-1 text-xs text-xlent-muted">{source.description}</div>
                  </td>
                  <td className="px-3 py-3">
                    <SourceStatusBadge status={source.status} />
                  </td>
                  <td className="px-3 py-3 text-xlent-ink">{source.alert_count}</td>
                  <td className="px-3 py-3 text-xlent-ink">{latestAlert}</td>
                  <td className="px-3 py-3">
                    <p className="text-xs leading-relaxed text-xlent-muted">
                      {source.status_note ?? "—"}
                    </p>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ── Varselkort ────────────────────────────────────────────────────────────────

function AlertCard({ alert }: { alert: RegulatoryAlert }) {
  const { i18n } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const locale = i18n.language === "en" ? "en-GB" : "nb-NO";

  const published = alert.published_at
    ? new Date(alert.published_at).toLocaleDateString(locale, {
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : null;

  return (
    <div
      className={clsx(
        "rounded-lg border bg-white p-4",
        alert.severity === "critical"
          ? "border-red-200"
          : "border-gray-200",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <SeverityBadge severity={alert.severity} />
        <SourceBadge source={alert.source} />
        <CategoryBadge category={alert.category} />
        {published && (
          <span className="ml-auto text-xs text-xlent-muted">{published}</span>
        )}
      </div>

      <div className="mt-2">
        {alert.link ? (
          <a
            href={alert.link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-xlent-primary hover:underline"
          >
            {alert.title}
          </a>
        ) : (
          <p className="text-sm font-medium text-xlent-ink">{alert.title}</p>
        )}
      </div>

      {alert.summary && (
        <div className="mt-2">
          {expanded ? (
            <>
              <p className="text-xs leading-relaxed text-xlent-muted">{alert.summary}</p>
              <button
                onClick={() => setExpanded(false)}
                className="mt-1 text-xs text-xlent-primary hover:underline"
              >
                ▲ Vis mindre
              </button>
            </>
          ) : (
            <button
              onClick={() => setExpanded(true)}
              className="text-xs text-xlent-primary hover:underline"
            >
              ▼ Vis sammendrag
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Filterknapp ───────────────────────────────────────────────────────────────

function FilterChip({
  active,
  onClick,
  children,
  danger,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
        active && danger
          ? "border-red-500 bg-red-500 text-white"
          : active
            ? "border-xlent-primary bg-xlent-primary text-white"
            : "border-gray-300 bg-white text-xlent-muted hover:bg-gray-50",
      )}
    >
      {children}
    </button>
  );
}

// ── Hovedelement ──────────────────────────────────────────────────────────────

const FALLBACK_SOURCES = ["OFAC", "EUR-Lex", "HM Treasury", "UN SC", "DEKSA"];

export function RegulatoryRadarPage() {
  const { t } = useTranslation("pages");
  const queryClient = useQueryClient();

  const [sourceFilter, setSourceFilter] = useState<string | undefined>(undefined);
  const [severityFilter, setSeverityFilter] = useState<string | undefined>(undefined);

  const { data, isLoading, error } = useQuery({
    queryKey: ["regulatory-radar", sourceFilter, severityFilter],
    queryFn: () =>
      getRegulatoryAlerts({
        source: sourceFilter,
        severity: severityFilter,
        limit: 100,
      }),
    staleTime: 60_000,
  });

  const {
    data: sources,
    isLoading: sourcesLoading,
    error: sourcesError,
  } = useQuery({
    queryKey: ["regulatory-radar-sources"],
    queryFn: getRegulatorySourcesList,
    staleTime: 60_000,
  });

  const refreshMutation = useMutation({
    mutationFn: refreshRegulatoryFeeds,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["regulatory-radar"] });
      queryClient.invalidateQueries({ queryKey: ["regulatory-radar-sources"] });
    },
  });

  const items = data?.items ?? [];
  const critical = items.filter((a) => a.severity === "critical");
  const info = items.filter((a) => a.severity !== "critical");
  const sourceNames = sources?.map((source) => source.name) ?? FALLBACK_SOURCES;

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-xlent-ink">
            {t("regulatory_radar.title")}
          </h1>
          <p className="mt-1 text-sm text-xlent-muted">
            {t("regulatory_radar.subtitle")}
          </p>
        </div>
        <button
          type="button"
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-xlent-muted hover:bg-gray-50 disabled:opacity-50"
        >
          {refreshMutation.isPending
            ? t("regulatory_radar.refreshing")
            : t("regulatory_radar.refresh")}
        </button>
      </div>

      {/* Oppdateringsresultat */}
      {refreshMutation.data && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-2 text-sm text-green-700">
          {t("regulatory_radar.refresh_done", {
            count: refreshMutation.data.total_new,
          })}
        </div>
      )}

      {/* Kilder */}
      {sourcesLoading && (
        <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-xlent-muted">
          {t("regulatory_radar.sources_loading")}
        </div>
      )}
      {sourcesError && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {t("regulatory_radar.sources_error")}
        </div>
      )}
      {sources && <SourceStatusTable sources={sources} />}

      {/* Kildefiltre */}
      <div className="flex flex-wrap gap-2">
        <FilterChip
          active={!sourceFilter}
          onClick={() => setSourceFilter(undefined)}
        >
          {t("regulatory_radar.filter_all_sources")}
        </FilterChip>
        {sourceNames.map((s) => (
          <FilterChip
            key={s}
            active={sourceFilter === s}
            onClick={() => setSourceFilter(sourceFilter === s ? undefined : s)}
          >
            {s}
          </FilterChip>
        ))}

        <span className="mx-1 self-center text-gray-300">|</span>

        <FilterChip
          active={!severityFilter}
          onClick={() => setSeverityFilter(undefined)}
        >
          {t("regulatory_radar.filter_all_severity")}
        </FilterChip>
        <FilterChip
          active={severityFilter === "critical"}
          danger
          onClick={() =>
            setSeverityFilter(severityFilter === "critical" ? undefined : "critical")
          }
        >
          ⚠ {t("regulatory_radar.filter_critical")}
        </FilterChip>
      </div>

      {/* Tell-sammendrag */}
      {data && (
        <div className="flex flex-wrap gap-4">
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-center">
            <div className="text-xl font-bold text-red-700">{critical.length}</div>
            <div className="text-xs text-red-800">{t("regulatory_radar.count_critical")}</div>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-center">
            <div className="text-xl font-bold text-xlent-ink">{info.length}</div>
            <div className="text-xs text-xlent-muted">{t("regulatory_radar.count_info")}</div>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-center">
            <div className="text-xl font-bold text-xlent-ink">{data.total}</div>
            <div className="text-xs text-xlent-muted">{t("regulatory_radar.count_total")}</div>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-xlent-primary border-t-transparent" />
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-100 bg-red-50 p-4 text-sm text-red-700">
          {t("regulatory_radar.loading_error")}
        </div>
      )}

      {!isLoading && !error && items.length === 0 && (
        <div className="rounded-lg border border-gray-200 bg-white py-12 text-center">
          <p className="text-sm font-medium text-xlent-ink">
            {t("regulatory_radar.empty_title")}
          </p>
          <p className="mt-1 text-xs text-xlent-muted">
            {t("regulatory_radar.empty_body")}
          </p>
        </div>
      )}

      {/* Kritiske varsler øverst */}
      {critical.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-red-700">
            {t("regulatory_radar.section_critical")}
          </p>
          {critical.map((alert) => (
            <AlertCard key={alert.id} alert={alert} />
          ))}
        </div>
      )}

      {/* Info-varsler */}
      {info.length > 0 && (
        <div className="space-y-3">
          {critical.length > 0 && (
            <p className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
              {t("regulatory_radar.section_info")}
            </p>
          )}
          {info.map((alert) => (
            <AlertCard key={alert.id} alert={alert} />
          ))}
        </div>
      )}
    </div>
  );
}
