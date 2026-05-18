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

import {
  listWatchlist,
  createWatchlistEntry,
  toggleWatchlistEntry,
  deleteWatchlistEntry,
} from "@/api/watchlist";
import type { WatchlistEntry, WatchlistEntryType, WatchlistSeverity } from "@/api/types";

// ── Konstanter ────────────────────────────────────────────────────────────────

const ENTRY_TYPE_LABELS: Record<WatchlistEntryType, string> = {
  name: "Navn",
  email_domain: "E-postdomene",
  country: "Land (ISO-2)",
  regex: "Regex",
};

const ENTRY_TYPE_PLACEHOLDERS: Record<WatchlistEntryType, string> = {
  name: "f.eks. Rosneft Oil Company",
  email_domain: "f.eks. rosneft.ru",
  country: "f.eks. KP, RU, BY, IR",
  regex: "f.eks. (?i)rosneft|gazprom",
};

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
  const [form, setForm] = useState<AddFormState>(EMPTY_FORM);
  const qc = useQueryClient();

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
      <h3 className="mb-3 text-sm font-semibold text-xlent-ink">Ny oppføring</h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* Type */}
        <div>
          <label className="mb-1 block text-xs font-semibold text-xlent-muted">Type</label>
          <select
            value={form.entry_type}
            onChange={(e) => set("entry_type", e.target.value as WatchlistEntryType)}
            className={inputCls}
          >
            {Object.entries(ENTRY_TYPE_LABELS).map(([k, label]) => (
              <option key={k} value={k}>{label}</option>
            ))}
          </select>
        </div>

        {/* Alvorlighet */}
        <div>
          <label className="mb-1 block text-xs font-semibold text-xlent-muted">Alvorlighet</label>
          <select
            value={form.severity}
            onChange={(e) => set("severity", e.target.value as WatchlistSeverity)}
            className={inputCls}
          >
            <option value="red">🔴 Rød (bekreftet treff)</option>
            <option value="yellow">🟡 Gul (potensielt treff)</option>
          </select>
        </div>

        {/* Verdi */}
        <div className="sm:col-span-2">
          <label className="mb-1 block text-xs font-semibold text-xlent-muted">
            {ENTRY_TYPE_LABELS[form.entry_type]}
          </label>
          <input
            type="text"
            value={form.value}
            onChange={(e) => set("value", e.target.value)}
            placeholder={ENTRY_TYPE_PLACEHOLDERS[form.entry_type]}
            className={inputCls}
          />
        </div>

        {/* Årsak */}
        <div className="sm:col-span-2">
          <label className="mb-1 block text-xs font-semibold text-xlent-muted">
            Årsak / begrunnelse (valgfri)
          </label>
          <input
            type="text"
            value={form.reason}
            onChange={(e) => set("reason", e.target.value)}
            placeholder="f.eks. Sanksjonert entitet iflg. EU-forordning 833/2014"
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
          Avbryt
        </button>
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !form.value.trim()}
          className="rounded bg-xlent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-xlent-primary/90 disabled:opacity-50"
        >
          {mutation.isPending ? "Lagrer…" : "Legg til"}
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
  const createdAt = new Date(entry.created_at).toLocaleDateString("nb-NO");

  return (
    <tr
      className={clsx(
        "border-t border-gray-100",
        !entry.is_active && "opacity-50",
      )}
    >
      <td className="px-3 py-2 text-xs text-xlent-muted">
        {ENTRY_TYPE_LABELS[entry.entry_type] ?? entry.entry_type}
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
          {entry.severity === "red" ? "🔴 Rød" : "🟡 Gul"}
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
          {entry.is_active ? "Aktiv" : "Inaktiv"}
        </span>
      </td>
      <td className="px-3 py-2 text-right">
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={() => onToggle(entry.id)}
            className="rounded border border-gray-200 px-2 py-0.5 text-xs text-xlent-muted hover:bg-gray-50"
          >
            {entry.is_active ? "Deaktiver" : "Aktiver"}
          </button>
          <button
            onClick={() => {
              if (
                window.confirm(
                  `Slett oppføring «${entry.value}»?\n\nDette kan ikke angres.`,
                )
              ) {
                onDelete(entry.id);
              }
            }}
            className="rounded px-2 py-0.5 text-xs text-red-600 hover:bg-red-50"
          >
            Slett
          </button>
        </div>
      </td>
    </tr>
  );
}

// ── Hovedelement ──────────────────────────────────────────────────────────────

export function WatchlistPage() {
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
          <h1 className="text-2xl font-semibold text-xlent-ink">🚫 Intern sperreliste</h1>
          <p className="mt-1 text-sm text-xlent-muted">
            Navn, e-postdomener, landkoder og mønstre som automatisk flagges ved screening.
            Treff eskalerer compliance-score til rødt eller gult.
          </p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="shrink-0 rounded-lg bg-xlent-primary px-4 py-2 text-sm font-medium text-white hover:bg-xlent-primary/90"
        >
          + Legg til
        </button>
      </div>

      {/* Forklaringsboks */}
      <div className="rounded-lg border border-gray-100 bg-gray-50 p-4 text-xs text-xlent-muted">
        <p className="font-semibold">Oppføringstyper</p>
        <ul className="mt-1 space-y-0.5">
          <li><strong>Navn</strong> — eksakt, case-insensitiv sammenligning mot entitetsnavn</li>
          <li><strong>E-postdomene</strong> — treff på domene i e-postadresser (f.eks. rosneft.ru)</li>
          <li><strong>Land (ISO-2)</strong> — treff på destinasjonsland eller entitetens land</li>
          <li><strong>Regex</strong> — regulært uttrykk kjøres mot navn, e-post og landkoder</li>
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
            Oppføringer ({total} totalt)
          </p>
          <label className="flex items-center gap-1.5 text-xs text-xlent-muted cursor-pointer">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
              className="rounded border-gray-300"
            />
            Vis inaktive
          </label>
        </div>

        {isLoading && <p className="py-4 text-sm text-xlent-muted">Laster …</p>}
        {error && <p className="py-4 text-sm text-red-600">Kunne ikke laste sperrelisten.</p>}

        {!isLoading && entries.length === 0 && (
          <div className="rounded-lg border border-dashed border-gray-200 py-12 text-center">
            <p className="text-sm text-xlent-muted">
              {showInactive
                ? "Ingen oppføringer funnet."
                : "Ingen aktive oppføringer. Legg til for å starte."}
            </p>
          </div>
        )}

        {entries.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-xlent-muted bg-gray-50">
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Verdi</th>
                  <th className="px-3 py-2">Alvorlighet</th>
                  <th className="px-3 py-2">Årsak</th>
                  <th className="px-3 py-2">Lagt til av</th>
                  <th className="px-3 py-2">Dato</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2 text-right">Handlinger</th>
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
