import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";

import { useUploadInvoice } from "@/hooks/useInvoices";
import { useCustomerList } from "@/hooks/useCustomers";
import type { InvoiceDirection } from "@/api/types";

export function InvoiceUploader() {
  const [direction, setDirection] = useState<InvoiceDirection>("incoming");
  const [customerId, setCustomerId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const upload = useUploadInvoice();
  const navigate = useNavigate();

  // Hent kunder for dropdown — maks 200 uten paginering
  const { data: customerData } = useCustomerList({ limit: 200 });

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      setError(null);
      const file = acceptedFiles[0];
      if (!file) return;

      try {
        const result = await upload.mutateAsync({
          file,
          direction,
          customerId: customerId || null,
        });
        // Gå til detaljsiden — den poller automatisk til parsing er ferdig
        navigate(`/invoices/${result.invoice.id}`);
      } catch (err) {
        const message =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Opplasting feilet. Sjekk at filen er gyldig og prøv igjen.";
        setError(message);
      }
    },
    [direction, customerId, navigate, upload],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "image/png": [".png"],
    },
    maxFiles: 1,
    disabled: upload.isPending,
  });

  const selectCls =
    "rounded border border-gray-300 bg-white px-2 py-1 text-sm disabled:opacity-60";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-4 text-sm">
        {/* Retning */}
        <div className="flex items-center gap-2">
          <label className="font-medium text-xlent-ink">Type:</label>
          <select
            value={direction}
            onChange={(e) => setDirection(e.target.value as InvoiceDirection)}
            className={selectCls}
            disabled={upload.isPending}
          >
            <option value="incoming">Innkommende</option>
            <option value="outgoing">Utgående</option>
          </select>
        </div>

        {/* Kunde */}
        {customerData && customerData.items.length > 0 && (
          <div className="flex items-center gap-2">
            <label className="font-medium text-xlent-ink">Kunde:</label>
            <select
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              className={selectCls}
              disabled={upload.isPending}
            >
              <option value="">— Ingen —</option>
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
          upload.isPending && "cursor-not-allowed opacity-60",
        )}
      >
        <input {...getInputProps()} />
        {upload.isPending ? (
          <div className="flex items-center gap-2">
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-xlent-primary border-t-transparent" />
            <p className="text-sm text-xlent-muted">Laster opp …</p>
          </div>
        ) : isDragActive ? (
          <p className="text-sm text-xlent-primary">Slipp filen her</p>
        ) : (
          <div>
            <p className="text-sm font-medium text-xlent-ink">
              Dra og slipp en invoice (PDF, XLSX eller PNG), eller klikk for å velge
            </p>
            <p className="mt-1 text-xs text-xlent-muted">Maks 25 MB. PDF, XLSX eller PNG.</p>
          </div>
        )}
      </div>

      {error && (
        <div className="rounded border border-traffic-red/50 bg-red-50 px-3 py-2 text-sm text-traffic-red">
          {error}
        </div>
      )}
    </div>
  );
}
