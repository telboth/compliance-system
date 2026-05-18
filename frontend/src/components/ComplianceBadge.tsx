/**
 * ComplianceBadge — samlet risikoindikator for en invoice.
 *
 * Kombinerer tre signaler:
 *  1. Sanksjonsscreening-resultat (compliance_score fra backend)
 *  2. Destinasjonslands risikotier (countryRisk.ts)
 *  3. Dual-use/ECCN-indikasjoner i LLM-analysen (invoice.comments)
 *
 * Verste-vinner-logikk:
 *  RED   = compliance_score=red  ELLER land er TIER 4
 *  ORANGE = compliance_score=yellow ELLER land er TIER 3 ELLER dual-use (uten lav-risiko NATO)
 *  YELLOW (dempet) = dual-use + NATO-destinasjon i TIER 1
 *  YELLOW = land er TIER 2
 *  GREEN  = alt klart (TIER 1 land + grønn screening + ingen dual-use)
 */

import clsx from "clsx";
import type { ComplianceScore, Invoice } from "@/api/types";
import { getCountryRisk, isNatoCountry, TIER_LABELS } from "@/data/countryRisk";

// ── Dual-use-deteksjon fra LLM-kommentarer ────────────────────────────────────

const DUAL_USE_PATTERNS = [
  /\bECCN\b/i,
  /\bdual[- ]use\b/i,
  /\beksportkontroll\b/i,
  /\blisens\b.*\bkrev/i,
  /\blicense\b.*\brequ/i,
  /\bcontrolled\b.*\btechnology\b/i,
  // ECCN-koder som ikke er EAR99 (f.eks. 7A001, 7A994, 9A004)
  /\b[0-9][A-E]\d{3}\b/,
];

function detectDualUse(comments: string | null | undefined): boolean {
  if (!comments) return false;
  return DUAL_USE_PATTERNS.some((p) => p.test(comments));
}

// ── Overordnet risikonivå ─────────────────────────────────────────────────────

export type OverallRisk = "green" | "yellow" | "orange" | "red";

export function computeOverallRisk(invoice: Partial<Invoice>): {
  risk: OverallRisk;
  reasons: string[];
} {
  const reasons: string[] = [];

  const score: ComplianceScore | null | undefined = invoice.compliance_score;
  const countryInfo = getCountryRisk(invoice.destination_country);
  const hasDualUse = detectDualUse(invoice.comments);
  const natoDestination = isNatoCountry(invoice.destination_country);

  // Tier 4-land eller bekreftet sanksjons-treff → RØD
  if (score === "red" || countryInfo.tier === 4) {
    if (score === "red") reasons.push("Bekreftet sanksjons-treff");
    if (countryInfo.tier === 4) {
      reasons.push(
        `Destinasjonsland (${invoice.destination_country}) er klassifisert som høy-risikoland`
      );
    }
    return { risk: "red", reasons };
  }

  // Sanksjons-gult eller Tier 3-land → ORANSJE
  if (score === "yellow" || countryInfo.tier === 3) {
    if (score === "yellow") reasons.push("Potensielt sanksjons-treff");
    if (countryInfo.tier === 3) {
      reasons.push(
        `Destinasjonsland (${invoice.destination_country}) er klassifisert som forhøyet risiko`
      );
    }
    if (hasDualUse) reasons.push("LLM-analyse indikerer dual-use / eksportkontroll-relevans");
    return { risk: "orange", reasons };
  }

  // Dual-use uten sanksjonssignal:
  // Lav-risiko NATO-destinasjon (tier 1) demper til GUL (moderat), ellers ORANSJE.
  if (hasDualUse) {
    reasons.push("LLM-analyse indikerer dual-use / eksportkontroll-relevans");
    if (natoDestination && countryInfo.tier === 1) {
      reasons.push(
        `Destinasjonsland (${invoice.destination_country}) er NATO-medlem og demper totalrisiko`
      );
      return { risk: "yellow", reasons };
    }
    return { risk: "orange", reasons };
  }

  // Tier 2-land → GUL
  if (countryInfo.tier === 2) {
    reasons.push(
      `Destinasjonsland (${invoice.destination_country ?? "ukjent"}) krever normal aktsomhet`
    );
    return { risk: "yellow", reasons };
  }

  // Alt klart → GRØNN
  if (score === "green") reasons.push("Godkjent sanksjonsscreening");
  if (countryInfo.tier === 1) {
    reasons.push(
      `Destinasjonsland (${invoice.destination_country}) er lav-risikoland`
    );
  }
  return { risk: "green", reasons };
}

