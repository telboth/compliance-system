/**
 * VatMismatch — fakturaer med mulig feilregistrert MVA.
 *
 * Eksport ut av Norge skal normalt være 0-sats; denne siden samler alle
 * fakturaer der avsender- og mottakerland er ulike men MVA likevel er
 * registrert. Controlleren får en arbeidsliste for oppfølging mot
 * regnskap/leverandør.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import clsx from "clsx";

import { listVatMismatches } from "@/api/invoices";
import { InvoiceFilePreviewLink } from "@/components/InvoiceFilePreview";
import { StatusBadge } from "@/components/StatusBadge";

export function VatMismatchPage() {
  const { t, i18n } = useTranslation("pages");
  const locale = i18n.language === "en" ? "en-GB" : "nb-NO";

  const [flaggedOnly, setFlaggedOnly] = useState(true);
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data, isLoading, error } = useQuery({
    queryKey: ["vat-mismatches", flaggedOnly, offset],
    queryFn: () => listVatMismatches({ flagged_only: flaggedOnly, limit, offset }),
    staleTime: 60_000,
  });

  const items = data?.items ?? [];
  const totalFlagged = data?.total_flagged ?? 0;
  const totalScanned = data?.total_scanned ?? 0;
  const shownTotal = flaggedOnly ? totalFlagged : totalScanned;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-xlent-ink">
          {t("vat_mismatch.title")}
        </h1>
        <p className="mt-1 text-sm text-xlent-muted">{t("vat_mismatch.subtitle")}</p>
      </header>

      {/* Oppsummering + toggle */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-center">
          <div className="text-2xl font-bold text-amber-700">{totalFlagged}</div>
          <div className="text-xs text-amber-800">{t("vat_mismatch.flagged_count")}</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-xlent-ink">{totalScanned}</div>
          <div className="text-xs text-xlent-muted">{t("vat_mismatch.scanned_count")}</div>
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
          {t("vat_mismatch.flagged_only")}
        </label>
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-xlent-primary border-t-transparent" />
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-100 bg-red-50 p-4 text-sm text-red-700">
          {t("vat_mismatch.loading_error")}
        </div>
      )}

      {!isLoading && !error && items.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-gray-200 bg-white py-16 text-center">
          <div className="mb-4 text-4xl">✅</div>
          <p className="text-sm font-medium text-xlent-ink">
            {t("vat_mismatch.empty_title")}
          </p>
          <p className="mt-1 text-xs text-xlent-muted">{t("vat_mismatch.empty_body")}</p>
        </div>
      )}

      {!isLoading && !error && items.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full">
            <thead>
              <tr className="bg-xlent-surface text-left text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                <th className="py-2 pl-4 pr-2">{t("vat_mismatch.col_invoice")}</th>
                <th className="px-2 py-2">{t("vat_mismatch.col_route")}</th>
                <th className="px-2 py-2 text-right">{t("vat_mismatch.col_vat")}</th>
                <th className="px-2 py-2">{t("vat_mismatch.col_status")}</th>
                <th className="px-2 py-2">{t("vat_mismatch.col_reason")}</th>
                <th className="py-2 pl-2 pr-4">{t("vat_mismatch.col_date")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const check = item.vat_check;
                return (
                  <tr
                    key={item.invoice_id}
                    className={clsx(
                      "border-t border-gray-100 hover:bg-xlent-surface/50",
                      check.flagged && "bg-amber-50/40",
                    )}
                  >
                    <td className="py-3 pl-4 pr-2">
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
                      {check.sender_country ?? "?"} → {check.receiver_country ?? "?"}
                    </td>
                    <td className="px-2 py-3 text-right text-sm tabular-nums text-xlent-ink">
                      {check.vat_amount != null
                        ? Number(check.vat_amount).toLocaleString(locale)
                        : "—"}
                      {check.vat_rate != null && (
                        <span className="ml-1 text-xs text-xlent-muted">
                          ({Number(check.vat_rate).toLocaleString(locale)} %)
                        </span>
                      )}
                    </td>
                    <td className="px-2 py-3">
                      <StatusBadge status={item.status} score={null} />
                    </td>
                    <td className="max-w-[18rem] px-2 py-3 text-xs text-xlent-muted">
                      {check.flagged ? (
                        <span className="font-medium text-amber-700">
                          {check.reason ?? t("vat_mismatch.default_reason")}
                        </span>
                      ) : (
                        <span>{t("vat_mismatch.not_flagged")}</span>
                      )}
                    </td>
                    <td className="py-3 pl-2 pr-4 text-xs text-xlent-muted">
                      {item.invoice_date
                        ? new Date(item.invoice_date).toLocaleDateString(locale)
                        : new Date(item.created_at).toLocaleDateString(locale)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Paginering */}
      {shownTotal > limit && (
        <div className="flex items-center justify-between text-sm text-xlent-muted">
          <span>
            {t("vat_mismatch.pagination", {
              from: offset + 1,
              to: Math.min(offset + limit, shownTotal),
              total: shownTotal,
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
              disabled={offset + limit >= shownTotal}
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
