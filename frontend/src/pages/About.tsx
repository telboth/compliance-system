/**
 * About — system documentation for XLENT Compliance.
 *
 * All text content (both nb and en) lives in aboutContent.ts.
 * The active language is read from i18next at render time and switches
 * live when the user toggles the language bar.
 */

import { useState } from "react";
import clsx from "clsx";
import { useTranslation } from "react-i18next";

import {
  ABOUT_CONTENT,
  type TabId,
  type AboutContent,
  type WorkflowStep,
} from "./aboutContent";

// ── Generic layout helpers ────────────────────────────────────────────────────

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-4 text-lg font-semibold text-xlent-ink">{children}</h2>
  );
}

function SectionText({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-4 max-w-3xl text-sm leading-relaxed text-xlent-ink">{children}</p>
  );
}

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx("rounded-lg border border-gray-200 bg-white p-5", className)}>
      {children}
    </div>
  );
}

/**
 * Renders a string, wrapping any occurrence of SCREENING_* env-var names in
 * a monospace code chip so they stand out in the threshold footnote.
 */
function renderWithCode(text: string) {
  const parts = text.split(/(SCREENING_\w+)/g);
  return parts.map((part, i) =>
    part.startsWith("SCREENING_") ? (
      <code key={i} className="rounded bg-gray-100 px-1 py-0.5 font-mono text-[11px]">
        {part}
      </code>
    ) : (
      part
    ),
  );
}

// ── OVERVIEW ──────────────────────────────────────────────────────────────────

