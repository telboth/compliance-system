/**
 * ApiKeysModal
 *
 * Vises automatisk når ingen API-nøkler er konfigurert (begge mangler).
 * Viser en advarselsbanner når kun én nøkkel mangler (degradert modus).
 *
 * Admin:        kan taste inn og lagre nøkler direkte i dialogen.
 * Andre roller: ser informasjonsmelding og kan lukke for denne sesjonen.
 */

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useAuth } from "@/auth/AuthContext";
import { fetchKeysStatus, updateApiKeys } from "@/api/config";

const QUERY_KEY = ["api-key-status"] as const;

/** Henter nøkkelstatus med 30 sekunders cache. */
export function useApiKeyStatus() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: fetchKeysStatus,
    staleTime: 30_000,
    retry: 2,
  });
}

// ── Inline kode-chip ──────────────────────────────────────────────────────────

function Code({ children }: { children: string }) {
  return (
    <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-[11px] text-gray-700">
      {children}
    </code>
  );
}

// ── Advarselsbanner (én nøkkel mangler) ───────────────────────────────────────

function PartialWarningBanner({
  missingKey,
  onDismiss,
}: {
  missingKey: "anthropic" | "openai";
  onDismiss: () => void;
}) {
  const label =
    missingKey === "anthropic" ? "ANTHROPIC_API_KEY (Claude)" : "OPENAI_API_KEY (GPT-4o)";
  const fallback =
    missingKey === "anthropic" ? "OpenAI GPT-4o" : "Anthropic Claude";

  return (
    <div className="flex items-center gap-3 border-b border-amber-200 bg-amber-50 px-6 py-2">
      <span className="text-base">⚠️</span>
      <p className="flex-1 text-xs text-amber-800">
        <Code>{label}</Code> mangler — systemet bruker kun <strong>{fallback}</strong> som LLM. Ingen
        fallback tilgjengelig.
      </p>
      <button
        onClick={onDismiss}
        className="rounded px-2 py-0.5 text-xs text-amber-700 hover:bg-amber-100"
      >
        ✕
      </button>
    </div>
  );
}

// ── Blokkerende modal (begge nøkler mangler) ──────────────────────────────────

