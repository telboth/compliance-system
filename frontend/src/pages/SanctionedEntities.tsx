import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { useTranslation } from "react-i18next";

import { Pagination } from "@/components/Pagination";
import {
  useRefreshExternalSources,
  useRefreshSanctions,
  useSanctionedEntities,
  useSanctionsStatus,
} from "@/hooks/useInvoices";
import type { SanctionedEntityType } from "@/api/types";

const selectCls =
  "rounded border border-gray-200 bg-white px-2 py-1 text-xs text-xlent-ink focus:outline-none focus:ring-1 focus:ring-xlent-primary";

function refreshStatusText(status: string | undefined, t: (key: string) => string): string {
  switch (status) {
    case "success":
      return t("sanctioned_entities.status.success");
    case "failed":
      return t("sanctioned_entities.status.failed");
    case "running":
      return t("sanctioned_entities.status.running");
    case "skipped":
      return t("sanctioned_entities.status.skipped");
    default:
      return t("sanctioned_entities.status.unknown");
  }
}

function refreshStatusClass(status: string | undefined): string {
  switch (status) {
    case "success":
      return "text-green-700";
    case "failed":
      return "text-red-700";
    case "running":
      return "text-amber-700";
    case "skipped":
      return "text-xlent-muted";
    default:
      return "text-xlent-muted";
  }
}

