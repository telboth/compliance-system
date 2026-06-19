import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import clsx from "clsx";

import { getInvoiceFileUrl } from "@/api/invoices";

const PREVIEWABLE_IMAGE_EXTENSIONS = new Set(["png", "jpg", "jpeg", "gif"]);

function extensionFromFilename(filename: string | null | undefined): string {
  return filename?.split(".").pop()?.toLowerCase() ?? "";
}

function InvoiceFileModal({
  invoiceId,
  filename,
  onClose,
}: {
  invoiceId: string;
  filename: string | null | undefined;
  onClose: () => void;
}) {
  const { t } = useTranslation("invoices");
  const fileUrl = getInvoiceFileUrl(invoiceId);
  const ext = extensionFromFilename(filename);
  const title = filename ?? invoiceId;

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={t("file_preview.title")}
      onMouseDown={onClose}
    >
      <div
        className="flex h-[88vh] w-full max-w-6xl flex-col overflow-hidden rounded-lg bg-white shadow-xl"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-gray-200 px-4 py-3">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-xlent-ink">{title}</h2>
            <p className="text-xs text-xlent-muted">{t("file_preview.subtitle")}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <a
              href={fileUrl}
              target="_blank"
              rel="noreferrer"
              className="rounded border border-gray-300 px-3 py-1.5 text-xs font-medium text-xlent-ink hover:bg-gray-50"
            >
              {t("file_preview.open_new_tab")}
            </a>
            <a
              href={fileUrl}
              download={filename ?? "invoice"}
              className="rounded border border-gray-300 px-3 py-1.5 text-xs font-medium text-xlent-ink hover:bg-gray-50"
            >
              {t("file_preview.download")}
            </a>
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-gray-300 px-3 py-1.5 text-xs font-medium text-xlent-ink hover:bg-gray-50"
            >
              {t("file_preview.close")}
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 bg-gray-100">
          {ext === "pdf" ? (
            <iframe
              src={fileUrl}
              className="h-full w-full border-0 bg-white"
              title={t("file_preview.pdf_title")}
            />
          ) : PREVIEWABLE_IMAGE_EXTENSIONS.has(ext) ? (
            <div className="flex h-full items-start justify-center overflow-auto p-4">
              <img src={fileUrl} alt={title} className="max-h-full max-w-full object-contain" />
            </div>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
              <p className="text-sm text-xlent-muted">
                {t("file_preview.preview_unavailable")}{" "}
                <span className="font-medium uppercase">{ext || t("file_preview.default_filetype")}</span>.
              </p>
              <a
                href={fileUrl}
                download={filename ?? "invoice"}
                className="rounded bg-xlent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-xlent-primary/90"
              >
                {t("file_preview.download")}
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function InvoiceFilePreviewLink({
  invoiceId,
  filename,
  invoiceNumber,
  className,
  showDetailsLink = true,
}: {
  invoiceId: string;
  filename: string | null | undefined;
  invoiceNumber?: string | null;
  className?: string;
  showDetailsLink?: boolean;
}) {
  const { t } = useTranslation("invoices");
  const [open, setOpen] = useState(false);
  const label = filename ?? invoiceNumber ?? invoiceId.slice(0, 8);
  const title = filename ?? invoiceNumber ?? invoiceId;

  return (
    <span className="inline-flex min-w-0 max-w-full items-center gap-2">
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={clsx(
          "min-w-0 truncate text-left text-xlent-primary hover:underline",
          className,
        )}
        title={title}
      >
        {label}
      </button>
      {showDetailsLink && (
        <Link
          to={`/invoices/${invoiceId}`}
          className="shrink-0 rounded border border-gray-200 px-1.5 py-0.5 text-[11px] font-medium text-xlent-muted hover:bg-gray-50 hover:text-xlent-ink"
          title={t("file_preview.open_details")}
        >
          {t("file_preview.details_short")}
        </Link>
      )}
      {open && (
        <InvoiceFileModal
          invoiceId={invoiceId}
          filename={filename}
          onClose={() => setOpen(false)}
        />
      )}
    </span>
  );
}