function OverviewTab({ c }: { c: AboutContent }) {
  return (
    <div className="space-y-8">
      <div>
        <SectionTitle>{c.overviewTitle}</SectionTitle>
        {c.overviewParas.map((para, i) => (
          <SectionText key={i}>{para}</SectionText>
        ))}
      </div>

      <div>
        <SectionTitle>{c.featuresTitle}</SectionTitle>
        <div className="grid gap-4 sm:grid-cols-2">
          {c.features.map((f) => (
            <Card key={f.title} className="flex gap-3">
              <span className="mt-0.5 text-2xl leading-none">{f.icon}</span>
              <div>
                <p className="mb-1 text-sm font-semibold text-xlent-ink">{f.title}</p>
                <p className="text-sm leading-relaxed text-xlent-muted">{f.desc}</p>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── WORKFLOW ──────────────────────────────────────────────────────────────────

function WorkflowStepItem({
  s,
  isLast,
}: {
  s: WorkflowStep;
  isLast: boolean;
}) {
  const [open, setOpen] = useState(false);
  const detailLines = Array.isArray(s.detail) ? s.detail : [s.detail];

  return (
    <div className="flex gap-4">
      {/* Connector line */}
      <div className="flex flex-col items-center">
        <div
          className={clsx(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-base font-bold",
            s.color,
          )}
        >
          {s.step}
        </div>
        {!isLast && <div className="mt-1 w-px flex-1 bg-gray-200" />}
      </div>

      {/* Content */}
      <div className="mb-6 min-w-0 flex-1">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-start gap-2 text-left"
        >
          <span className="text-xl leading-none">{s.icon}</span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-xlent-ink">{s.title}</p>
            <p className="mt-0.5 text-sm leading-relaxed text-xlent-muted">{s.desc}</p>
          </div>
          <span className="mt-0.5 text-xs text-xlent-muted">{open ? "▲" : "▼"}</span>
        </button>

        {open && (
          <div className="mt-3 rounded border border-gray-100 bg-gray-50 p-3">
            {detailLines.map((line, i) => (
              <p key={i} className="text-xs leading-relaxed text-xlent-ink">
                {line}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function WorkflowTab({ c }: { c: AboutContent }) {
  return (
    <div className="space-y-6">
      <div>
        <SectionTitle>{c.workflowTitle}</SectionTitle>
        <SectionText>{c.workflowIntro}</SectionText>
      </div>
      <div className="max-w-2xl">
        {c.workflowSteps.map((s, i) => (
          <WorkflowStepItem
            key={s.step}
            s={s}
            isLast={i === c.workflowSteps.length - 1}
          />
        ))}
      </div>
    </div>
  );
}

// ── PAGES ─────────────────────────────────────────────────────────────────────

function PagesTab({ c }: { c: AboutContent }) {
  return (
    <div className="space-y-6">
      <div>
        <SectionTitle>{c.pagesTitle}</SectionTitle>
        <SectionText>{c.pagesIntro}</SectionText>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {c.pageDocs.map((p) => (
          <Card key={p.path}>
            <div className="mb-2 flex items-start gap-2">
              <span className="text-xl leading-none">{p.icon}</span>
              <div className="flex-1">
                <p className="text-sm font-semibold text-xlent-ink">{p.name}</p>
                <p className="text-xs text-xlent-muted">{p.path}</p>
              </div>
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600">
                {p.access}
              </span>
            </div>
            <p className="text-sm leading-relaxed text-xlent-muted">{p.desc}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}

// ── ROLES ─────────────────────────────────────────────────────────────────────

function RolesTab({ c }: { c: AboutContent }) {
  return (
    <div className="space-y-6">
      <div>
        <SectionTitle>{c.rolesTitle}</SectionTitle>
        <SectionText>{c.rolesIntro}</SectionText>
      </div>
      <div className="space-y-4">
        {c.roles.map((r) => (
          <Card key={r.name}>
            <div className="mb-3 flex items-center gap-2">
              <span
                className={clsx(
                  "rounded-full px-2.5 py-0.5 text-xs font-semibold",
                  r.colorClass,
                )}
              >
                {r.name}
              </span>
              <p className="text-sm text-xlent-muted">{r.desc}</p>
            </div>
            <ul className="grid gap-1 sm:grid-cols-2">
              {r.perms.map((p) => (
                <li key={p} className="flex items-start gap-1.5 text-xs text-xlent-ink">
                  <span className="mt-0.5 text-green-600">✓</span>
                  {p}
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </div>
  );
}

// ── TECHNICAL ─────────────────────────────────────────────────────────────────

function TechnicalTab({ c }: { c: AboutContent }) {
  const [tierH, examplesH, criterionH] = c.tierTableHeaders;
  const [threshH, valueH, consequenceH] = c.thresholdTableHeaders;

  return (
    <div className="space-y-8">
      {/* Tech stack */}
      <div>
        <SectionTitle>{c.techTitle}</SectionTitle>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {c.techStack.map((cat) => (
            <Card key={cat.category}>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-xlent-muted">
                {cat.category}
              </p>
              <ul className="space-y-2">
                {cat.items.map((item) => (
                  <li key={item.name}>
                    <p className="text-xs font-semibold text-xlent-ink">{item.name}</p>
                    <p className="text-xs text-xlent-muted">{item.desc}</p>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      </div>

      {/* Country risk tiers */}
      <div>
        <SectionTitle>{c.tierTitle}</SectionTitle>
        <SectionText>{c.tierIntro}</SectionText>
        <div className="max-w-2xl overflow-hidden rounded-lg border border-gray-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left">
                <th className="px-4 py-2 text-xs font-semibold text-xlent-muted">{tierH}</th>
                <th className="px-4 py-2 text-xs font-semibold text-xlent-muted">{examplesH}</th>
                <th className="px-4 py-2 text-xs font-semibold text-xlent-muted">{criterionH}</th>
              </tr>
            </thead>
            <tbody>
              {c.tiers.map((row, i) => (
                <tr
                  key={row.tier}
                  className={i < c.tiers.length - 1 ? "border-b border-gray-100" : ""}
                >
                  <td className="px-4 py-2">
                    <span
                      className={clsx(
                        "rounded-full px-2 py-0.5 text-xs font-semibold",
                        row.colorClass,
                      )}
                    >
                      {row.tier}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs text-xlent-ink">{row.examples}</td>
                  <td className="px-4 py-2 text-xs text-xlent-muted">{row.rule}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Screening confidence thresholds */}
      <div>
        <SectionTitle>{c.thresholdTitle}</SectionTitle>
        <div className="max-w-xl overflow-hidden rounded-lg border border-gray-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left">
                <th className="px-4 py-2 text-xs font-semibold text-xlent-muted">{threshH}</th>
                <th className="px-4 py-2 text-xs font-semibold text-xlent-muted">{valueH}</th>
                <th className="px-4 py-2 text-xs font-semibold text-xlent-muted">{consequenceH}</th>
              </tr>
            </thead>
            <tbody>
              {c.thresholds.map((row, i) => (
                <tr
                  key={row.label}
                  className={i < c.thresholds.length - 1 ? "border-b border-gray-100" : ""}
                >
                  <td className="px-4 py-2 text-xs font-medium text-xlent-ink">{row.label}</td>
                  <td className="px-4 py-2 text-xs text-xlent-ink">{row.value}</td>
                  <td className="px-4 py-2 text-xs text-xlent-muted">{row.consequence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-xlent-muted">
          {renderWithCode(c.thresholdNote)}
        </p>
      </div>
    </div>
  );
}

// ── COMPLIANCE / REGULATORY ───────────────────────────────────────────────────

function ComplianceTab({ c }: { c: AboutContent }) {
  return (
    <div className="space-y-8">
      <div>
        <SectionTitle>{c.complianceTitle}</SectionTitle>
        <SectionText>{c.complianceIntro}</SectionText>
      </div>

      <div className="space-y-6">
        {c.complianceSections.map((section) => (
          <Card key={section.title}>
            <div className="mb-4 flex items-center gap-3">
              <span className="text-2xl leading-none">{section.icon}</span>
              <div>
                <p className="text-sm font-semibold text-xlent-ink">{section.title}</p>
                <p className="text-xs text-xlent-muted">{section.subtitle}</p>
              </div>
            </div>
            <div className="space-y-3">
              {section.points.map((point) => (
                <div
                  key={point.label}
                  className="border-l-2 border-blue-200 pl-3"
                >
                  <p className="mb-0.5 text-xs font-semibold text-xlent-ink">
                    {point.label}
                  </p>
                  <p className="text-xs leading-relaxed text-xlent-muted">{point.desc}</p>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

// ── MAIN COMPONENT ────────────────────────────────────────────────────────────

export function AboutPage() {
  const { i18n } = useTranslation();

  // Map any Norwegian locale variant (nb, nb-NO, no) to "nb"; everything else → "en"
  const lang =
    i18n.language.startsWith("nb") || i18n.language.startsWith("no") ? "nb" : "en";
  const c = ABOUT_CONTENT[lang];

  const [activeTab, setActiveTab] = useState<TabId>("overview");

  return (
    <div className="mx-auto max-w-6xl p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-xlent-ink">XLENT Compliance</h1>
        <p className="mt-1 text-sm text-xlent-muted">{c.subtitle}</p>
      </div>

      {/* Tab bar — labels come from the content object, so they switch with language */}
      <div className="mb-6 border-b border-gray-200">
        <nav className="-mb-px flex flex-wrap gap-x-6">
          {c.tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                "border-b-2 pb-3 text-sm font-medium transition-colors",
                activeTab === tab.id
                  ? "border-xlent-primary text-xlent-primary"
                  : "border-transparent text-xlent-muted hover:text-xlent-ink",
              )}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "overview"   && <OverviewTab   c={c} />}
      {activeTab === "workflow"   && <WorkflowTab   c={c} />}
      {activeTab === "pages"      && <PagesTab      c={c} />}
      {activeTab === "roles"      && <RolesTab      c={c} />}
      {activeTab === "technical"  && <TechnicalTab  c={c} />}
      {activeTab === "compliance" && <ComplianceTab c={c} />}
    </div>
  );
}
