/**
 * EditableField — klikk-for-å-redigere komponent.
 *
 * Viser verdien som tekst. Ved klikk bytter den til et input-felt.
 * Lagrer ved Enter eller blur; avbryter ved Escape.
 *
 * Brukes for inline-redigering av LLM-ekstraherte felt direkte i
 * invoice-detaljvisningen.
 */

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";

export interface EditableFieldOption {
  value: string;
  label: string;
}

interface EditableFieldProps {
  /** Nåværende verdi fra databasen. */
  value: string | null | undefined;

  /** Kalles med den nye verdien når brukeren bekrefter. Kast for å signalisere feil. */
  onSave: (newValue: string) => Promise<void>;

  /** Tekst som vises når value er tom. */
  placeholder?: string;

  /** Input-type. "select" bruker <select> med options-lista. */
  type?: "text" | "date" | "select";

  /** Brukes kun når type="select". */
  options?: EditableFieldOption[];

  /** Ekstra CSS-klasser på wrapper-elementet. */
  className?: string;

  /** Om feltet kan redigeres. Default true. */
  editable?: boolean;
}

export function EditableField({
  value,
  onSave,
  placeholder = "—",
  type = "text",
  options,
  className,
  editable = true,
}: EditableFieldProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement & HTMLSelectElement>(null);

  function startEdit() {
    if (!editable) return;
    setDraft(value ?? "");
    setEditing(true);
    setError(null);
  }

  async function save(valueOverride?: string) {
    // Tillat en eksplisitt verdi-override — nødvendig for select-elementer der
    // setDraft og save() kalles i samme event handler (state-oppdatering er async).
    const valueToSave = valueOverride !== undefined ? valueOverride : draft;
    // Ingen endring — bare lukk
    if (valueToSave === (value ?? "")) {
      setEditing(false);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSave(valueToSave);
      setEditing(false);
    } catch {
      setError("Lagring feilet");
    } finally {
      setSaving(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      void save();
    }
    if (e.key === "Escape") {
      setEditing(false);
    }
  }

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      if (type !== "select" && "select" in inputRef.current) {
        (inputRef.current as HTMLInputElement).select();
      }
    }
  }, [editing, type]);

  if (!editable) {
    return <span className={className}>{value || placeholder}</span>;
  }

  if (editing) {
    return (
      <span className={clsx("inline-flex items-center gap-1", className)}>
        {type === "select" && options ? (
          <select
            ref={inputRef as React.RefObject<HTMLSelectElement>}
            value={draft}
            onChange={(e) => {
              const newValue = e.target.value;
              setDraft(newValue);
              // Lagre umiddelbart — onBlur er upålitelig for native <select>:
              // brukeren klikker et valg og fokus forblir i elementet.
              void save(newValue);
            }}
            onBlur={() => void save()}
            onKeyDown={handleKeyDown}
            disabled={saving}
            className="rounded border border-xlent-primary/60 bg-white px-1.5 py-0.5 text-sm focus:outline-none focus:ring-1 focus:ring-xlent-primary"
          >
            <option value="">—</option>
            {options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        ) : (
          <input
            ref={inputRef as React.RefObject<HTMLInputElement>}
            type={type}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={() => void save()}
            onKeyDown={handleKeyDown}
            disabled={saving}
            className="min-w-0 rounded border border-xlent-primary/60 bg-white px-1.5 py-0.5 text-sm focus:outline-none focus:ring-1 focus:ring-xlent-primary disabled:opacity-60"
          />
        )}
        {saving && (
          <span className="h-3 w-3 animate-spin rounded-full border border-xlent-primary border-t-transparent" />
        )}
        {error && (
          <span className="text-xs text-traffic-red" title={error}>
            !
          </span>
        )}
      </span>
    );
  }

  const displayValue = value || null;

  return (
    <button
      onClick={startEdit}
      title="Klikk for å redigere"
      className={clsx(
        "group inline-flex items-center gap-1 text-left transition-colors hover:text-xlent-primary",
        className,
      )}
    >
      <span className={clsx(!displayValue && "text-xlent-muted/50 italic")}>
        {displayValue ?? placeholder}
      </span>
      {/* Blyant-ikon — kun synlig ved hover */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 16 16"
        fill="currentColor"
        className="hidden h-3 w-3 shrink-0 opacity-40 group-hover:block"
        aria-hidden
      >
        <path d="M13.488 2.513a1.75 1.75 0 0 0-2.475 0L3.76 9.768a2.75 2.75 0 0 0-.726 1.399l-.575 2.68a.25.25 0 0 0 .297.297l2.68-.575a2.75 2.75 0 0 0 1.4-.726l7.252-7.252a1.75 1.75 0 0 0 0-2.475l-.6-.603Z" />
      </svg>
    </button>
  );
}
