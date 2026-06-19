/**
 * ExportControl — arbeidsliste over fakturaer med mulig listematch.
 *
 * Matcher fakturalinjer mot DEKSAs Vareliste I (forsvarsmateriell) og
 * Vareliste II (flerbruksvarer/dual-use). Fakturaer fargekodes etter
 * alvorlighetsgrad. Controlleren får en arbeidsliste for å avgjøre om en
 * eksport krever lisens og egenvurdering mot lista.
 *
 * VIKTIG: Dette er beslutningsstøtte, ikke en juridisk avgjørelse — endelig
 * kontrollstatus krever eksportørens tekniske egenvurdering mot lista.
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import clsx from "clsx";

import { listExportControlInvoices } from "@/api/exportControl";
import { InvoiceFilePreviewLink } from "@/components/InvoiceFilePreview";
import type {
  ExportControlConfidence,
  ExportControlLineHit,
  ExportControlListCode,
  ExportControlStatus,
} from "@/api/types";

// ── Status-chip ───────────────────────────────────────────────────────────────

function StatusChip({ status }: { status: ExportControlStatus }) {
  const { t } = useTranslation("pages");
  if (status === "controlled") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
        🔴 {t("export_control.status_controlled")}
      </span>
    );
  }
  if (status === "review") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-semibold text-yellow-700">
        🟡 {t("export_control.status_review")}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
      🟢 {t("export_control.status_clear")}
    </span>
  );
}

// ── Liste-badge (I / II) ──────────────────────────────────────────────────────

function ListBadge({ code }: { code: ExportControlListCode }) {
  const isMilitary = code === "I";
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-semibold",
        isMilitary ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700",
      )}
      title={isMilitary ? "Vareliste I — forsvarsmateriell" : "Vareliste II — flerbruksvarer"}
    >
      🛡 Liste {code}
    </span>
  );
}

function ConfidenceDot({ confidence }: { confidence: ExportControlConfidence }) {
  const { t } = useTranslation("pages");
  const map: Record<ExportControlConfidence, string> = {
    high: "bg-red-500",
    medium: "bg-amber-400",
    low: "bg-gray-300",
  };
  return (
    <span
      className="inline-flex items-center gap-1 text-[11px] text-xlent-muted"
      title={t(`export_control.confidence.${confidence}`)}
    >
      <span className={clsx("inline-block h-2 w-2 rounded-full", map[confidence])} />
      {t(`export_control.confidence.${confidence}`)}
    </span>
  );
}

// ── Treff-detalj per faktura ──────────────────────────────────────────────────

function HitList({ hits }: { hits: ExportControlLineHit[] }) {
  const { t } = useTranslation("pages");
  // Dedupliser visning per (list, category)
  const seen = new Set<string>();
  const unique = hits.filter((h) => {
    const k = `${h.list_code}:${h.category}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  return (
    <div className="flex flex-col gap-1.5">
      {unique.map((h, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2">
          <ListBadge code={h.list_code} />
          <span className="text-xs font-medium text-xlent-ink">
            {h.item_code ?? h.category}
          </span>
          <span className="text-xs text-xlent-muted">{h.category_title}</span>
          <ConfidenceDot confidence={h.confidence} />
          <span className="rounded bg-gray-100 px-1 py-0.5 text-[10px] text-gray-500">
            {t(`export_control.via.${h.matched_via}`)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Hovedelement ──────────────────────────────────────────────────────────────

const LIST_FILTERS: { key: string; code?: ExportControlListCode }[] = [
  { key: "all" },
  { key: "I", code: "I" },
  { key: "II", code: "II" },
];

export function ExportControlPage() {
  const { t, i18n } = useTranslation("pages");
  const locale = i18n.language === "en" ? "en-GB" : "nb-NO";

  const [flaggedOnly, setFlaggedOnly] = useState(true);
  const [listFilter, setListFilter] = useState<ExportControlListCode | undefined>(undefined);
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data, isLoading, error } = useQuery({
    queryKey: ["export-control", flaggedOnly, listFilter, offset],
    queryFn: () =>
      listExportControlInvoices({
        flagged_only: flaggedOnly,
        list_filter: listFilter,
        limit,
        offset,
      }),
    staleTime: 60_000,
  });

  const items = data?.items ?? [];
  const totalFlagged = data?.total_flagged ?? 0;
  const totalScanned = data?.total_scanned ?? 0;
  const controlledCount = items.filter((i) => i.check.status === "controlled").length;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold text-xlent-ink">
            {t("export_control.title")}
          </h1>
          <p className="mt-1 text-sm text-xlent-muted">{t("export_control.subtitle")}</p>
        </div>
        <Link
          to="/export-control/reference"
          className="text-sm text-xlent-primary hover:underline"
        >
          {t("export_control.reference_link")} →
        </Link>
      </header>

      {/* Disclaimer — egenvurdering */}
      <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-xs text-blue-800">
        ℹ {t("export_control.disclaimer")}
      </div>

      {/* Oppsummering */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-center">
          <div className="text-2xl font-bold text-amber-700">{totalFlagged}</div>
          <div className="text-xs text-amber-800">{t("export_control.flagged_count")}</div>
        </div>
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-center">
          <div className="text-2xl font-bold text-red-700">{controlledCount}</div>
          <div className="text-xs text-red-800">{t("export_control.controlled_count")}</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-xlent-ink">{totalScanned}</div>
          <div className="text-xs text-xlent-muted">{t("export_control.scanned_count")}</div>
        </div>
        <label className="ml-auto flex cursor-pointer items-center gap-2 text-sm text-xlent-muted">
          <input
            type="checkbox"
            checked={flaggedOnly}
            onChange={(e) => {
              setFlaggedOnly(e.target.checked);
              setOffset(0);
            }}
            className="h-4 w-4 rounded border-gray-300"
          />
          {t("export_control.flagged_only")}
        </label>
      </div>

      {/* Liste-filter */}
      <div className="flex flex-wrap gap-2">
        {LIST_FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => {
              setListFilter(f.code);
              setOffset(0);
            }}
            className={clsx(
              "rounded-full border px-3 py-1 text-xs font-medium",
              listFilter === f.code
                ? "border-xlent-primary bg-xlent-primary text-white"
                : "border-gray-300 bg-white text-xlent-muted hover:bg-gray-50",
            )}
          >
            {t(`export_control.filter_${f.key}`)}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-xlent-primary border-t-transparent" />
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-100 bg-red-50 p-4 text-sm text-red-700">
          {t("export_control.loading_error")}
        </div>
      )}

      {!isLoading && !error && items.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-gray-200 bg-white py-16 text-center">
          <div className="mb-4 text-4xl">✅</div>
          <p className="text-sm font-medium text-xlent-ink">
            {t("export_control.empty_title")}
          </p>
          <p className="mt-1 text-xs text-xlent-muted">{t("export_control.empty_body")}</p>
        </div>
      )}

      {!isLoading && !error && items.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full">
            <thead>
              <tr className="bg-xlent-surface text-left text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                <th className="py-2 pl-4 pr-2">{t("export_control.col_status")}</th>
                <th className="px-2 py-2">{t("export_control.col_invoice")}</th>
                <th className="px-2 py-2">{t("export_control.col_destination")}</th>
                <th className="px-2 py-2">{t("export_control.col_hits")}</th>
                <th className="py-2 pl-2 pr-4">{t("export_control.col_date")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.invoice_id}
                  className={clsx(
                    "border-t border-gray-100 align-top hover:bg-xlent-surface/50",
                    item.check.status === "controlled" && "bg-red-50/40",
                  )}
                >
                  <td className="py-3 pl-4 pr-2">
                    <StatusChip status={item.check.status} />
                  </td>
                  <td className="px-2 py-3">
                    <InvoiceFilePreviewLink
                      invoiceId={item.invoice_id}
                      filename={item.original_filename}
                      invoiceNumber={item.invoice_number}
                      className="text-sm font-medium"
                    />
                    {item.invoice_number && item.original_filename && (
                      <span className="ml-2 text-xs text-xlent-muted">
                        #{item.invoice_number}
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-3 text-sm text-xlent-muted">
                    {item.destination_country ?? "—"}
                    {item.check.destination_sanctioned && (
                      <span className="ml-1 text-xs font-semibold text-red-600">
                        ⚠ {t("export_control.sanctioned")}
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-3">
                    <HitList hits={item.check.hits} />
                  </td>
                  <td className="py-3 pl-2 pr-4 text-xs text-xlent-muted">
                    {item.invoice_date
                      ? new Date(item.invoice_date).toLocaleDateString(locale)
                      : new Date(item.created_at).toLocaleDateString(locale)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Paginering */}
      {totalFlagged > limit && (
        <div className="flex items-center justify-between text-sm text-xlent-muted">
          <span>
            {t("export_control.pagination", {
              from: offset + 1,
              to: Math.min(offset + limit, totalFlagged),
              total: totalFlagged,
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
              disabled={offset + limit >= totalFlagged}
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
