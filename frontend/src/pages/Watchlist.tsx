/**
 * Intern sperreliste — administrasjon.
 *
 * Viser alle oppføringer i den interne sperrelisten og lar
 * compliance_officer/admin legge til, redigere og deaktivere oppføringer.
 * Treff fra sperrelisten dukker opp som ScreeningResults under screeningen.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useTranslation } from "react-i18next";

import {
  listWatchlist,
  createWatchlistEntry,
  toggleWatchlistEntry,
  deleteWatchlistEntry,
} from "@/api/watchlist";
import type { WatchlistEntry, WatchlistEntryType, WatchlistSeverity } from "@/api/types";

// ── Konstanter ────────────────────────────────────────────────────────────────

const SEVERITY_COLORS: Record<WatchlistSeverity, string> = {
  red: "bg-red-100 text-red-800 border-red-200",
  yellow: "bg-amber-100 text-amber-800 border-amber-200",
};

// ── Tillegg-skjema ────────────────────────────────────────────────────────────

interface AddFormState {
  entry_type: WatchlistEntryType;
  value: string;
  reason: string;
  severity: WatchlistSeverity;
  added_by: string;
}

const EMPTY_FORM: AddFormState = {
  entry_type: "name",
  value: "",
  reason: "",
  severity: "red",
  added_by: "admin",
};

function AddEntryForm({ onCancel, onSaved }: { onCancel: () => void; onSaved: () => void }) {
  const { t } = useTranslation("watchlist");
  const [form, setForm] = useState<AddFormState>(EMPTY_FORM);
  const qc = useQueryClient();
  const entryTypeLabels: Record<WatchlistEntryType, string> = {
    name: t("type_name"),
    email_domain: t("type_email_domain"),
    country: t("type_country"),
    regex: t("type_regex"),
  };
  const entryTypePlaceholders: Record<WatchlistEntryType, string> = {
    name: t("placeholder_name"),
    email_domain: t("placeholder_email"),
    country: t("placeholder_country"),
    regex: t("placeholder_regex"),
  };

  const mutation = useMutation({
    mutationFn: () =>
      createWatchlistEntry({
        entry_type: form.entry_type,
        value: form.value.trim(),
        reason: form.reason.trim() || undefined,
        severity: form.severity,
        added_by: form.added_by || "admin",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      onSaved();
    },
  });

  const set = <K extends keyof AddFormState>(key: K, value: AddFormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const inputCls =
    "w-full rounded border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-xlent-primary/30";

  return (
    <div className="rounded-lg border border-xlent-primary/20 bg-blue-50 p-4">
      <h3 className="mb-3 text-sm font-semibold text-xlent-ink">{t("form.title")}</h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* Type */}
        <div>
          <label className="mb-1 block text-xs font-semibold text-xlent-muted">{t("form.type_label")}</label>
          <select
            value={form.entry_type}
            onChange={(e) => set("entry_type", e.target.value as WatchlistEntryType)}
            className={inputCls}
          >
            {Object.entries(entryTypeLabels).map(([k, label]) => (
              <option key={k} value={k}>{label}</option>
            ))}
          </select>
        </div>

        {/* Alvorlighet */}
        <div>
          <label className="mb-1 block text-xs font-semibold text-xlent-muted">{t("form.severity_label")}</label>
          <select
            value={form.severity}
            onChange={(e) => set("severity", e.target.value as WatchlistSeverity)}
            className={inputCls}
          >
            <option value="red">{t("form.severity_red")}</option>
            <option value="yellow">{t("form.severity_yellow")}</option>
          </select>
        </div>

        {/* Verdi */}
        <div className="sm:col-span-2">
          <label className="mb-1 block text-xs font-semibold text-xlent-muted">
            {entryTypeLabels[form.entry_type]}
          </label>
          <input
            type="text"
            value={form.value}
            onChange={(e) => set("value", e.target.value)}
            placeholder={entryTypePlaceholders[form.entry_type]}
            className={inputCls}
          />
        </div>

        {/* Årsak */}
        <div className="sm:col-span-2">
          <label className="mb-1 block text-xs font-semibold text-xlent-muted">
            {t("form.reason_label")}
          </label>
          <input
            type="text"
            value={form.reason}
            onChange={(e) => set("reason", e.target.value)}
            placeholder={t("form.reason_placeholder")}
            className={inputCls}
          />
        </div>
      </div>

      {mutation.error && (
        <p className="mt-2 text-xs text-red-600">
          {String((mutation.error as Error)?.message ?? mutation.error)}
        </p>
      )}

      <div className="mt-4 flex justify-end gap-2">
        <button
          onClick={onCancel}
          className="rounded border border-gray-200 px-3 py-1.5 text-sm text-xlent-muted hover:bg-gray-50"
        >
          {t("form.cancel")}
        </button>
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !form.value.trim()}
          className="rounded bg-xlent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-xlent-primary/90 disabled:opacity-50"
        >
          {mutation.isPending ? t("form.saving") : t("form.add")}
        </button>
      </div>
    </div>
  );
}

// ── Oppføring-rad ─────────────────────────────────────────────────────────────

