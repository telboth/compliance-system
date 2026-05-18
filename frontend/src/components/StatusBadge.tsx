import { useTranslation } from "react-i18next";
import clsx from "clsx";

import type { ComplianceScore, InvoiceStatus } from "@/api/types";

interface StatusBadgeProps {
  status: InvoiceStatus;
  score?: ComplianceScore | null;
}

export function StatusBadge({ status, score }: StatusBadgeProps) {
  const { t } = useTranslation();

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

  // t("status.uploaded") osv. — faller tilbake til nøkkelen dersom oversettelse mangler
  const label = t(`status.${status}`, { defaultValue: status });

  return (
    <span className={className}>
      {isNotInvoice && <span aria-hidden>⚠️</span>}
      {isApproved && <span aria-hidden>✓</span>}
      {isBlocked && <span aria-hidden>🔒</span>}
      {label}
    </span>
  );
}