// ── Visuelle definisjoner ─────────────────────────────────────────────────────

const RISK_CONFIG: Record<
  OverallRisk,
  { label: string; emoji: string; bg: string; border: string; text: string }
> = {
  green: {
    label: "Lav risiko",
    emoji: "😊",
    bg: "bg-green-50",
    border: "border-green-200",
    text: "text-green-800",
  },
  yellow: {
    label: "Normal aktsomhet",
    emoji: "🙂",
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    text: "text-yellow-800",
  },
  orange: {
    label: "Forhøyet risiko",
    emoji: "😐",
    bg: "bg-orange-50",
    border: "border-orange-200",
    text: "text-orange-800",
  },
  red: {
    label: "Høy risiko",
    emoji: "🚨",
    bg: "bg-red-50",
    border: "border-red-200",
    text: "text-red-800",
  },
};

// ── Kompakt badge (til header / list-visning) ─────────────────────────────────

interface ComplianceBadgeProps {
  invoice: Partial<Invoice>;
  showReasons?: boolean;
}

export function ComplianceBadge({ invoice, showReasons = true }: ComplianceBadgeProps) {
  const { risk, reasons } = computeOverallRisk(invoice);
  const cfg = RISK_CONFIG[risk];
  const countryInfo = getCountryRisk(invoice.destination_country);

  return (
    <div
      className={clsx(
        "rounded-lg border p-4",
        cfg.bg,
        cfg.border,
      )}
    >
      {/* Hoved-indikator */}
      <div className="flex items-center gap-3">
        <span className="text-3xl leading-none" role="img" aria-label={cfg.label}>
          {cfg.emoji}
        </span>
        <div>
          <div className={clsx("text-base font-semibold", cfg.text)}>{cfg.label}</div>
          <div className="text-xs text-xlent-muted">
            Samlet risikovurdering basert på screening, destinasjonsland og LLM-analyse
          </div>
        </div>
        {/* Landrisiko-chip */}
        {invoice.destination_country && (
          <div className="ml-auto flex flex-col items-end gap-1">
            <span className="font-mono text-sm font-medium text-xlent-ink uppercase">
              {invoice.destination_country}
            </span>
            <span
              className={clsx(
                "rounded-full px-2 py-0.5 text-xs font-medium",
                countryInfo.tier === 1
                  ? "bg-green-100 text-green-700"
                  : countryInfo.tier === 2
                    ? "bg-yellow-100 text-yellow-700"
                    : countryInfo.tier === 3
                      ? "bg-orange-100 text-orange-700"
                      : "bg-red-100 text-red-700",
              )}
            >
              {TIER_LABELS[countryInfo.tier]}
            </span>
          </div>
        )}
      </div>

      {/* Begrunnelse */}
      {showReasons && reasons.length > 0 && (
        <ul className="mt-3 space-y-1 border-t border-current/10 pt-3">
          {reasons.map((r, i) => (
            <li key={i} className={clsx("text-xs", cfg.text)}>
              <span className="mr-1.5">›</span>
              {r}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Liten inline-chip (f.eks. i tabeller). */
export function ComplianceChip({ invoice }: { invoice: Partial<Invoice> }) {
  const { risk } = computeOverallRisk(invoice);
  const cfg = RISK_CONFIG[risk];
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium border",
        cfg.bg,
        cfg.border,
        cfg.text,
      )}
    >
      <span>{cfg.emoji}</span>
      <span>{cfg.label}</span>
    </span>
  );
}
