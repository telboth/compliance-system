import clsx from "clsx";

import type { ComplianceScore, InvoiceStatus } from "@/api/types";

interface StatusBadgeProps {
  status: InvoiceStatus;
  score?: ComplianceScore | null;
}

const STATUS_LABEL: Record<InvoiceStatus, string> = {
  uploaded: "Lastet opp",
  parsing: "Parser",
  parsed: "Parset",
  parsing_failed: "Parsing feilet",
  not_invoice: "Ikke faktura",
  extracting: "Ekstraherer",
  extraction_failed: "Ekstraksjon feilet",
  extracted: "Ekstrahert",
  screening: "Screening",
  screening_failed: "Screening feilet",
  screened: "Screenet",
  reviewed: "Reviewert",
  approved: "Godkjent",
  blocked: "Blokkert",
};

export function StatusBadge({ status, score }: StatusBadgeProps) {
  const isFailed =
    status === "parsing_failed" ||
    status === "extraction_failed" ||
    status === "screening_failed";

  const isNotInvoice = status === "not_invoice";
  const isApproved = status === "approved";
  const isBlocked = status === "blocked";

  const className = clsx(
    "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
    isNotInvoice
      ? "bg-orange-100 text-orange-700"
      : isApproved
        ? "bg-green-100 text-green-700"
        : isBlocked
          ? "bg-red-100 text-traffic-red"
          : isFailed
            ? "bg-red-100 text-traffic-red"
            : score === "green"
              ? "bg-green-100 text-traffic-green"
              : score === "yellow"
                ? "bg-yellow-100 text-traffic-yellow"
                : score === "red"
                  ? "bg-red-100 text-traffic-red"
                  : "bg-gray-100 text-xlent-muted",
  );

  return (
    <span className={className}>
      {isNotInvoice && <span aria-hidden>⚠️</span>}
      {isApproved && <span aria-hidden>✓</span>}
      {isBlocked && <span aria-hidden>🔒</span>}
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}
