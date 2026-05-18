/**
 * Rules — YAML-regelmotor-administrasjon.
 *
 * Viser alle compliance-regler, lar brukeren opprette og redigere regler
 * i YAML-format, og tilbyr en inline test-modus der regelen kjøres mot
 * et oppgitt sett med felt uten å lagre.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useAuth } from "@/auth/AuthContext";
import { useTranslation } from "react-i18next";
import {
  listRules,
  createRule,
  updateRule,
  toggleRule,
  testRule,
  rerunRules,
} from "@/api/rules";
import type { Rule, RerunResponse } from "@/api/rules";

// ── Hjelpere ──────────────────────────────────────────────────────────────────

const SEVERITY_COLORS: Record<string, string> = {
  green: "bg-green-100 text-green-800 border-green-200",
  yellow: "bg-yellow-100 text-yellow-800 border-yellow-200",
  red: "bg-red-100 text-red-800 border-red-200",
};

const DEFAULT_YAML = `name: Min nye regel
description: Beskriv hva regelen sjekker
severity: yellow   # green | yellow | red
conditions:
  operator: OR
  rules:
    - field: destination_country
      op: in
      value: [RU, BY, KP, IR]
    - field: entities.email
      op: regex
      value: "rosneft|sanctionbuster"
`;

// ── Regel-rad ─────────────────────────────────────────────────────────────────

function RuleRow({
  rule,
  onEdit,
  onToggle,
  canEdit,
}: {
  rule: Rule;
  onEdit: (rule: Rule) => void;
  onToggle: (rule: Rule) => void;
  canEdit: boolean;
}) {
  const { t } = useTranslation("rules");

  return (
    <div
      className={clsx(
        "flex flex-col gap-2 rounded-lg border p-4 sm:flex-row sm:items-start",
        rule.is_active ? "border-gray-200 bg-white" : "border-gray-100 bg-gray-50 opacity-60",
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-xlent-ink">{rule.name}</span>
          <span
            className={clsx(
              "rounded-full border px-2 py-0.5 text-xs font-medium",
              SEVERITY_COLORS[rule.severity] ?? "bg-gray-100 text-gray-700",
            )}
          >
            {rule.severity}
          </span>
          <span className="text-xs text-xlent-muted">v{rule.active_version}</span>
          {!rule.is_active && (
            <span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs text-gray-500">
              {t("rules.row.inactive_badge")}
            </span>
          )}
        </div>
        {rule.description && (
          <p className="mt-0.5 text-sm text-xlent-muted">{rule.description}</p>
        )}
      </div>
      <div className="flex shrink-0 gap-2">
        <button
          onClick={() => canEdit && onToggle(rule)}
          disabled={!canEdit}
          title={!canEdit ? t("rules.row.no_access") : undefined}
          className={clsx(
            "rounded border px-2 py-1 text-xs",
            canEdit
              ? "border-gray-200 text-xlent-muted hover:bg-gray-50"
              : "cursor-not-allowed border-gray-100 text-gray-300",
          )}
        >
          {rule.is_active ? t("rules.row.deactivate") : t("rules.row.activate")}
        </button>
        <button
          onClick={() => canEdit && onEdit(rule)}
          disabled={!canEdit}
          title={!canEdit ? t("rules.row.no_access") : undefined}
          className={clsx(
            "rounded border px-2 py-1 text-xs",
            canEdit
              ? "border-xlent-primary/30 text-xlent-primary hover:bg-xlent-primary/5"
              : "cursor-not-allowed border-gray-100 text-gray-300",
          )}
        >
          {t("rules.row.edit")}
        </button>
      </div>
    </div>
  );
}

// ── Regelrediger ──────────────────────────────────────────────────────────────

interface EditorProps {
  rule: Rule | null;  // null = ny regel
  onClose: () => void;
  onSaved: () => void;
}

function RuleEditor({ rule, onClose, onSaved }: EditorProps) {
  const { t } = useTranslation("rules");
  const isNew = rule === null;
  const [yaml, setYaml] = useState(
    isNew ? DEFAULT_YAML : (rule.versions.find((v) => v.version === rule.active_version)?.rule_yaml ?? DEFAULT_YAML),
  );
  const [comment, setComment] = useState("");
  const [testResult, setTestResult] = useState<{ triggered: boolean; error: string | null } | null>(null);
  const [testContext, setTestContext] = useState(
    JSON.stringify({ destination_country: "RU", entities: [{ email: "test@rosneft.com" }] }, null, 2),
  );
  const [testError, setTestError] = useState<string | null>(null);

  const qc = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (body: Parameters<typeof createRule>[0]) => createRule(body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rules"] }); onSaved(); },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof updateRule>[1] }) =>
      updateRule(id, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rules"] }); onSaved(); },
  });

  const handleSave = () => {
    if (isNew) {
      createMutation.mutate({ name: "Ny regel", rule_yaml: yaml, comment });
    } else {
      updateMutation.mutate({ id: rule.id, body: { rule_yaml: yaml, comment } });
    }
  };

  const handleTest = async () => {
    setTestResult(null);
    setTestError(null);
    try {
      const ctx = JSON.parse(testContext);
      const res = await testRule({ rule_yaml: yaml, context: ctx });
      setTestResult(res);
    } catch (e) {
      setTestError(String(e));
    }
  };

  const isSaving = createMutation.isPending || updateMutation.isPending;
  const saveError = createMutation.error || updateMutation.error;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="flex w-full max-w-3xl flex-col gap-4 rounded-xl bg-white p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-xlent-ink">
            {isNew ? t("rules.editor.new_title") : t("rules.editor.edit_title", { name: rule.name })}
          </h2>
          <button onClick={onClose} className="text-xlent-muted hover:text-xlent-ink">✕</button>
        </div>

        {/* YAML-editor */}
        <div>
          <label className="mb-1 block text-xs font-semibold text-xlent-muted">{t("rules.editor.yaml_label")}</label>
          <textarea
            value={yaml}
            onChange={(e) => setYaml(e.target.value)}
            rows={16}
            className="w-full rounded border border-gray-200 bg-gray-50 p-3 font-mono text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-xlent-primary/30"
            spellCheck={false}
          />
        </div>

        {/* Endringskommentar */}
        <div>
          <label className="mb-1 block text-xs font-semibold text-xlent-muted">{t("rules.editor.comment_label")}</label>
          <input
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder={t("rules.editor.comment_placeholder")}
            className="w-full rounded border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-xlent-primary/30"
          />
        </div>

        {/* Test-seksjon */}
        <div className="rounded-lg border border-blue-100 bg-blue-50 p-4">
          <p className="mb-2 text-xs font-semibold text-blue-800">
            {t("rules.editor.test_title")}
          </p>
          <label className="mb-1 block text-xs text-blue-700">{t("rules.editor.test_context_label")}</label>
          <textarea
            value={testContext}
            onChange={(e) => setTestContext(e.target.value)}
            rows={5}
            className="w-full rounded border border-blue-200 bg-white p-2 font-mono text-xs focus:outline-none"
          />
          <button
            onClick={handleTest}
            className="mt-2 rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700"
          >
            {t("rules.editor.test_run")}
          </button>
          {testError && <p className="mt-2 text-xs text-red-600">{testError}</p>}
          {testResult && (
            <div
              className={clsx(
                "mt-2 rounded border px-3 py-2 text-xs font-medium",
                testResult.triggered
                  ? "border-orange-200 bg-orange-50 text-orange-800"
                  : "border-green-200 bg-green-50 text-green-800",
              )}
            >
              {testResult.triggered
                ? t("rules.editor.test_triggered")
                : t("rules.editor.test_not_triggered")}
              {testResult.error && <p className="mt-1 text-red-600">{testResult.error}</p>}
            </div>
          )}
        </div>

        {saveError && (
          <p className="text-sm text-traffic-red">
            {t("rules.editor.error_prefix")}{String((saveError as Error)?.message ?? saveError)}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded border border-gray-200 px-4 py-2 text-sm text-xlent-muted hover:bg-gray-50"
          >
            {t("rules.editor.cancel")}
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="rounded bg-xlent-primary px-4 py-2 text-sm font-medium text-white hover:bg-xlent-primary/90 disabled:opacity-50"
          >
            {isSaving ? t("rules.editor.saving") : t("rules.editor.save")}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Hovedelement ──────────────────────────────────────────────────────────────

export function RulesPage() {
  const { t } = useTranslation("rules");
  const { can } = useAuth();
  const canEdit = can("rules:edit");

  const [editingRule, setEditingRule] = useState<Rule | null | "new">(undefined as unknown as Rule | null | "new");
  const [showEditor, setShowEditor] = useState(false);
  const [rerunResult, setRerunResult] = useState<RerunResponse | null>(null);
  const [rerunBusy, setRerunBusy] = useState(false);
  const [rerunError, setRerunError] = useState<string | null>(null);

  const { data: rules, isLoading, error } = useQuery({
    queryKey: ["rules"],
    queryFn: listRules,
    staleTime: 30_000,
  });

  const qc = useQueryClient();

  const toggleMutation = useMutation({
    mutationFn: (id: string) => toggleRule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });

  const handleRerun = async () => {
    if (!window.confirm(t("rules.rerun_confirm"))) return;
    setRerunBusy(true);
    setRerunResult(null);
    setRerunError(null);
    try {
      const res = await rerunRules(500);
      setRerunResult(res);
    } catch {
      setRerunError(t("rules.rerun_error"));
    } finally {
      setRerunBusy(false);
    }
  };

  const openNew = () => {
    setEditingRule(null);
    setShowEditor(true);
  };

  const openEdit = (rule: Rule) => {
    setEditingRule(rule);
    setShowEditor(true);
  };

  const handleToggle = (rule: Rule) => {
    toggleMutation.mutate(rule.id);
  };

  const closeEditor = () => setShowEditor(false);
  const onSaved = () => setShowEditor(false);

  const activeRules = rules?.filter((r) => r.is_active) ?? [];
  const inactiveRules = rules?.filter((r) => !r.is_active) ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-xlent-ink">{t("rules.title")}</h1>
          <p className="mt-1 text-sm text-xlent-muted">
            {t("rules.subtitle")}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          {canEdit && (
            <button
              onClick={handleRerun}
              disabled={rerunBusy}
              title="Re-evaluer alle aktive regler mot eksisterende fakturaer"
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-xlent-muted hover:bg-gray-50 disabled:opacity-50"
            >
              {rerunBusy ? t("rules.rerun_running") : t("rules.rerun_button")}
            </button>
          )}
          <button
            onClick={canEdit ? openNew : undefined}
            disabled={!canEdit}
            title={!canEdit ? t("rules.no_access_create") : undefined}
            className={clsx(
              "rounded-lg px-4 py-2 text-sm font-medium",
              canEdit
                ? "bg-xlent-primary text-white hover:bg-xlent-primary/90"
                : "cursor-not-allowed bg-gray-100 text-gray-400",
            )}
          >
            {t("rules.new_button")}
          </button>
        </div>
      </div>

      {/* Re-evaluer resultat */}
      {rerunError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {rerunError}
        </div>
      )}
      {rerunResult && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          <p className="font-medium">{t("rules.rerun_success")}</p>
          <p className="mt-1 text-xs">
            {t("rules.rerun_detail", { evaluated: rerunResult.evaluated, changed: rerunResult.score_changed })}
          </p>
          {rerunResult.details.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs text-green-700">
              {rerunResult.details.slice(0, 10).map((d) => (
                <li key={d.invoice_id}>
                  {d.filename ?? d.invoice_id.slice(0, 8)}: {d.old_score} → {d.new_score}
                </li>
              ))}
              {rerunResult.details.length > 10 && (
                <li>{t("rules.rerun_more", { count: rerunResult.details.length - 10 })}</li>
              )}
            </ul>
          )}
        </div>
      )}

      {/* Info-boks */}
      <div className="rounded-lg border border-gray-100 bg-gray-50 p-4 text-xs text-xlent-muted">
        <p className="font-semibold">{t("rules.operators_title")}</p>
        <p className="mt-1">
          <code className="rounded bg-white px-1">eq, neq, in, not_in, contains, not_contains, regex, gt, gte, lt, lte, exists</code>
        </p>
        <p className="mt-1">
          <span className="font-semibold">{t("rules.fields_label")}</span>{" "}
          <code className="rounded bg-white px-1">destination_country, compliance_score, total_amount, currency, incoterms</code>
          {" | "}
          <code className="rounded bg-white px-1">entities.name, entities.country, entities.email, entities.role</code>
          {" | "}
          <code className="rounded bg-white px-1">lines.hs_code, lines.eccn, lines.description</code>
        </p>
      </div>

      {isLoading && <p className="py-8 text-center text-sm text-xlent-muted">{t("rules.loading")}</p>}
      {error && <p className="py-4 text-sm text-traffic-red">{t("rules.error")}</p>}

      {rules && rules.length === 0 && (
        <div className="rounded-lg border border-dashed border-gray-200 py-16 text-center">
          <p className="text-sm text-xlent-muted">{t("rules.empty")}</p>
          {canEdit && (
            <button
              onClick={openNew}
              className="mt-3 rounded-lg bg-xlent-primary px-4 py-2 text-sm font-medium text-white hover:bg-xlent-primary/90"
            >
              {t("rules.empty_button")}
            </button>
          )}
        </div>
      )}

      {activeRules.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
            {t("rules.active", { count: activeRules.length })}
          </p>
          {activeRules.map((rule) => (
            <RuleRow key={rule.id} rule={rule} onEdit={openEdit} onToggle={handleToggle} canEdit={canEdit} />
          ))}
        </div>
      )}

      {inactiveRules.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-xlent-muted">
            {t("rules.inactive", { count: inactiveRules.length })}
          </p>
          {inactiveRules.map((rule) => (
            <RuleRow key={rule.id} rule={rule} onEdit={openEdit} onToggle={handleToggle} canEdit={canEdit} />
          ))}
        </div>
      )}

      {showEditor && (
        <RuleEditor
          rule={editingRule === "new" ? null : editingRule}
          onClose={closeEditor}
          onSaved={onSaved}
        />
      )}
    </div>
  );
}