function EntryRow({
  entry,
  onToggle,
  onDelete,
}: {
  entry: WatchlistEntry;
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const { t, i18n } = useTranslation("watchlist");
  const locale = i18n.language === "en" ? "en-GB" : "nb-NO";
  const createdAt = new Date(entry.created_at).toLocaleDateString(locale);
  const entryTypeLabels: Record<WatchlistEntryType, string> = {
    name: t("type_name"),
    email_domain: t("type_email_domain"),
    country: t("type_country"),
    regex: t("type_regex"),
  };

  return (
    <tr
      className={clsx(
        "border-t border-gray-100",
        !entry.is_active && "opacity-50",
      )}
    >
      <td className="px-3 py-2 text-xs text-xlent-muted">
        {entryTypeLabels[entry.entry_type] ?? entry.entry_type}
      </td>
      <td className="px-3 py-2 font-mono text-sm">
        {entry.value}
      </td>
      <td className="px-3 py-2">
        <span
          className={clsx(
            "inline-flex rounded border px-1.5 py-0.5 text-[11px] font-medium",
            SEVERITY_COLORS[entry.severity] ?? "bg-gray-100 text-gray-700",
          )}
        >
          {entry.severity === "red" ? t("entry.severity_red") : t("entry.severity_yellow")}
        </span>
      </td>
      <td className="px-3 py-2 text-sm text-xlent-muted">
          {entry.reason ?? "—"}
      </td>
      <td className="px-3 py-2 text-xs text-xlent-muted">{entry.added_by}</td>
      <td className="px-3 py-2 text-xs text-xlent-muted">{createdAt}</td>
      <td className="px-3 py-2">
        <span
          className={clsx(
            "inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold",
            entry.is_active
              ? "bg-green-100 text-green-700"
              : "bg-gray-100 text-gray-500",
          )}
        >
          {entry.is_active ? t("entry.active") : t("entry.inactive")}
        </span>
      </td>
      <td className="px-3 py-2 text-right">
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={() => onToggle(entry.id)}
            className="rounded border border-gray-200 px-2 py-0.5 text-xs text-xlent-muted hover:bg-gray-50"
          >
            {entry.is_active ? t("entry.deactivate") : t("entry.activate")}
          </button>
          <button
            onClick={() => {
              if (
                window.confirm(
                  t("entry.delete_confirm", { value: entry.value }),
                )
              ) {
                onDelete(entry.id);
              }
            }}
            className="rounded px-2 py-0.5 text-xs text-red-600 hover:bg-red-50"
          >
            {t("entry.delete")}
          </button>
        </div>
      </td>
    </tr>
  );
}

// ── Hovedelement ──────────────────────────────────────────────────────────────

export function WatchlistPage() {
  const { t } = useTranslation("watchlist");
  const [showForm, setShowForm] = useState(false);
  const [showInactive, setShowInactive] = useState(false);
  const qc = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["watchlist", showInactive],
    queryFn: () => listWatchlist({ active_only: !showInactive }),
    staleTime: 30_000,
  });

  const toggleMutation = useMutation({
    mutationFn: (id: string) => toggleWatchlistEntry(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteWatchlistEntry(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  const entries = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-xlent-ink">{t("title")}</h1>
          <p className="mt-1 text-sm text-xlent-muted">
            {t("subtitle")}
          </p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="shrink-0 rounded-lg bg-xlent-primary px-4 py-2 text-sm font-medium text-white hover:bg-xlent-primary/90"
        >
          {t("add_button")}
        </button>
      </div>

      {/* Forklaringsboks */}
      <div className="rounded-lg border border-gray-100 bg-gray-50 p-4 text-xs text-xlent-muted">
        <p className="font-semibold">{t("info_title")}</p>
        <ul className="mt-1 space-y-0.5">
          <li>{t("info_name")}</li>
          <li>{t("info_email")}</li>
          <li>{t("info_country")}</li>
          <li>{t("info_regex")}</li>
        </ul>
      </div>

      {/* Tillegg-skjema */}
      {showForm && (
        <AddEntryForm
          onCancel={() => setShowForm(false)}
          onSaved={() => setShowForm(false)}
        />
      )}

      {/* Tabell */}
      <section>
        <div className="mb-3 flex items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
            {t("table.entries", { total })}
          </p>
          <label className="flex items-center gap-1.5 text-xs text-xlent-muted cursor-pointer">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
              className="rounded border-gray-300"
            />
            {t("table.show_inactive")}
          </label>
        </div>

        {isLoading && <p className="py-4 text-sm text-xlent-muted">{t("table.loading")}</p>}
        {error && <p className="py-4 text-sm text-red-600">{t("table.error")}</p>}

        {!isLoading && entries.length === 0 && (
          <div className="rounded-lg border border-dashed border-gray-200 py-12 text-center">
            <p className="text-sm text-xlent-muted">
              {showInactive
                ? t("table.empty_inactive")
                : t("table.empty")}
            </p>
          </div>
        )}

        {entries.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-xlent-muted bg-gray-50">
                  <th className="px-3 py-2">{t("table.col_type")}</th>
                  <th className="px-3 py-2">{t("table.col_value")}</th>
                  <th className="px-3 py-2">{t("table.col_severity")}</th>
                  <th className="px-3 py-2">{t("table.col_reason")}</th>
                  <th className="px-3 py-2">{t("table.col_added_by")}</th>
                  <th className="px-3 py-2">{t("table.col_date")}</th>
                  <th className="px-3 py-2">{t("table.col_status")}</th>
                  <th className="px-3 py-2 text-right">{t("table.col_actions")}</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <EntryRow
                    key={entry.id}
                    entry={entry}
                    onToggle={(id) => toggleMutation.mutate(id)}
                    onDelete={(id) => deleteMutation.mutate(id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
