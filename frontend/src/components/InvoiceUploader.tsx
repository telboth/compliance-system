import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";

import { useUploadInvoice } from "@/hooks/useInvoices";
import { useCustomerList } from "@/hooks/useCustomers";
import type { InvoiceDirection } from "@/api/types";
import { useTranslation } from "react-i18next";

export function InvoiceUploader() {
  const [direction, setDirection] = useState<InvoiceDirection>("incoming");
  const [customerId, setCustomerId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [batchProgress, setBatchProgress] = useState<{
    current: number;
    total: number;
  } | null>(null);
  const upload = useUploadInvoice();
  const navigate = useNavigate();

  // Hent kunder for dropdown — maks 200 uten paginering
  const { data: customerData } = useCustomerList({ limit: 200 });
  const { t } = useTranslation("components");

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      setError(null);
      setWarnings([]);
      setBatchProgress(null);
      if (acceptedFiles.length === 0) return;

      const failures: string[] = [];
      const duplicateWarnings: string[] = [];
      let lastInvoiceId: string | null = null;

      for (let i = 0; i < acceptedFiles.length; i += 1) {
        const file = acceptedFiles[i];
        if (!file) continue;
        setBatchProgress({ current: i + 1, total: acceptedFiles.length });
        try {
          const result = await upload.mutateAsync({
            file,
            direction,
            customerId: customerId || null,
          });
          if (result.duplicate_detected) {
            duplicateWarnings.push(
              t("uploader.duplicate_reused", {
                filename: file.name,
                invoiceId: result.duplicate_of_invoice_id ?? result.invoice.id,
              }),
            );
          }
          lastInvoiceId = result.invoice.id;
        } catch (err) {
          const message =
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
            t("uploader.error");
          failures.push(`${file.name}: ${message}`);
        }
      }

      setBatchProgress(null);
      if (duplicateWarnings.length > 0) {
        setWarnings(duplicateWarnings);
      }
      if (failures.length > 0) {
        setError(failures.join(" | "));
      }

      if (lastInvoiceId) {
        if (acceptedFiles.length === 1) {
          navigate(`/invoices/${lastInvoiceId}`);
        } else {
          navigate("/");
        }
      }
    },
    [direction, customerId, navigate, upload, t],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "image/png": [".png"],
      "image/jpeg": [".jpg", ".jpeg"],
      "image/gif": [".gif"],
    },
    multiple: true,
    disabled: upload.isPending || batchProgress !== null,
  });

  const selectCls =
    "rounded border border-gray-300 bg-white px-2 py-1 text-sm disabled:opacity-60";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-4 text-sm">
        {/* Retning */}
        <div className="flex items-center gap-2">
          <label className="font-medium text-xlent-ink">{t("uploader.type_label")}</label>
          <select
            value={direction}
            onChange={(e) => setDirection(e.target.value as InvoiceDirection)}
            className={selectCls}
            disabled={upload.isPending || batchProgress !== null}
          >
            <option value="incoming">{t("uploader.direction_incoming")}</option>
            <option value="outgoing">{t("uploader.direction_outgoing")}</option>
          </select>
        </div>

        {/* Kunde */}
        {customerData && customerData.items.length > 0 && (
          <div className="flex items-center gap-2">
            <label className="font-medium text-xlent-ink">{t("uploader.customer_label")}</label>
            <select
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              className={selectCls}
              disabled={upload.isPending || batchProgress !== null}
            >
              <option value="">{t("uploader.customer_none")}</option>
              {customerData.items.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                  {c.country ? ` (${c.country})` : ""}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div
        {...getRootProps()}
        className={clsx(
          "flex h-40 cursor-pointer items-center justify-center rounded-lg border-2 border-dashed text-center transition-colors",
          isDragActive
            ? "border-xlent-accent bg-orange-50"
            : "border-gray-300 hover:border-xlent-primary",
          (upload.isPending || batchProgress !== null) && "cursor-not-allowed opacity-60",
        )}
      >
        <input {...getInputProps()} />
        {upload.isPending || batchProgress !== null ? (
          <div className="flex items-center gap-2">
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-xlent-primary border-t-transparent" />
            <p className="text-sm text-xlent-muted">
              {batchProgress
                ? t("uploader.loading_batch", {
                    current: batchProgress.current,
                    total: batchProgress.total,
                  })
                : t("uploader.loading")}
            </p>
          </div>
        ) : isDragActive ? (
          <p className="text-sm text-xlent-primary">{t("uploader.drop_active")}</p>
        ) : (
          <div>
            <p className="text-sm font-medium text-xlent-ink">
              {t("uploader.drop_hint")}
            </p>
            <p className="mt-1 text-xs text-xlent-muted">{t("uploader.size_hint")}</p>
          </div>
        )}
      </div>

      {error && (
        <div className="rounded border border-traffic-red/50 bg-red-50 px-3 py-2 text-sm text-traffic-red">
          {error}
        </div>
      )}

      {warnings.length > 0 && (
        <div className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <p className="font-medium">{t("uploader.duplicate_title")}</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {warnings.map((warning, idx) => (
              <li key={`${warning}-${idx}`}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
