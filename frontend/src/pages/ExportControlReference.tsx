/**
 * ExportControlReference — oppslag og referanseliste for eksportkontroll.
 *
 * To verktøy for controlleren:
 *   1. Slå opp ett ECCN/ML-nummer og se hvilken vareliste/kategori det hører til.
 *   2. Bla i den importerte referanselista (Vareliste I/II) med søk og filter.
 *
 * Admin kan også kjøre backfill av historiske fakturaer herfra.
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import clsx from "clsx";

import {
  browseExportControlItems,
  classifyControlCode,
  runExportControlBackfill,
} from "@/api/exportControl";
import { runCatchAllBackfill } from "@/api/catchAll";
import type { ExportControlClassifyResponse, ExportControlListCode } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";

// ── Kode-oppslag ──────────────────────────────────────────────────────────────

function CodeLookup() {
  const { t } = useTranslation("pages");
  const [code, setCode] = useState("");
  const [submitted, setSubmitted] = useState<string | null>(null);

  const { data, isFetching, error } = useQuery<ExportControlClassifyResponse>({
    queryKey: ["ec-classify", submitted],
    queryFn: () => classifyControlCode(submitted as string),
    enabled: !!submitted,
    retry: false,
  });

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-xlent-ink">
        {t("export_control_ref.lookup_title")}
      </h2>
      <p className="mt-1 text-xs text-xlent-muted">{t("export_control_ref.lookup_hint")}</p>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(code.trim() || null);
        }}
      >
        <input
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="6A001 / ML10"
          className="w-48 rounded-lg border border-gray-300 px-3 py-1.5 font-mono text-sm"
        />
        <button
          type="submit"
          className="rounded-lg bg-xlent-primary px-4 py-1.5 text-sm font-medium text-white hover:opacity-90"
        >
          {t("export_control_ref.lookup_button")}
        </button>
      </form>

      {isFetching && (
        <p className="mt-3 text-xs text-xlent-muted">{t("export_control_ref.looking_up")}</p>
      )}
      {error && submitted && (
        <p className="mt-3 text-xs text-red-600">
          {t("export_control_ref.not_recognized", { code: submitted })}
        </p>
      )}
      {data && !isFetching && (
        <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={clsx(
                "rounded px-1.5 py-0.5 text-xs font-semibold",
                data.list_code === "I"
                  ? "bg-red-100 text-red-700"
                  : "bg-amber-100 text-amber-700",
              )}
            >
              🛡 Vareliste {data.list_code}
            </span>
            <span className="font-mono text-sm font-semibold text-xlent-ink">
              {data.normalized_code}
            </span>
            <span className="text-xs text-xlent-muted">
              {t("export_control_ref.category")} {data.category}
              {data.group ? `${data.group}` : ""}
            </span>
            {data.regime && (
              <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-600">
                {data.regime}
              </span>
            )}
          </div>
          <p className="mt-2 text-sm text-xlent-ink">{data.category_title_no}</p>
          <p className="text-xs text-xlent-muted">{data.category_title_en}</p>
        </div>
      )}
    </div>
  );
}

// ── Admin: backfill ───────────────────────────────────────────────────────────

function BackfillCard() {
  const { t } = useTranslation("pages");
  // Fyller begge arbeidslistene (vareliste + catch-all) i ett admin-klikk.
  const mutation = useMutation({
    mutationFn: async () => {
      const ec = await runExportControlBackfill(true);
      const ca = await runCatchAllBackfill(true);
      return { processed: ec.processed, flagged: ec.flagged + ca.flagged, rescored: ec.rescored + ca.rescored };
    },
  });

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-xlent-ink">
        {t("export_control_ref.backfill_title")}
      </h2>
      <p className="mt-1 text-xs text-xlent-muted">{t("export_control_ref.backfill_hint")}</p>
      <button
        type="button"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className="mt-3 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-xlent-ink hover:bg-gray-50 disabled:opacity-50"
      >
        {mutation.isPending
          ? t("export_control_ref.backfill_running")
          : t("export_control_ref.backfill_button")}
      </button>
      {mutation.data && (
        <p className="mt-3 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-700">
          {t("export_control_ref.backfill_done", {
            processed: mutation.data.processed,
            flagged: mutation.data.flagged,
            rescored: mutation.data.rescored,
          })}
        </p>
      )}
      {mutation.error && (
        <p className="mt-3 text-xs text-red-600">{t("export_control_ref.backfill_error")}</p>
      )}
    </div>
  );
}

// ── Referanseliste-bla ────────────────────────────────────────────────────────

const LIST_TABS: { key: string; code?: ExportControlListCode }[] = [
  { key: "all" },
  { key: "I", code: "I" },
  { key: "II", code: "II" },
];

function ReferenceBrowser() {
  const { t } = useTranslation("pages");
  const [listCode, setListCode] = useState<ExportControlListCode | undefined>(undefined);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 100;

  const { data, isLoading, error } = useQuery({
    queryKey: ["ec-items", listCode, search, offset],
    queryFn: () =>
      browseExportControlItems({
        list_code: listCode,
        search: search.trim() || undefined,
        limit,
        offset,
      }),
    staleTime: 60_000,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const itemCountTotal = data?.item_count_total ?? 0;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-xlent-ink">
          {t("export_control_ref.browse_title")}
        </h2>
        <span className="text-xs text-xlent-muted">
          {t("export_control_ref.imported_count", { count: itemCountTotal })}
        </span>
      </div>

      {itemCountTotal === 0 && (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {t("export_control_ref.not_imported")}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {LIST_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => {
              setListCode(tab.code);
              setOffset(0);
            }}
            className={clsx(
              "rounded-full border px-3 py-1 text-xs font-medium",
              listCode === tab.code
                ? "border-xlent-primary bg-xlent-primary text-white"
                : "border-gray-300 bg-white text-xlent-muted hover:bg-gray-50",
            )}
          >
            {t(`export_control_ref.tab_${tab.key}`)}
          </button>
        ))}
        <input
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
          placeholder={t("export_control_ref.search_placeholder")}
          className="ml-auto w-56 rounded-lg border border-gray-300 px-3 py-1.5 text-sm"
        />
      </div>

      {isLoading && (
        <div className="flex justify-center py-8">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-xlent-primary border-t-transparent" />
        </div>
      )}
      {error && (
        <p className="mt-3 text-xs text-red-600">{t("export_control_ref.browse_error")}</p>
      )}

      {!isLoading && !error && items.length > 0 && (
        <div className="mt-3 overflow-hidden rounded-lg border border-gray-200">
          <table className="min-w-full">
            <thead>
              <tr className="bg-xlent-surface text-left text-xs font-semibold uppercase tracking-wide text-xlent-muted">
                <th className="py-2 pl-3 pr-2">{t("export_control_ref.col_code")}</th>
                <th className="px-2 py-2">{t("export_control_ref.col_list")}</th>
                <th className="px-2 py-2">{t("export_control_ref.col_title")}</th>
                <th className="px-2 py-2">{t("export_control_ref.col_regime")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.id} className="border-t border-gray-100">
                  <td className="py-2 pl-3 pr-2 font-mono text-xs font-semibold text-xlent-ink">
                    {it.item_code}
                  </td>
                  <td className="px-2 py-2">
                    <span
                      className={clsx(
                        "rounded px-1.5 py-0.5 text-[11px] font-semibold",
                        it.list_code === "I"
                          ? "bg-red-50 text-red-700"
                          : "bg-amber-50 text-amber-700",
                      )}
                    >
                      {it.list_code} · {it.category}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-xs text-xlent-ink">{it.title ?? "—"}</td>
                  <td className="px-2 py-2 text-xs text-xlent-muted">{it.regime ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > limit && (
        <div className="mt-3 flex items-center justify-between text-xs text-xlent-muted">
          <span>
            {t("export_control_ref.pagination", {
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
              className="rounded border border-gray-300 px-3 py-1 disabled:opacity-40"
            >
              ←
            </button>
            <button
              type="button"
              disabled={offset + limit >= total}
              onClick={() => setOffset(offset + limit)}
              className="rounded border border-gray-300 px-3 py-1 disabled:opacity-40"
            >
              →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Hovedelement ──────────────────────────────────────────────────────────────

export function ExportControlReferencePage() {
  const { t } = useTranslation("pages");
  const { can } = useAuth();

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold text-xlent-ink">
            {t("export_control_ref.title")}
          </h1>
          <p className="mt-1 text-sm text-xlent-muted">{t("export_control_ref.subtitle")}</p>
        </div>
        <Link to="/export-control" className="text-sm text-xlent-primary hover:underline">
          ← {t("export_control_ref.back_to_worklist")}
        </Link>
      </header>

      <CodeLookup />
      {can("system:admin") && <BackfillCard />}
      <ReferenceBrowser />
    </div>
  );
}