export function SanctionedEntitiesPage() {
  const { t, i18n } = useTranslation("pages");
  const locale = i18n.language === "en" ? "en-GB" : "nb-NO";
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [entityType, setEntityType] = useState<SanctionedEntityType>("all");
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [refreshInfo, setRefreshInfo] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [externalRefreshInfo, setExternalRefreshInfo] = useState<string | null>(null);
  const [externalRefreshError, setExternalRefreshError] = useState<string | null>(null);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setOffset(0);
      setSearch(searchInput.trim());
    }, 350);
    return () => window.clearTimeout(handle);
  }, [searchInput]);

  const { data, isLoading, isFetching, error } = useSanctionedEntities({
    q: search,
    entity_type: entityType,
    limit,
    offset,
    fuzzy: true,
    simple: true,
  });
  const {
    data: sanctionsStatus,
    isLoading: sanctionsStatusLoading,
    error: sanctionsStatusError,
  } = useSanctionsStatus(true);
  const refreshMutation = useRefreshSanctions();
  const externalRefreshMutation = useRefreshExternalSources();

  const total = data?.total ?? 0;
  const relation = data?.total_relation ?? "eq";
  const resultText = useMemo(() => {
    if (!data) return "0";
    return relation === "gte" ? `${t("sanctioned_entities.at_least")} ${total.toLocaleString(locale)}` : total.toLocaleString(locale);
  }, [data, relation, total, t, locale]);
  const latestUpdatedAt = useMemo(() => {
    const timestamps = (sanctionsStatus?.datasets ?? [])
      .map((dataset) => dataset.last_updated)
      .filter((value): value is string => Boolean(value))
      .map((value) => new Date(value))
      .filter((dt) => !Number.isNaN(dt.getTime()));
    if (timestamps.length === 0) return null;
    timestamps.sort((a, b) => b.getTime() - a.getTime());
    return timestamps[0];
  }, [sanctionsStatus]);
  const latestRun = sanctionsStatus?.last_refresh_run ?? null;
  const externalIssues = (sanctionsStatus?.external_sources ?? []).filter(
    (row) => row.status !== "ok" || row.stale || row.error_message,
  );

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-xlent-ink">{t("sanctioned_entities.title")}</h1>
        <p className="mt-1 text-sm text-xlent-muted">
          {t("sanctioned_entities.subtitle")}
        </p>
      </header>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded border border-gray-100 bg-gray-50 px-3 py-2 text-xs">
          <div className="space-y-1 text-xlent-muted">
            <div>
              {t("sanctioned_entities.yente")}:{" "}
              <span className={sanctionsStatus?.yente_available ? "text-green-700" : "text-red-700"}>
                {sanctionsStatusLoading
                  ? t("sanctioned_entities.checking")
                  : sanctionsStatus?.yente_available
                    ? t("sanctioned_entities.up")
                    : t("sanctioned_entities.down")}
              </span>
              {" · "}
              {t("sanctioned_entities.elasticsearch")}:{" "}
              <span
                className={
                  sanctionsStatus?.elasticsearch_available ? "text-green-700" : "text-red-700"
                }
              >
                {sanctionsStatusLoading
                  ? t("sanctioned_entities.checking")
                  : sanctionsStatus?.elasticsearch_available
                    ? t("sanctioned_entities.up")
                    : t("sanctioned_entities.down")}
              </span>
            </div>
            <div>
              {t("sanctioned_entities.last_list_update")}:{" "}
              <span className="font-medium text-xlent-ink">
                {latestUpdatedAt
                  ? latestUpdatedAt.toLocaleString(locale)
                  : sanctionsStatusLoading
                    ? t("sanctioned_entities.loading")
                    : t("sanctioned_entities.unknown")}
              </span>
            </div>
            <div>
              {t("sanctioned_entities.scheduled_refresh")}:{" "}
              <span className="font-medium text-xlent-ink">
                {sanctionsStatus?.refresh_schedule_time ?? "07:40"}{" "}
                {sanctionsStatus?.refresh_schedule_timezone ?? "Europe/Oslo"}
              </span>
            </div>
            <div>
              {t("sanctioned_entities.scheduled_external_ingest")}:{" "}
              <span className="font-medium text-xlent-ink">
                {sanctionsStatus?.external_refresh_schedule_time ?? "07:45"}{" "}
                {sanctionsStatus?.refresh_schedule_timezone ?? "Europe/Oslo"}
              </span>
            </div>
            <div>
              {t("sanctioned_entities.last_refresh_job")}:{" "}
              {!latestRun ? (
                <span className="font-medium text-xlent-muted">{t("sanctioned_entities.no_runs")}</span>
              ) : (
                <>
                  <span className={clsx("font-medium", refreshStatusClass(latestRun.status))}>
                    {refreshStatusText(latestRun.status, t)}
                  </span>
                  <span className="text-xlent-muted">
                    {" · "}
                    {latestRun.trigger === "scheduled" ? t("sanctioned_entities.daily_cron") : t("sanctioned_entities.manual")}
                    {" · "}
                    {new Date(latestRun.started_at).toLocaleString(locale)}
                  </span>
                  {latestRun.message && (
                    <span className="text-xlent-muted">
                      {" · "}
                      {latestRun.message}
                    </span>
                  )}
                </>
              )}
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <button
              onClick={() => {
                setRefreshInfo(null);
                setRefreshError(null);
                refreshMutation.mutate(undefined, {
                  onSuccess: (response) => {
                    setRefreshInfo(
                      t("sanctioned_entities.refresh_triggered", { count: response.datasets_triggered.length }),
                    );
                  },
                  onError: () => {
                    setRefreshError(t("sanctioned_entities.refresh_error"));
                  },
                });
              }}
              disabled={refreshMutation.isPending}
              className={clsx(
                "rounded border px-3 py-1.5 text-xs font-medium transition-colors",
                refreshMutation.isPending
                  ? "cursor-not-allowed border-gray-200 text-xlent-muted"
                  : "border-xlent-primary/40 text-xlent-primary hover:bg-xlent-primary/5",
              )}
            >
              {refreshMutation.isPending ? t("sanctioned_entities.refreshing_lists") : t("sanctioned_entities.refresh_lists")}
            </button>
            <button
              onClick={() => {
                setExternalRefreshInfo(null);
                setExternalRefreshError(null);
                externalRefreshMutation.mutate(undefined, {
                  onSuccess: (response) => {
                    setExternalRefreshInfo(
                      t("sanctioned_entities.external_triggered", { count: response.datasets_triggered.length }),
                    );
                  },
                  onError: () => {
                    setExternalRefreshError(t("sanctioned_entities.external_error"));
                  },
                });
              }}
              disabled={externalRefreshMutation.isPending}
              className={clsx(
                "rounded border px-3 py-1.5 text-xs font-medium transition-colors",
                externalRefreshMutation.isPending
                  ? "cursor-not-allowed border-gray-200 text-xlent-muted"
                  : "border-indigo-300 bg-indigo-50 text-indigo-700 hover:bg-indigo-100",
              )}
            >
              {externalRefreshMutation.isPending ? t("sanctioned_entities.refreshing_external") : t("sanctioned_entities.refresh_external")}
            </button>
          </div>
        </div>
        {refreshInfo && <p className="mb-2 text-xs text-green-700">{refreshInfo}</p>}
        {refreshError && <p className="mb-2 text-xs text-traffic-red">{refreshError}</p>}
        {externalRefreshInfo && <p className="mb-2 text-xs text-green-700">{externalRefreshInfo}</p>}
        {externalRefreshError && <p className="mb-2 text-xs text-traffic-red">{externalRefreshError}</p>}
        {sanctionsStatusError && (
          <p className="mb-2 text-xs text-traffic-red">
            {t("sanctioned_entities.status_fetch_error")}
          </p>
        )}
        {externalIssues.length > 0 && (
          <div className="mb-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
            <div className="font-medium">{t("sanctioned_entities.external_warnings")}</div>
            <ul className="mt-1 space-y-1">
              {externalIssues.map((row) => (
                <li key={row.source}>
                  {row.source}: {row.status}
                  {row.stale ? ` (${t("sanctioned_entities.stale")})` : ""}
                  {row.error_message ? ` - ${row.error_message}` : ""}
                </li>
              ))}
            </ul>
          </div>
        )}
        {sanctionsStatus?.external_sources && sanctionsStatus.external_sources.length > 0 && (
          <div className="mb-3 overflow-x-auto rounded border border-gray-200">
            <table className="w-full min-w-[780px] text-left text-xs">
              <thead className="bg-gray-50 text-xlent-muted">
                <tr>
                  <th className="px-2 py-1.5">{t("sanctioned_entities.col_source")}</th>
                  <th className="px-2 py-1.5">{t("sanctioned_entities.col_status")}</th>
                  <th className="px-2 py-1.5">{t("sanctioned_entities.col_entries")}</th>
                  <th className="px-2 py-1.5">{t("sanctioned_entities.col_last_updated")}</th>
                  <th className="px-2 py-1.5">{t("sanctioned_entities.col_stale")}</th>
                </tr>
              </thead>
              <tbody>
                {sanctionsStatus.external_sources.map((row) => (
                  <tr key={row.source} className="border-t border-gray-100 text-xlent-ink">
                    <td className="px-2 py-1.5">{row.source}</td>
                    <td className={clsx("px-2 py-1.5", row.status === "ok" ? "text-green-700" : "text-red-700")}>
                      {row.status}
                    </td>
                    <td className="px-2 py-1.5">
                      {row.entry_count != null ? row.entry_count.toLocaleString(locale) : "—"}
                    </td>
                    <td className="px-2 py-1.5">
                      {row.last_updated ? new Date(row.last_updated).toLocaleString(locale) : "—"}
                    </td>
                    <td className="px-2 py-1.5">{row.stale ? t("sanctioned_entities.yes") : t("sanctioned_entities.no")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder={t("sanctioned_entities.search_placeholder")}
            className={clsx(selectCls, "w-full min-w-[220px] flex-1 text-sm")}
          />
          <select
            value={entityType}
            onChange={(e) => {
              setOffset(0);
              setEntityType(e.target.value as SanctionedEntityType);
            }}
            className={selectCls}
            aria-label={t("sanctioned_entities.entity_type_aria")}
          >
            <option value="all">{t("sanctioned_entities.entity_type_all")}</option>
            <option value="company">{t("sanctioned_entities.entity_type_company")}</option>
            <option value="person">{t("sanctioned_entities.entity_type_person")}</option>
          </select>
        </div>

        <div className="mt-2 text-xs text-xlent-muted">
          {t("sanctioned_entities.hits")}: {resultText}
          {isFetching && !isLoading && <span className="ml-2">{t("sanctioned_entities.refreshing")}</span>}
        </div>
      </section>

      <section>
        {isLoading && <p className="text-sm text-xlent-muted">{t("sanctioned_entities.loading")}</p>}
        {error && (
          <p className="text-sm text-traffic-red">
            {t("sanctioned_entities.load_error")}
          </p>
        )}

        {data && (
          <>
            <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-xlent-surface text-left text-xs uppercase text-xlent-muted">
                  <tr>
                    <th className="px-3 py-2">{t("sanctioned_entities.col_name")}</th>
                    <th className="px-3 py-2">{t("sanctioned_entities.col_type")}</th>
                    <th className="px-3 py-2">{t("sanctioned_entities.col_dataset")}</th>
                    <th className="px-3 py-2">{t("sanctioned_entities.col_country")}</th>
                    <th className="px-3 py-2">{t("sanctioned_entities.col_last_seen")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data.items.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-3 py-6 text-center text-xlent-muted">
                        {t("sanctioned_entities.no_hits")}
                      </td>
                    </tr>
                  )}
                  {data.items.map((entity) => (
                    <tr key={entity.id} className="hover:bg-xlent-surface">
                      <td className="px-3 py-2">
                        <div className="font-medium text-xlent-ink">{entity.caption}</div>
                        <div className="font-mono text-[11px] text-xlent-muted">{entity.id}</div>
                      </td>
                      <td className="px-3 py-2 text-xs text-xlent-muted">{entity.schema}</td>
                      <td className="px-3 py-2 text-xs text-xlent-muted">
                        {entity.datasets.length > 0 ? entity.datasets.join(", ") : "—"}
                      </td>
                      <td className="px-3 py-2 text-xs uppercase text-xlent-muted">
                        {entity.countries.length > 0 ? entity.countries.join(", ") : "—"}
                      </td>
                      <td className="px-3 py-2 text-xs text-xlent-muted">
                        {entity.last_seen
                          ? new Date(entity.last_seen).toLocaleString(locale, {
                              dateStyle: "short",
                              timeStyle: "short",
                            })
                          : "—"}
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
              onPrev={() => setOffset((prev) => Math.max(0, prev - limit))}
              onNext={() => setOffset((prev) => prev + limit)}
            />
          </>
        )}
      </section>
    </div>
  );
}
