/**
 * Agreements — rammeavtale-administrasjon og sjekkresultater.
 *
 * Viser alle lastede rammeavtaler, LLM-ekstraherte vilkår og resultater
 * av invoice-sjekker mot avtalene. Støtter opplasting av nye PDF-avtaler.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/auth/AuthContext";
import {
  listAgreements,
  createAgreement,
} from "@/api/agreements";
import type { Agreement } from "@/api/agreements";

// ── Hjelpere ──────────────────────────────────────────────────────────────────

function formatDate(dateStr: string | null, locale: string): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function TermChip({ label, value }: { label: string; value: unknown }) {
  if (value === null || value === undefined) return null;
  const display = Array.isArray(value) ? value.join(", ") : String(value);
  return (
    <div className="flex gap-1 text-xs">
      <span className="font-semibold text-xlent-muted">{label}:</span>
      <span className="text-xlent-ink">{display}</span>
    </div>
  );
}

// ── Avtale-kort ────────────────────────────────────────────────────────────────

function AgreementCard({ agreement }: { agreement: Agreement }) {
  const [expanded, setExpanded] = useState(false);
  const { t, i18n } = useTranslation("pages");
  const terms = agreement.extracted_terms;
  const isExpired =
    agreement.valid_to !== null && new Date(agreement.valid_to) < new Date();

  return (
    <div
      className={clsx(
        "rounded-lg border p-4",
        isExpired
          ? "border-orange-100 bg-orange-50"
          : agreement.is_active
            ? "border-gray-200 bg-white"
            : "border-gray-100 bg-gray-50 opacity-70",
      )}
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-xlent-ink">{agreement.name}</span>
            {agreement.reference && (
              <span className="text-xs text-xlent-muted">({agreement.reference})</span>
            )}
            {isExpired && (
              <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-800">
                {t("agreements.card.expired")}
              </span>
            )}
            {!agreement.is_active && !isExpired && (
              <span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs text-gray-500">
                {t("agreements.card.inactive")}
              </span>
            )}
          </div>

          {agreement.description && (
            <p className="mt-0.5 text-sm text-xlent-muted">{agreement.description}</p>
          )}

          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-xlent-muted">
            <span>{t("agreements.card.valid", { from: formatDate(agreement.valid_from, i18n.language === "en" ? "en-GB" : "nb-NO"), to: formatDate(agreement.valid_to, i18n.language === "en" ? "en-GB" : "nb-NO") })}</span>
            {agreement.original_filename && (
              <span>📄 {agreement.original_filename}</span>
            )}
            {agreement.extraction_model && (
              <span className="rounded bg-gray-100 px-1">
                {t("agreements.card.extracted_with", { model: agreement.extraction_model })}
              </span>
            )}
          </div>
        </div>

        <button
          onClick={() => setExpanded((e) => !e)}
          className="shrink-0 rounded border border-gray-200 px-2 py-1 text-xs text-xlent-muted hover:bg-gray-50"
        >
          {expanded ? t("agreements.card.collapse") : t("agreements.card.expand")}
        </button>
      </div>

      {expanded && terms && (
        <div className="mt-4 rounded-lg bg-gray-50 p-3">
          <p className="mb-2 text-xs font-semibold text-xlent-muted">{t("agreements.card.terms_title")}</p>
          <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
            <TermChip label={t("agreements.card.term_allowed_countries")} value={terms.allowed_countries} />
            <TermChip label={t("agreements.card.term_blocked_countries")} value={terms.blocked_countries} />
            <TermChip label={t("agreements.card.term_hs_codes")} value={terms.allowed_hs_codes} />
            <TermChip label={t("agreements.card.term_eccn")} value={terms.allowed_eccn} />
            <TermChip label={t("agreements.card.term_max_unit")} value={terms.max_unit_price} />
            <TermChip label={t("agreements.card.term_max_total")} value={terms.max_total_value} />
            <TermChip label={t("agreements.card.term_currency")} value={terms.currency} />
            <TermChip label={t("agreements.card.term_incoterms")} value={terms.allowed_incoterms} />
            {Boolean(terms.customer_names) && (
              <TermChip label={t("agreements.card.term_customers")} value={terms.customer_names} />
            )}
          </div>
          {Boolean(terms.notes) && (
            <p className="mt-2 text-xs text-xlent-muted">{String(terms.notes)}</p>
          )}
          {Boolean(terms.error) && (
            <p className="mt-2 text-xs text-traffic-red">{t("agreements.card.extraction_error", { error: String(terms.error) })}</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Opplastingsskjema ─────────────────────────────────────────────────────────

interface UploadFormProps {
  onClose: () => void;
}

function UploadForm({ onClose }: UploadFormProps) {
  const { t } = useTranslation("pages");
  const [name, setName] = useState("");
  const [reference, setReference] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: (fd: FormData) => createAgreement(fd),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agreements"] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    const fd = new FormData();
    fd.append("name", name);
    if (reference) fd.append("reference", reference);
    if (description) fd.append("description", description);
    if (file) fd.append("file", file);
    mutation.mutate(fd);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-xlent-ink">{t("agreements.upload.title")}</h2>
          <button onClick={onClose} className="text-xlent-muted hover:text-xlent-ink">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-semibold text-xlent-muted">{t("agreements.upload.name_label")}</label>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="f.eks. EuroTech Rammeavtale 2025"
              className="w-full rounded border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-xlent-primary/30"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-xlent-muted">{t("agreements.upload.reference_label")}</label>
            <input
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              placeholder="f.eks. RA-2025-047"
              className="w-full rounded border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-xlent-primary/30"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-xlent-muted">{t("agreements.upload.description_label")}</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full rounded border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-xlent-primary/30"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-xlent-muted">
              {t("agreements.upload.file_label")}
            </label>
            <input
              type="file"
              accept=".pdf"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="w-full text-sm text-xlent-muted"
            />
          </div>

          {mutation.isError && (
            <p className="text-sm text-traffic-red">
              {t("agreements.upload.error_prefix")}{String((mutation.error as Error)?.message ?? mutation.error)}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-gray-200 px-4 py-2 text-sm text-xlent-muted hover:bg-gray-50"
            >
              {t("agreements.upload.cancel")}
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="rounded bg-xlent-primary px-4 py-2 text-sm font-medium text-white hover:bg-xlent-primary/90 disabled:opacity-50"
            >
              {mutation.isPending ? t("agreements.upload.uploading") : t("agreements.upload.submit")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Hovedelement ──────────────────────────────────────────────────────────────

export function AgreementsPage() {
  const { t } = useTranslation("pages");
  const { can } = useAuth();
  const canEdit = can("agreements:edit");

  const [showForm, setShowForm] = useState(false);

  const { data: agreements, isLoading, error } = useQuery({
    queryKey: ["agreements"],
    queryFn: listAgreements,
    staleTime: 30_000,
  });

  const active = agreements?.filter((a) => a.is_active) ?? [];
  const inactive = agreements?.filter((a) => !a.is_active) ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-xlent-ink">{t("agreements.title")}</h1>
          <p className="mt-1 text-sm text-xlent-muted">
            {t("agreements.subtitle")}
          </p>
        </div>
        <button
          onClick={canEdit ? () => setShowForm(true) : undefined}
          disabled={!canEdit}
          title={!canEdit ? t("agreements.no_access_tooltip") : undefined}
          className={clsx(
            "shrink-0 rounded-lg px-4 py-2 text-sm font-medium",
            canEdit
              ? "bg-xlent-primary text-white hover:bg-xlent-primary/90"
              : "cursor-not-allowed bg-gray-100 text-gray-400",
          )}
        >
          {t("agreements.new_button")}
        </button>
      </div>

      {isLoading && <p className="py-8 text-center text-sm text-xlent-muted">{t("agreements.loading")}</p>}
      {error && <p className="py-4 text-sm text-traffic-red">{t("agreements.error")}</p>}

      {agreements && agreements.length === 0 && (
        <div className="rounded-lg border border-dashed border-gray-200 py-16 text-center">
          <p className="text-sm text-xlent-muted">{t("agreements.empty")}</p>
          {canEdit && (
            <button
              onClick={() => setShowForm(true)}
              className="mt-3 rounded-lg bg-xlent-primary px-4 py-2 text-sm font-medium text-white hover:bg-xlent-primary/90"
            >
              {t("agreements.empty_button")}
            </button>
          )}
        </div>
      )}

      {active.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
            {t("agreements.active", { count: active.length })}
          </p>
          {active.map((ag) => (
            <AgreementCard key={ag.id} agreement={ag} />
          ))}
        </div>
      )}

      {inactive.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
            {t("agreements.inactive", { count: inactive.length })}
          </p>
          {inactive.map((ag) => (
            <AgreementCard key={ag.id} agreement={ag} />
          ))}
        </div>
      )}

      {showForm && <UploadForm onClose={() => setShowForm(false)} />}
    </div>
  );
}
