/**
 * ListAdmin — administrasjon av automatiske listesynkroniseringer.
 *
 * Viser status for Vareliste I, Vareliste II og Embargo-lista.
 * Alle brukere kan sjekke og trigge import; URL-konfigurasjon er kun for admin.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import clsx from "clsx";

import {
  getExportListSyncStatus,
  checkExportListUpdates,
  importExportList,
  setExportListUrl,
} from "@/api/exportControl";
import {
  getEmbargoSyncStatus,
  checkEmbargoUpdates,
  importEmbargoList,
  setEmbargoListUrl,
} from "@/api/embargo";
import type { EmbargoSyncState, ExportListSyncState, ListSyncStatus } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";

// ── Helpers ───────────────────────────────────────────────────────────────────

function statusColor(status: ListSyncStatus) {
  switch (status) {
    case "ok": return "bg-emerald-100 text-emerald-800";
    case "update_available": return "bg-amber-100 text-amber-800";
    case "error": return "bg-red-100 text-red-800";
    case "importing":
    case "checking": return "bg-blue-100 text-blue-800";
    default: return "bg-gray-100 text-gray-600";
  }
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("nb-NO", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

// ── URL-editor ────────────────────────────────────────────────────────────────

function UrlEditor({
  current,
  onSave,
  saving,
}: {
  current: string | null;
  onSave: (url: string) => void;
  saving: boolean;
}) {
  const { t } = useTranslation("pages");
  const [open, setOpen] = useState(false);
  const [val, setVal] = useState(current ?? "");

  if (!open) {
    return (
      <button
        className="text-xs text-xlent-primary underline hover:opacity-80"
        onClick={() => { setVal(current ?? ""); setOpen(true); }}
      >
        {t("list_admin.url_edit")}
      </button>
    );
  }

  return (
    <div className="mt-2 flex gap-2">
      <input
        type="url"
        value={val}
        onChange={(e) => setVal(e.target.value)}
        placeholder="https://…"
        className="flex-1 rounded border border-gray-300 px-2 py-1 text-xs font-mono"
      />
      <button
        disabled={saving || !val.trim()}
        onClick={() => { onSave(val.trim()); setOpen(false); }}
        className="rounded bg-xlent-primary px-3 py-1 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
      >
        {saving ? t("list_admin.saving") : t("list_admin.url_save")}
      </button>
      <button
        onClick={() => setOpen(false)}
        className="rounded border border-gray-300 px-3 py-1 text-xs hover:bg-gray-50"
      >
        {t("list_admin.cancel")}
      </button>
    </div>
  );
}

// ── Sync-kort for én liste ────────────────────────────────────────────────────

interface SyncCardProps {
  label: string;
  listCode: string;
  state: ExportListSyncState | EmbargoSyncState | undefined;
  isLoading: boolean;
  onCheck: () => void;
  onImport: () => void;
  onSetUrl: (url: string) => void;
  checking: boolean;
  importing: boolean;
  savingUrl: boolean;
  isAdmin: boolean;
}

function SyncCard({
  label, listCode, state, isLoading,
  onCheck, onImport, onSetUrl,
  checking, importing, savingUrl, isAdmin,
}: SyncCardProps) {
  const { t } = useTranslation("pages");

  const status = state?.status ?? "idle";
  const hasSourceUrl = Boolean(state?.source_url);
  const hasUpdate = status === "update_available";
  const isBusy = status === "checking" || status === "importing" || checking || importing;

  return (
    <div className={clsx(
      "rounded-xl border bg-white p-5 shadow-sm transition-all",
      hasUpdate ? "border-amber-300" : "border-gray-200",
    )}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-xlent-ink">{label}</h2>
          {listCode && (
            <span className="mt-0.5 inline-block rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[11px] text-gray-500">
              {listCode}
            </span>
          )}
        </div>
        <span className={clsx("rounded-full px-2.5 py-0.5 text-xs font-medium", statusColor(status))}>
          {t(`list_admin.status.${status}`, { defaultValue: status })}
        </span>
      </div>

      {isLoading ? (
        <p className="mt-4 text-xs text-xlent-muted">{t("list_admin.loading")}</p>
      ) : state ? (
        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
          <div>
            <dt className="text-xlent-muted">{t("list_admin.last_checked")}</dt>
            <dd className="font-medium text-xlent-ink">{fmtDate(state.last_checked_at)}</dd>
          </div>
          <div>
            <dt className="text-xlent-muted">{t("list_admin.last_imported")}</dt>
            <dd className="font-medium text-xlent-ink">{fmtDate(state.last_imported_at)}</dd>
          </div>
          <div>
            <dt className="text-xlent-muted">{t("list_admin.version")}</dt>
            <dd className="font-medium text-xlent-ink">{state.current_version ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xlent-muted">{t("list_admin.item_count")}</dt>
            <dd className="font-medium text-xlent-ink">
              {state.item_count != null ? state.item_count.toLocaleString("nb-NO") : "—"}
            </dd>
          </div>
          {state.last_imported_by && (
            <div className="col-span-2">
              <dt className="text-xlent-muted">{t("list_admin.imported_by")}</dt>
              <dd className="font-medium text-xlent-ink">{state.last_imported_by}</dd>
            </div>
          )}
          {state.status_message && (
            <div className="col-span-2">
              <dt className="text-xlent-muted">{t("list_admin.message")}</dt>
              <dd className={clsx("font-medium", status === "error" ? "text-red-600" : "text-xlent-ink")}>
                {state.status_message}
              </dd>
            </div>
          )}
          {state.source_url && (
            <div className="col-span-2">
              <dt className="text-xlent-muted">{t("list_admin.source_url")}</dt>
              <dd className="truncate font-mono text-[11px] text-xlent-muted">{state.source_url}</dd>
            </div>
          )}
        </dl>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          disabled={isBusy || !hasSourceUrl}
          onClick={onCheck}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-xlent-ink hover:bg-gray-50 disabled:opacity-50"
        >
          {checking ? t("list_admin.checking") : t("list_admin.check_now")}
        </button>
        <button
          disabled={isBusy || !hasSourceUrl}
          onClick={onImport}
          className={clsx(
            "rounded-lg px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50",
            hasUpdate
              ? "bg-amber-500 hover:opacity-90"
              : "bg-xlent-primary hover:opacity-90",
          )}
        >
          {importing ? t("list_admin.importing") : t("list_admin.import_now")}
        </button>
      </div>
      {!hasSourceUrl && state && (
        <p className="mt-2 text-[11px] text-xlent-muted">
          {t("list_admin.no_source_url")}
        </p>
      )}

      {isAdmin && (
        <div className="mt-3 border-t border-gray-100 pt-3">
          <p className="mb-1 text-[11px] text-xlent-muted">{t("list_admin.url_label")}</p>
          <UrlEditor
            current={state?.source_url ?? null}
            onSave={onSetUrl}
            saving={savingUrl}
          />
        </div>
      )}
    </div>
  );
}

// ── Hoved-side ────────────────────────────────────────────────────────────────

export function ListAdminPage() {
  const { t } = useTranslation("pages");
  const { can } = useAuth();
  const qc = useQueryClient();
  const isAdmin = can("system:admin");

  // ── Queries ─────────────────────────────────────────────────────────────────
  const { data: vareLister, isLoading: loadingVL } = useQuery({
    queryKey: ["export-list-sync-status"],
    queryFn: getExportListSyncStatus,
    refetchInterval: 15_000,
  });

  const { data: embargoState, isLoading: loadingEmbargo } = useQuery({
    queryKey: ["embargo-sync-status"],
    queryFn: getEmbargoSyncStatus,
    refetchInterval: 15_000,
  });

  const stateI = vareLister?.find((s) => s.list_code === "I");
  const stateII = vareLister?.find((s) => s.list_code === "II");

  // ── Check-mutasjoner ─────────────────────────────────────────────────────────
  const checkVL = useMutation({
    mutationFn: checkExportListUpdates,
    onSettled: () => void qc.invalidateQueries({ queryKey: ["export-list-sync-status"] }),
  });
  const checkEmbargo = useMutation({
    mutationFn: checkEmbargoUpdates,
    onSettled: () => void qc.invalidateQueries({ queryKey: ["embargo-sync-status"] }),
  });

  // ── Import-mutasjoner ────────────────────────────────────────────────────────
  const importI = useMutation({
    mutationFn: () => importExportList("I"),
    onSettled: () => void qc.invalidateQueries({ queryKey: ["export-list-sync-status"] }),
  });
  const importII = useMutation({
    mutationFn: () => importExportList("II"),
    onSettled: () => void qc.invalidateQueries({ queryKey: ["export-list-sync-status"] }),
  });
  const importEmbargo = useMutation({
    mutationFn: () => importEmbargoList(),
    onSettled: () => void qc.invalidateQueries({ queryKey: ["embargo-sync-status"] }),
  });

  // ── URL-mutasjoner ───────────────────────────────────────────────────────────
  const setUrlI = useMutation({
    mutationFn: (url: string) => setExportListUrl("I", url),
    onSettled: () => void qc.invalidateQueries({ queryKey: ["export-list-sync-status"] }),
  });
  const setUrlII = useMutation({
    mutationFn: (url: string) => setExportListUrl("II", url),
    onSettled: () => void qc.invalidateQueries({ queryKey: ["export-list-sync-status"] }),
  });
  const setUrlEmbargo = useMutation({
    mutationFn: (url: string) => setEmbargoListUrl(url),
    onSettled: () => void qc.invalidateQueries({ queryKey: ["embargo-sync-status"] }),
  });

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-xlent-ink">{t("list_admin.title")}</h1>
        <p className="mt-1 text-sm text-xlent-muted">{t("list_admin.subtitle")}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <SyncCard
          label={t("list_admin.list_I")}
          listCode="I"
          state={stateI}
          isLoading={loadingVL}
          onCheck={() => checkVL.mutate()}
          onImport={() => importI.mutate()}
          onSetUrl={(url) => setUrlI.mutate(url)}
          checking={checkVL.isPending}
          importing={importI.isPending}
          savingUrl={setUrlI.isPending}
          isAdmin={isAdmin}
        />
        <SyncCard
          label={t("list_admin.list_II")}
          listCode="II"
          state={stateII}
          isLoading={loadingVL}
          onCheck={() => checkVL.mutate()}
          onImport={() => importII.mutate()}
          onSetUrl={(url) => setUrlII.mutate(url)}
          checking={checkVL.isPending}
          importing={importII.isPending}
          savingUrl={setUrlII.isPending}
          isAdmin={isAdmin}
        />
        <SyncCard
          label={t("list_admin.list_embargo")}
          listCode="EMBG"
          state={embargoState}
          isLoading={loadingEmbargo}
          onCheck={() => checkEmbargo.mutate()}
          onImport={() => importEmbargo.mutate()}
          onSetUrl={(url) => setUrlEmbargo.mutate(url)}
          checking={checkEmbargo.isPending}
          importing={importEmbargo.isPending}
          savingUrl={setUrlEmbargo.isPending}
          isAdmin={isAdmin}
        />
      </div>

      <div className="mt-8 rounded-lg border border-gray-200 bg-gray-50 p-4 text-xs text-xlent-muted">
        <p className="font-semibold text-xlent-ink">{t("list_admin.schedule_title")}</p>
        <p className="mt-1">{t("list_admin.schedule_body")}</p>
      </div>
    </div>
  );
}
