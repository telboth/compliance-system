/**
 * ControlEffectiveness — avvik der fakturaer ble godkjent tross forhøyet risiko.
 *
 * Hver gang en reviewer godkjenner en faktura med yellow/red score
 * registreres et kontroll-avvik. Denne siden gir compliance-offiseren
 * og ledelsen oversikt over avvikene — spesielt gjentatte leverandører,
 * som kan tyde på at en kontroll i praksis er satt ut av spill.
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import clsx from "clsx";

import { listControlDeviations } from "@/api/controlDeviations";

// ── Avvikstype-chip ───────────────────────────────────────────────────────────

function DeviationChip({ type }: { type: string }) {
  const { t } = useTranslation("pages");
  const isRed = type === "approved_despite_red";
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold",
        isRed ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700",
      )}
    >
      {isRed ? "🔴" : "🟡"}{" "}
      {t(`control_effectiveness.type.${type}`, { defaultValue: type })}
    </span>
  );
}

// ── Hovedelement ──────────────────────────────────────────────────────────────

export function ControlEffectivenessPage() {
  const { t, i18n } = useTranslation("pages");
  const locale = i18n.language === "en" ? "en-GB" : "nb-NO";

  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined);
  const [repeatOnly, setRepeatOnly] = useState(false);
  const [vendorSearch, setVendorSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data, isLoading, error } = useQuery({
    queryKey: ["control-deviations", typeFilter, repeatOnly, vendorSearch, offset],
    queryFn: () =>
      listControlDeviations({
        deviation_type: typeFilter,
        is_repeat_vendor: repeatOnly || undefined,
        vendor_name: vendorSearch.trim() || undefined,
        limit,
        offset,
      }),
    staleTime: 60_000,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const redCount = items.filter(
    (d) => d.deviation_type === "approved_despite_red",
  ).length;
  const repeatCount = items.filter((d) => d.is_repeat_vendor).length;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-xlent-ink">
          {t("control_effectiveness.title")}
        </h1>
        <p className="mt-1 text-sm text-xlent-muted">
          {t("control_effectiveness.subtitle")}
        </p>
      </header>

      {/* Filtre */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => {
            setTypeFilter(undefined);
            setOffset(0);
          }}
          className={clsx(
            "rounded-full border px-3 py-1 text-xs font-medium",
            !typeFilter
              ? "border-xlent-primary bg-xlent-primary text-white"
              : "border-gray-300 bg-white text-xlent-muted hover:bg-gray-50",
          )}
        >
          {t("control_effectiveness.filter_all")}
        </button>
        <button
          type="button"
          onClick={() => {
            setTypeFilter(
              typeFilter === "approved_despite_yellow"
                ? undefined
                : "approved_despite_yellow",
            );
            setOffset(0);
          }}
          className={clsx(
            "rounded-full border px-3 py-1 text-xs font-medium",
            typeFilter === "approved_despite_yellow"
              ? "border-yellow-500 bg-yellow-500 text-white"
              : "border-gray-300 bg-white text-xlent-muted hover:bg-gray-50",
          )}
        >
          🟡 {t("control_effectiveness.type.approved_despite_yellow")}
        </button>
        <button
          type="button"
          onClick={() => {
            setTypeFilter(
              typeFilter === "approved_despite_red" ? undefined : "approved_despite_red",
            );
            setOffset(0);
          }}
          className={clsx(
            "rounded-full border px-3 py-1 text-xs font-medium",
            typeFilter === "approved_despite_red"
              ? "border-red-500 bg-red-500 text-white"
              : "border-gray-300 bg-white text-xlent-muted hover:bg-gray-50",
          )}
        >
          🔴 {t("control_effectiveness.type.approved_despite_red")}
        </button>

        <label className="flex cursor-pointer items-center gap-2 text-xs text-xlent-muted">
          <input
            type="checkbox"
            checked={repeatOnly}
            onChange={(e) => {
              setRepeatOnly(e.target.checked);
              setOffset(0);
            }}
            className="h-4 w-4 rounded border-gray-300"
          />
          {t("control_effectiveness.repeat_only")}
        </label>

        <input
          type="search"
          value={vendorSearch}
          onChange={(e) => {
            setVendorSearch(e.target.value);
            setOffset(0);
          }}
          placeholder={t("control_effectiveness.vendor_search_placeholder")}
          className="ml-auto w-56 rounded-lg border border-gray-300 px-3 py-1.5 text-sm"
        />
      </div>

      {/* Oppsummering */}
      {data && (
        <div className="flex flex-wrap gap-4">
          <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-center">
            <div className="text-2xl font-bold text-xlent-ink">{total}</div>
            <div className="text-xs text-xlent-muted">
              {t("control_effectiveness.count_total")}
            </div>
          </div>
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-center">
            <div className="text-2xl font-bold text-red-700">{redCount}</div>
            <div className="text-xs text-red-800">
              {t("control_effectiveness.count_red")}
            </div>
          </div>
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-center">
            <div className="text-2xl font-bold text-amber-700">{repeatCount}</div>
            <div className="text-xs text-amber-800">
              {t("control_effectiveness.count_repeat")}
            </div>
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
          {t("control_effectiveness.loading_error")}
        </div>
      )}

      {!isLoading && !error && items.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-gray-200 bg-white py-16 text-center">
          <div className="mb-4 text-4xl">✅</div>
          <p className="text-sm font-medium text-xlent-ink">
            {t("control_effectiveness.empty_title")}
          </p>
          <p className="mt-1 text-xs text-xlent-muted">
            {t("control_effectiveness.empty_body")}
          </p>
        </div>
      )}

      {!isLoading && !error && items.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full">
            <thead>
              <tr className="bg-xlent-surface text-left text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                <th className="py-2 pl-4 pr-2">{t("control_effectiveness.col_type")}</th>
                <th className="px-2 py-2">{t("control_effectiveness.col_vendor")}</th>
                <th className="px-2 py-2">{t("control_effectiveness.col_country")}</th>
                <th className="px-2 py-2">{t("control_effectiveness.col_reviewer")}</th>
                <th className="px-2 py-2">{t("control_effectiveness.col_reason")}</th>
                <th className="px-2 py-2">{t("control_effectiveness.col_repeat")}</th>
                <th className="py-2 pl-2 pr-4">{t("control_effectiveness.col_date")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((dev) => (
                <tr
                  key={dev.id}
                  className={clsx(
                    "border-t border-gray-100 hover:bg-xlent-surface/50",
                    dev.is_repeat_vendor && "bg-amber-50/40",
                  )}
                >
                  <td className="py-3 pl-4 pr-2">
                    <DeviationChip type={dev.deviation_type} />
                  </td>
                  <td className="px-2 py-3">
                    <Link
                      to={`/invoices/${dev.invoice_id}`}
                      className="text-sm font-medium text-xlent-primary hover:underline"
                    >
                      {dev.vendor_name ?? t("control_effectiveness.unknown_vendor")}
                    </Link>
                  </td>
                  <td className="px-2 py-3 text-sm text-xlent-muted">
                    {dev.destination_country ?? "—"}
                  </td>
                  <td className="px-2 py-3 text-sm text-xlent-muted">{dev.reviewed_by}</td>
                  <td
                    className="max-w-[16rem] truncate px-2 py-3 text-xs text-xlent-muted"
                    title={dev.reason_summary ?? undefined}
                  >
                    {dev.reason_summary ?? "—"}
                  </td>
                  <td className="px-2 py-3 text-xs">
                    {dev.is_repeat_vendor ? (
                      <span className="font-semibold text-amber-700">
                        ⚠ {t("control_effectiveness.repeat_yes")}
                      </span>
                    ) : (
                      <span className="text-xlent-muted">
                        {t("control_effectiveness.repeat_no")}
                      </span>
                    )}
                  </td>
                  <td className="py-3 pl-2 pr-4 text-xs text-xlent-muted">
                    {new Date(dev.created_at).toLocaleDateString(locale)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Paginering */}
      {total > limit && (
        <div className="flex items-center justify-between text-sm text-xlent-muted">
          <span>
            {t("control_effectiveness.pagination", {
              from: offset + 1,
              to: Math.min(offset + limit, total),
              total,
            })}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - limit))}
              className="rounded border border-gray-300 px-3 py-1 text-xs disabled:opacity-40"
            >
              ←
            </button>
            <button
              type="button"
              disabled={offset + limit >= total}
              onClick={() => setOffset(offset + limit)}
              className="rounded border border-gray-300 px-3 py-1 text-xs disabled:opacity-40"
            >
              →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
