/**
 * CatchAll — arbeidsliste over fakturaer med sluttbruker-/sluttbrukrisiko.
 *
 * Det tredje benet i eksportkontroll (DEKSAs «catch-all»): selv varer som
 * ikke står på varelistene kan kreve lisens dersom sluttbruker eller
 * sluttbruk er sensitiv, eller det er diversjonsrisiko. Fakturaer
 * fargekodes etter alvorlighetsgrad.
 *
 * VIKTIG: Beslutningsstøtte, ikke en juridisk avgjørelse — endelig vurdering
 * krever egenvurdering og evt. sluttbrukererklæring.
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import clsx from "clsx";

import { listCatchAllInvoices } from "@/api/catchAll";
import { InvoiceFilePreviewLink } from "@/components/InvoiceFilePreview";
import type {
  CatchAllSignal,
  CatchAllSignalType,
  ExportControlStatus,
} from "@/api/types";

// ── Status-chip ───────────────────────────────────────────────────────────────

function StatusChip({ status }: { status: ExportControlStatus }) {
  const { t } = useTranslation("pages");
  if (status === "controlled") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
        🔴 {t("catch_all.status_controlled")}
      </span>
    );
  }
  if (status === "review") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-semibold text-yellow-700">
        🟡 {t("catch_all.status_review")}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
      🟢 {t("catch_all.status_clear")}
    </span>
  );
}

const SIGNAL_ICON: Record<CatchAllSignalType, string> = {
  embargoed_end_user: "⛔",
  military_end_user: "🎖",
  nuclear_end_user: "☢",
  sensitive_end_use: "⚠",
  diversion_risk: "🔀",
  undeclared_end_user: "❓",
};

function SignalList({ signals }: { signals: CatchAllSignal[] }) {
  const { t } = useTranslation("pages");
  return (
    <div className="flex flex-col gap-1.5">
      {signals.map((s, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2">
          <span
            className={clsx(
              "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold",
              s.severity === "red"
                ? "bg-red-50 text-red-700"
                : "bg-amber-50 text-amber-700",
            )}
            title={s.detail}
          >
            {SIGNAL_ICON[s.signal_type] ?? "•"}{" "}
            {t(`catch_all.signal.${s.signal_type}`, { defaultValue: s.title })}
          </span>
          {s.entity_name && (
            <span className="text-xs text-xlent-muted" title={s.detail}>
              {s.entity_name}
              {s.country ? ` (${s.country})` : ""}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Hovedelement ──────────────────────────────────────────────────────────────

export function CatchAllPage() {
  const { t } = useTranslation("pages");

  const [flaggedOnly, setFlaggedOnly] = useState(true);
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data, isLoading, error } = useQuery({
    queryKey: ["catch-all", flaggedOnly, offset],
    queryFn: () => listCatchAllInvoices({ flagged_only: flaggedOnly, limit, offset }),
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
          <h1 className="text-2xl font-semibold text-xlent-ink">{t("catch_all.title")}</h1>
          <p className="mt-1 text-sm text-xlent-muted">{t("catch_all.subtitle")}</p>
        </div>
        <Link to="/export-control" className="text-sm text-xlent-primary hover:underline">
          {t("catch_all.export_control_link")} →
        </Link>
      </header>

      {/* Disclaimer */}
      <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-xs text-blue-800">
        ℹ {t("catch_all.disclaimer")}
      </div>

      {/* Oppsummering */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-center">
          <div className="text-2xl font-bold text-amber-700">{totalFlagged}</div>
          <div className="text-xs text-amber-800">{t("catch_all.flagged_count")}</div>
        </div>
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-center">
          <div className="text-2xl font-bold text-red-700">{controlledCount}</div>
          <div className="text-xs text-red-800">{t("catch_all.controlled_count")}</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-xlent-ink">{totalScanned}</div>
          <div className="text-xs text-xlent-muted">{t("catch_all.scanned_count")}</div>
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
          {t("catch_all.flagged_only")}
        </label>
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-xlent-primary border-t-transparent" />
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-100 bg-red-50 p-4 text-sm text-red-700">
          {t("catch_all.loading_error")}
        </div>
      )}

      {!isLoading && !error && items.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-gray-200 bg-white py-16 text-center">
          <div className="mb-4 text-4xl">✅</div>
          <p className="text-sm font-medium text-xlent-ink">{t("catch_all.empty_title")}</p>
          <p className="mt-1 text-xs text-xlent-muted">{t("catch_all.empty_body")}</p>
        </div>
      )}

      {!isLoading && !error && items.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full">
            <thead>
              <tr className="bg-xlent-surface text-left text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                <th className="py-2 pl-4 pr-2">{t("catch_all.col_status")}</th>
                <th className="px-2 py-2">{t("catch_all.col_invoice")}</th>
                <th className="px-2 py-2">{t("catch_all.col_destination")}</th>
                <th className="py-2 pl-2 pr-4">{t("catch_all.col_signals")}</th>
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
                    {item.check.end_user_name && (
                      <div className="text-xs text-xlent-muted">
                        {t("catch_all.end_user")}: {item.check.end_user_name}
                      </div>
                    )}
                  </td>
                  <td className="px-2 py-3 text-sm text-xlent-muted">
                    {item.destination_country ?? "—"}
                  </td>
                  <td className="py-3 pl-2 pr-4">
                    <SignalList signals={item.check.signals} />
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
            {t("catch_all.pagination", {
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
