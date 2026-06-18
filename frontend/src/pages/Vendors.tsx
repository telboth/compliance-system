/**
 * Vendors — leverandørregister med risikoprofil.
 *
 * Viser alle leverandører systemet har sett i fakturaer, med antall
 * fakturaer, screening-treff og risikonivå. Controlleren kan raskt
 * identifisere leverandører som gir gjentatte flagg, og legge inn
 * egne notater per leverandør.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import clsx from "clsx";

import { listVendors, updateVendorNotes } from "@/api/vendors";
import type { Vendor } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";

// ── Risiko-chip ───────────────────────────────────────────────────────────────

function RiskChip({ level }: { level: string }) {
  const { t } = useTranslation("pages");
  const map: Record<string, { cls: string; icon: string }> = {
    critical: { cls: "bg-red-100 text-red-700", icon: "🔴" },
    high: { cls: "bg-orange-100 text-orange-700", icon: "🟠" },
    medium: { cls: "bg-yellow-100 text-yellow-700", icon: "🟡" },
    low: { cls: "bg-green-100 text-green-700", icon: "🟢" },
  };
  const conf = map[level] ?? { cls: "bg-gray-100 text-gray-600", icon: "⚪" };
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold",
        conf.cls,
      )}
    >
      {conf.icon} {t(`vendors.risk.${level}`, { defaultValue: level })}
    </span>
  );
}

// ── Notat-redigering ──────────────────────────────────────────────────────────

function NotesCell({ vendor, canEdit }: { vendor: Vendor; canEdit: boolean }) {
  const { t } = useTranslation("pages");
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(vendor.notes ?? "");

  const mutation = useMutation({
    mutationFn: (notes: string | null) => updateVendorNotes(vendor.id, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["vendors"] });
      setEditing(false);
    },
  });

  if (editing) {
    return (
      <div className="flex flex-col gap-1">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={2}
          className="w-full rounded border border-gray-300 px-2 py-1 text-xs"
          autoFocus
        />
        <div className="flex gap-1">
          <button
            type="button"
            onClick={() => mutation.mutate(draft.trim() || null)}
            disabled={mutation.isPending}
            className="rounded bg-xlent-primary px-2 py-0.5 text-[11px] font-medium text-white disabled:opacity-50"
          >
            {mutation.isPending ? t("vendors.notes_saving") : t("vendors.notes_save")}
          </button>
          <button
            type="button"
            onClick={() => {
              setDraft(vendor.notes ?? "");
              setEditing(false);
            }}
            className="rounded border border-gray-300 px-2 py-0.5 text-[11px] text-xlent-muted"
          >
            {t("vendors.notes_cancel")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => canEdit && setEditing(true)}
      disabled={!canEdit}
      className={clsx(
        "block w-full text-left text-xs",
        vendor.notes ? "text-xlent-ink" : "italic text-xlent-muted",
        canEdit && "cursor-pointer hover:underline",
      )}
      title={canEdit ? t("vendors.notes_edit_hint") : undefined}
    >
      {vendor.notes || t("vendors.notes_empty")}
    </button>
  );
}

// ── Hovedelement ──────────────────────────────────────────────────────────────

const RISK_LEVELS = ["critical", "high", "medium", "low"] as const;

export function VendorsPage() {
  const { t } = useTranslation("pages");
  const { can } = useAuth();
  const canEdit = can("customers:edit");

  const [riskFilter, setRiskFilter] = useState<string | undefined>(undefined);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data, isLoading, error } = useQuery({
    queryKey: ["vendors", riskFilter, search, offset],
    queryFn: () =>
      listVendors({
        risk_level: riskFilter,
        search: search.trim() || undefined,
        limit,
        offset,
      }),
    staleTime: 60_000,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  // Oppsummering pr. risikonivå — beregnes fra synlige rader
  const summary = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const v of items) counts[v.risk_level] = (counts[v.risk_level] ?? 0) + 1;
    return counts;
  }, [items]);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-xlent-ink">{t("vendors.title")}</h1>
        <p className="mt-1 text-sm text-xlent-muted">{t("vendors.subtitle")}</p>
      </header>

      {/* Filtre */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => {
            setRiskFilter(undefined);
            setOffset(0);
          }}
          className={clsx(
            "rounded-full border px-3 py-1 text-xs font-medium",
            !riskFilter
              ? "border-xlent-primary bg-xlent-primary text-white"
              : "border-gray-300 bg-white text-xlent-muted hover:bg-gray-50",
          )}
        >
          {t("vendors.filter_all")}
        </button>
        {RISK_LEVELS.map((level) => (
          <button
            key={level}
            type="button"
            onClick={() => {
              setRiskFilter(riskFilter === level ? undefined : level);
              setOffset(0);
            }}
            className={clsx(
              "rounded-full border px-3 py-1 text-xs font-medium",
              riskFilter === level
                ? "border-xlent-primary bg-xlent-primary text-white"
                : "border-gray-300 bg-white text-xlent-muted hover:bg-gray-50",
            )}
          >
            {t(`vendors.risk.${level}`)}
            {summary[level] != null && ` (${summary[level]})`}
          </button>
        ))}
        <input
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
          placeholder={t("vendors.search_placeholder")}
          className="ml-auto w-56 rounded-lg border border-gray-300 px-3 py-1.5 text-sm"
        />
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-xlent-primary border-t-transparent" />
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-100 bg-red-50 p-4 text-sm text-red-700">
          {t("vendors.loading_error")}
        </div>
      )}

      {!isLoading && !error && items.length === 0 && (
        <div className="rounded-lg border border-gray-200 bg-white py-12 text-center">
          <p className="text-sm font-medium text-xlent-ink">{t("vendors.empty_title")}</p>
          <p className="mt-1 text-xs text-xlent-muted">{t("vendors.empty_body")}</p>
        </div>
      )}

      {!isLoading && !error && items.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full">
            <thead>
              <tr className="bg-xlent-surface text-left text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                <th className="py-2 pl-4 pr-2">{t("vendors.col_risk")}</th>
                <th className="px-2 py-2">{t("vendors.col_name")}</th>
                <th className="px-2 py-2">{t("vendors.col_country")}</th>
                <th className="px-2 py-2 text-right">{t("vendors.col_invoices")}</th>
                <th className="px-2 py-2 text-right">{t("vendors.col_hits")}</th>
                <th className="px-2 py-2 text-right">{t("vendors.col_confirmed")}</th>
                <th className="py-2 pl-2 pr-4">{t("vendors.col_notes")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((vendor) => (
                <tr
                  key={vendor.id}
                  className="border-t border-gray-100 hover:bg-xlent-surface/50"
                >
                  <td className="py-3 pl-4 pr-2">
                    <RiskChip level={vendor.risk_level} />
                  </td>
                  <td className="px-2 py-3">
                    <span className="text-sm font-medium text-xlent-ink">
                      {vendor.name_display}
                    </span>
                    {vendor.email_domain && (
                      <span className="ml-2 text-xs text-xlent-muted">
                        @{vendor.email_domain}
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-3 text-sm text-xlent-muted">
                    {vendor.country ?? "—"}
                  </td>
                  <td className="px-2 py-3 text-right text-sm tabular-nums text-xlent-ink">
                    {vendor.invoice_count}
                  </td>
                  <td
                    className={clsx(
                      "px-2 py-3 text-right text-sm tabular-nums",
                      vendor.screening_hit_count > 0
                        ? "font-semibold text-amber-700"
                        : "text-xlent-muted",
                    )}
                  >
                    {vendor.screening_hit_count}
                  </td>
                  <td
                    className={clsx(
                      "px-2 py-3 text-right text-sm tabular-nums",
                      vendor.confirmed_hit_count > 0
                        ? "font-semibold text-red-700"
                        : "text-xlent-muted",
                    )}
                  >
                    {vendor.confirmed_hit_count}
                  </td>
                  <td className="max-w-[16rem] py-3 pl-2 pr-4">
                    <NotesCell vendor={vendor} canEdit={canEdit} />
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
            {t("vendors.pagination", {
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
