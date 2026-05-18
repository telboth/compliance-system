/**
 * ReviewQueue — liste over fakturaer som venter på manuell beslutning.
 *
 * Viser fakturaer med compliance_score yellow/red som er i status
 * screened, approved eller blocked. Sortert RED-først, ubehandlede-først.
 */
import { Link } from "react-router-dom";
import clsx from "clsx";
import { useTranslation } from "react-i18next";

import { StatusBadge } from "@/components/StatusBadge";
import { useReviewQueue } from "@/hooks/useInvoices";
import type { ReviewQueueItem, ComplianceScore } from "@/api/types";

// ── Compliance-score chip ────────────────────────────────────────────────────

function ScoreChip({ score }: { score: ComplianceScore | null }) {
  if (!score) return <span className="text-xs text-xlent-muted">—</span>;
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold uppercase tracking-wide",
        score === "red"
          ? "bg-red-100 text-red-700"
          : score === "yellow"
            ? "bg-yellow-100 text-yellow-700"
            : "bg-green-100 text-green-700",
      )}
    >
      {score === "red" ? "🔴" : score === "yellow" ? "🟡" : "🟢"} {score}
    </span>
  );
}

// ── Rad i tabellen ────────────────────────────────────────────────────────────

function QueueRow({ item }: { item: ReviewQueueItem }) {
  const isPending = item.status === "screened";
  const { t, i18n } = useTranslation("pages");
  const { t: tCommon } = useTranslation();
  return (
    <tr className="border-t border-gray-100 hover:bg-xlent-surface/50">
      <td className="py-3 pl-4 pr-2">
        <ScoreChip score={item.compliance_score} />
      </td>
      <td className="py-3 px-2">
        <Link
          to={`/invoices/${item.id}`}
          className="font-medium text-xlent-primary hover:underline"
        >
          {item.original_filename ?? item.invoice_number ?? item.id.slice(0, 8)}
        </Link>
        {item.invoice_number && item.original_filename && (
          <span className="ml-2 text-xs text-xlent-muted">#{item.invoice_number}</span>
        )}
      </td>
      <td className="py-3 px-2 text-sm text-xlent-muted capitalize">
        {tCommon(`direction.${item.direction}`)}
      </td>
      <td className="py-3 px-2 text-sm text-xlent-muted">
        {item.destination_country ?? "—"}
      </td>
      <td className="py-3 px-2 text-sm tabular-nums text-xlent-muted">
        {item.total_amount
          ? `${Number(item.total_amount).toLocaleString(i18n.language === "en" ? "en-GB" : "nb-NO")} ${item.currency ?? ""}`
          : "—"}
      </td>
      <td className="py-3 px-2">
        <StatusBadge status={item.status} score={item.compliance_score} />
      </td>
      <td className="py-3 px-2 text-xs text-xlent-muted">
        {isPending ? (
          <span className="font-medium text-amber-700">{t("review_queue.decision_pending")}</span>
        ) : (
          <span className={item.review_decision === "approved" ? "text-green-700" : "text-red-700"}>
            {item.review_decision === "approved" ? t("review_queue.decision_approved") : t("review_queue.decision_blocked")}
          </span>
        )}
      </td>
      <td className="py-3 pl-2 pr-4 text-xs text-xlent-muted">
        {new Date(item.created_at).toLocaleDateString(i18n.language === "en" ? "en-GB" : "nb-NO")}
      </td>
    </tr>
  );
}

// ── Tom tilstand ──────────────────────────────────────────────────────────────

function EmptyState() {
  const { t } = useTranslation("pages");
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 text-4xl">✅</div>
      <h3 className="mb-1 text-base font-semibold text-xlent-ink">
        {t("review_queue.empty_title")}
      </h3>
      <p className="text-sm text-xlent-muted">
        {t("review_queue.empty_subtitle")}
      </p>
    </div>
  );
}

// ── Hovedside ─────────────────────────────────────────────────────────────────

export function ReviewQueuePage() {
  const { t } = useTranslation("pages");
  const { data, isLoading, error } = useReviewQueue({ limit: 100 });

  const pending = data?.items.filter((i) => i.status === "screened") ?? [];
  const decided = data?.items.filter((i) => i.status !== "screened") ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-xlent-ink">{t("review_queue.title")}</h1>
        <p className="mt-1 text-sm text-xlent-muted">
          {t("review_queue.subtitle")}
        </p>
      </header>

      {/* Oppsummering */}
      {data && (
        <div className="flex flex-wrap gap-4">
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-center">
            <div className="text-2xl font-bold text-amber-700">{pending.length}</div>
            <div className="text-xs text-amber-800">{t("review_queue.pending")}</div>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-center">
            <div className="text-2xl font-bold text-xlent-ink">{decided.length}</div>
            <div className="text-xs text-xlent-muted">{t("review_queue.decided")}</div>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-center">
            <div className="text-2xl font-bold text-xlent-ink">{total}</div>
            <div className="text-xs text-xlent-muted">{t("review_queue.total")}</div>
          </div>
        </div>
      )}

      {isLoading && (
        <p className="text-sm text-xlent-muted">{t("review_queue.loading")}</p>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {t("review_queue.error")}
        </div>
      )}

      {!isLoading && !error && total === 0 && <EmptyState />}

      {!isLoading && !error && total > 0 && (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full">
            <thead>
              <tr className="bg-xlent-surface text-left text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                <th className="py-2 pl-4 pr-2">{t("review_queue.col_score")}</th>
                <th className="px-2 py-2">{t("review_queue.col_invoice")}</th>
                <th className="px-2 py-2">{t("review_queue.col_direction")}</th>
                <th className="px-2 py-2">{t("review_queue.col_dest")}</th>
                <th className="px-2 py-2">{t("review_queue.col_amount")}</th>
                <th className="px-2 py-2">{t("review_queue.col_status")}</th>
                <th className="px-2 py-2">{t("review_queue.col_decision")}</th>
                <th className="pl-2 pr-4 py-2">{t("review_queue.col_date")}</th>
              </tr>
            </thead>
            <tbody>
              {/* Ubehandlede fakturaer — uthevet øverst */}
              {pending.length > 0 && (
                <>
                  {pending.map((item) => (
                    <QueueRow key={item.id} item={item} />
                  ))}
                </>
              )}
              {/* Behandlede fakturaer */}
              {decided.length > 0 && (
                <>
                  {pending.length > 0 && (
                    <tr>
                      <td
                        colSpan={8}
                        className="bg-gray-50 px-4 py-2 text-[11px] font-semibold uppercase tracking-wider text-xlent-muted"
                      >
                        {t("review_queue.section_decided")}
                      </td>
                    </tr>
                  )}
                  {decided.map((item) => (
                    <QueueRow key={item.id} item={item} />
                  ))}
                </>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
