/**
 * ReviewQueue — liste over fakturaer som venter på manuell beslutning.
 *
 * Viser fakturaer med compliance_score yellow/red som er i status
 * screened, approved eller blocked. Sortert RED-først, ubehandlede-først.
 */
import { Link } from "react-router-dom";
import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { useMemo, useState } from "react";

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

// ── Flagg-kilder ──────────────────────────────────────────────────────────────

/** Viser én pille per flagg-kilde som er aktiv på fakturaen. */
function FlagPills({ item }: { item: ReviewQueueItem }) {
  const { t } = useTranslation("pages");
  const flags: { active: boolean; icon: string; key: string; cls: string }[] = [
    { active: item.has_sanctions_hit, icon: "🚫", key: "sanctions", cls: "bg-red-100 text-red-700" },
    { active: item.has_embargo_hit, icon: "⛔", key: "embargo", cls: "bg-red-100 text-red-700" },
    { active: item.has_export_control, icon: "🛡", key: "export_control", cls: "bg-amber-100 text-amber-700" },
    { active: item.has_catch_all, icon: "🎯", key: "catch_all", cls: "bg-amber-100 text-amber-700" },
    { active: item.has_dual_use_risk, icon: "🔬", key: "dual_use", cls: "bg-yellow-100 text-yellow-700" },
    { active: item.has_ownership_risk, icon: "🏢", key: "ownership", cls: "bg-gray-100 text-gray-600" },
    { active: item.has_vat_deviation, icon: "％", key: "vat", cls: "bg-gray-100 text-gray-600" },
  ];
  const active = flags.filter((f) => f.active);
  if (active.length === 0) {
    return <span className="text-xs text-xlent-muted">—</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {active.map((f) => (
        <span
          key={f.key}
          className={clsx(
            "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold",
            f.cls,
          )}
          title={t(`review_queue.flag.${f.key}`)}
        >
          {f.icon} {t(`review_queue.flag.${f.key}`)}
        </span>
      ))}
    </div>
  );
}

// ── Rad i tabellen ────────────────────────────────────────────────────────────

function QueueRow({ item }: { item: ReviewQueueItem }) {
  const isPending = item.status === "screened";
  const { t, i18n } = useTranslation("pages");
  const { t: tCommon } = useTranslation();
  const claimText = (() => {
    if (!item.review_claimed_by) return t("review_queue.claim_open");
    if (item.claim_is_mine) return t("review_queue.claim_mine");
    if (item.claim_is_stale) return t("review_queue.claim_stale", { name: item.review_claimed_by });
    return t("review_queue.claim_other", { name: item.review_claimed_by });
  })();
  const claimClass = !item.review_claimed_by
    ? "text-green-700"
    : item.claim_is_mine
      ? "text-blue-700"
      : item.claim_is_stale
        ? "text-amber-700"
        : "text-red-700";
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
      <td className="py-3 px-2">
        <FlagPills item={item} />
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
      <td className={clsx("py-3 px-2 text-xs font-medium", claimClass)}>
        {claimText}
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
  const [quickFilter, setQuickFilter] = useState<
    | "all"
    | "sanctions"
    | "embargo"
    | "export_control"
    | "catch_all"
    | "ownership"
    | "dual_use"
    | "vat"
    | "awaiting"
  >("all");

  const filteredItems = useMemo(() => {
    const items = data?.items ?? [];
    if (quickFilter === "all") return items;
    if (quickFilter === "sanctions") return items.filter((i) => i.has_sanctions_hit);
    if (quickFilter === "embargo") return items.filter((i) => i.has_embargo_hit);
    if (quickFilter === "export_control") return items.filter((i) => i.has_export_control);
    if (quickFilter === "catch_all") return items.filter((i) => i.has_catch_all);
    if (quickFilter === "ownership") return items.filter((i) => i.has_ownership_risk);
    if (quickFilter === "dual_use") return items.filter((i) => i.has_dual_use_risk);
    if (quickFilter === "vat") return items.filter((i) => i.has_vat_deviation);
    if (quickFilter === "awaiting") return items.filter((i) => i.awaiting_approval);
    return items;
  }, [data?.items, quickFilter]);

  const pending = filteredItems.filter((i) => i.status === "screened");
  const decided = filteredItems.filter((i) => i.status !== "screened");
  const total = data?.total ?? 0;
  const shownTotal = filteredItems.length;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-xlent-ink">{t("review_queue.title")}</h1>
        <p className="mt-1 text-sm text-xlent-muted">
          {t("review_queue.subtitle")}
        </p>
      </header>

      {/* Hurtigfiltre */}
      <div className="flex flex-wrap gap-2">
        {[
          ["all", t("review_queue.filter_all")],
          ["sanctions", t("review_queue.filter_sanctions")],
          ["embargo", t("review_queue.filter_embargo")],
          ["export_control", t("review_queue.filter_export_control")],
          ["catch_all", t("review_queue.filter_catch_all")],
          ["ownership", t("review_queue.filter_ownership")],
          ["dual_use", t("review_queue.filter_dual_use")],
          ["vat", t("review_queue.filter_vat")],
          ["awaiting", t("review_queue.filter_awaiting")],
        ].map(([key, label]) => {
          const active = quickFilter === key;
          return (
            <button
              key={key}
              type="button"
              onClick={() => setQuickFilter(key as typeof quickFilter)}
              className={clsx(
                "rounded-full border px-3 py-1 text-xs font-medium",
                active
                  ? "border-xlent-primary bg-xlent-primary text-white"
                  : "border-gray-300 bg-white text-xlent-muted hover:bg-gray-50",
              )}
            >
              {label}
            </button>
          );
        })}
      </div>

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
            <div className="text-2xl font-bold text-xlent-ink">{shownTotal}</div>
            <div className="text-xs text-xlent-muted">
              {t("review_queue.total")} ({t("review_queue.of_total", { total })})
            </div>
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

      {!isLoading && !error && shownTotal === 0 && <EmptyState />}

      {!isLoading && !error && shownTotal > 0 && (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full">
            <thead>
              <tr className="bg-xlent-surface text-left text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                <th className="py-2 pl-4 pr-2">{t("review_queue.col_score")}</th>
                <th className="px-2 py-2">{t("review_queue.col_invoice")}</th>
                <th className="px-2 py-2">{t("review_queue.col_flags")}</th>
                <th className="px-2 py-2">{t("review_queue.col_direction")}</th>
                <th className="px-2 py-2">{t("review_queue.col_dest")}</th>
                <th className="px-2 py-2">{t("review_queue.col_amount")}</th>
                <th className="px-2 py-2">{t("review_queue.col_status")}</th>
                <th className="px-2 py-2">{t("review_queue.col_decision")}</th>
                <th className="px-2 py-2">{t("review_queue.col_claim")}</th>
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
                        colSpan={9}
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