function BothMissingModal({ onDismiss }: { onDismiss: () => void }) {
  const { role } = useAuth();
  const isAdmin = role === "admin" || role === "c_level";
  const queryClient = useQueryClient();

  const [anthropicKey, setAnthropicKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const canSave = anthropicKey.trim().length > 0 || openaiKey.trim().length > 0;

  const handleSave = async () => {
    if (!canSave) return;
    setSaving(true);
    setSaveError(null);
    try {
      await updateApiKeys({
        anthropic_api_key: anthropicKey.trim() || undefined,
        openai_api_key: openaiKey.trim() || undefined,
      });
      setSaved(true);
      // Re-hent status — modalen lukkes automatisk når begge er satt
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    } catch {
      setSaveError("Lagring feilet. Kontroller nøklene og at du har admin-tilgang.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-lg rounded-xl border border-gray-200 bg-white shadow-2xl">

        {/* Header */}
        <div className="flex items-start gap-3 rounded-t-xl bg-amber-50 px-6 py-4">
          <span className="mt-0.5 text-2xl">🔑</span>
          <div>
            <p className="font-semibold text-amber-900">Ingen API-nøkler er konfigurert</p>
            <p className="mt-0.5 text-xs text-amber-700">
              AI-ekstraksjon og sanksjonsskjerming er ikke tilgjengelig før minst én LLM-nøkkel er satt.
            </p>
          </div>
        </div>

        {/* Body */}
        <div className="px-6 py-5">
          {!isAdmin ? (
            /* ── Ikke-admin: informasjonsvisning ─────────────────────────── */
            <div className="space-y-3">
              <p className="text-sm text-xlent-ink">
                Systemet mangler LLM-tilkobling. Nye fakturaer kan ikke prosesseres.
              </p>
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs text-gray-700">
                <p className="mb-1 font-medium">Hva administrator må gjøre:</p>
                <ol className="ml-3 list-decimal space-y-1">
                  <li>
                    Logg inn med <span className="font-medium">admin</span>-rolle
                  </li>
                  <li>Klikk «Konfigurer nøkler» i dialogen som vises</li>
                  <li>
                    Eller rediger <Code>.secrets</Code> manuelt med{" "}
                    <Code>ANTHROPIC_API_KEY</Code> eller <Code>OPENAI_API_KEY</Code>
                  </li>
                </ol>
              </div>
              <p className="text-xs text-xlent-muted">
                Du kan fortsatt bla gjennom eksisterende fakturaer og data.
              </p>
            </div>
          ) : (
            /* ── Admin: nøkkelinnlegging ─────────────────────────────────── */
            <div className="space-y-4">
              {saved ? (
                <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-800">
                  ✅ Nøkler lagret og aktivert — systemet er klart!
                </div>
              ) : (
                <>
                  <p className="text-sm text-xlent-ink">
                    Fyll inn minst én nøkkel. Nøklene lagres til{" "}
                    <Code>.secrets</Code> og aktiveres umiddelbart — ingen restart nødvendig.
                  </p>

                  <div className="space-y-3">
                    {/* Anthropic */}
                    <div>
                      <label className="mb-1 flex items-center gap-1.5 text-xs font-medium text-xlent-muted">
                        <Code>ANTHROPIC_API_KEY</Code>
                        <span className="text-gray-400">— Claude (anbefalt primær)</span>
                      </label>
                      <input
                        type="password"
                        value={anthropicKey}
                        onChange={(e) => setAnthropicKey(e.target.value)}
                        placeholder="sk-ant-api03-…"
                        autoComplete="off"
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm placeholder-gray-300 focus:border-xlent-primary focus:outline-none focus:ring-1 focus:ring-xlent-primary/30"
                      />
                    </div>

                    {/* OpenAI */}
                    <div>
                      <label className="mb-1 flex items-center gap-1.5 text-xs font-medium text-xlent-muted">
                        <Code>OPENAI_API_KEY</Code>
                        <span className="text-gray-400">— GPT-4o (fallback)</span>
                      </label>
                      <input
                        type="password"
                        value={openaiKey}
                        onChange={(e) => setOpenaiKey(e.target.value)}
                        placeholder="sk-proj-…"
                        autoComplete="off"
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm placeholder-gray-300 focus:border-xlent-primary focus:outline-none focus:ring-1 focus:ring-xlent-primary/30"
                      />
                    </div>
                  </div>

                  {saveError && (
                    <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
                      ⚠️ {saveError}
                    </p>
                  )}

                  <button
                    onClick={() => void handleSave()}
                    disabled={saving || !canSave}
                    className={clsx(
                      "w-full rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition-opacity",
                      "bg-xlent-primary",
                      saving || !canSave ? "cursor-not-allowed opacity-40" : "hover:opacity-90",
                    )}
                  >
                    {saving ? "Lagrer og aktiverer…" : "Lagre og aktiver"}
                  </button>
                </>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between rounded-b-xl border-t border-gray-100 bg-gray-50 px-6 py-3">
          <p className="text-xs text-xlent-muted">
            Nøklene forlater aldri serveren. Bare tilstedeværelse eksponeres via API.
          </p>
          <button
            onClick={onDismiss}
            className="text-xs text-gray-400 hover:text-gray-600 underline"
          >
            Fortsett uten AI
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Hoved-komponent ───────────────────────────────────────────────────────────

/**
 * Render dette én gang i AppShell — komponenten bestemmer selv hva som vises
 * basert på nøkkelstatus og om brukeren har lukket varselet.
 */
export function ApiKeysModal() {
  const { data: status, isLoading } = useApiKeyStatus();
  const [dismissedBoth, setDismissedBoth] = useState(false);
  const [dismissedPartial, setDismissedPartial] = useState(false);

  // Ikke vis noe mens status lastes (unngår flimmer)
  if (isLoading || !status) return null;

  const bothMissing = !status.anthropic && !status.openai;
  const partialMissing = !bothMissing && (!status.anthropic || !status.openai);
  const missingKey = !status.anthropic ? "anthropic" : "openai";

  if (bothMissing && !dismissedBoth) {
    return <BothMissingModal onDismiss={() => setDismissedBoth(true)} />;
  }

  if (partialMissing && !dismissedPartial) {
    return (
      <PartialWarningBanner
        missingKey={missingKey as "anthropic" | "openai"}
        onDismiss={() => setDismissedPartial(true)}
      />
    );
  }

  return null;
}
