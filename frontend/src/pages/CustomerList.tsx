import { useState } from "react";
import clsx from "clsx";

import { Pagination } from "@/components/Pagination";
import {
  useCreateCustomer,
  useCustomerList,
  useDeleteCustomer,
  useUpdateCustomer,
} from "@/hooks/useCustomers";
import type { Customer, CustomerCreate, CustomerUpdate } from "@/api/customers";

// ── Risiko-badge ──────────────────────────────────────────────────────────────

const RISK_COLORS: Record<string, string> = {
  low: "bg-green-100 text-green-800",
  normal: "bg-gray-100 text-gray-700",
  high: "bg-yellow-100 text-yellow-800",
  critical: "bg-red-100 text-red-800",
};

const RISK_LABELS: Record<string, string> = {
  low: "Lav",
  normal: "Normal",
  high: "Høy",
  critical: "Kritisk",
};

function RiskBadge({ level }: { level: string }) {
  return (
    <span
      className={clsx(
        "inline-block rounded px-1.5 py-0.5 text-xs font-medium",
        RISK_COLORS[level] ?? RISK_COLORS.normal,
      )}
    >
      {RISK_LABELS[level] ?? level}
    </span>
  );
}

// ── Opprett/rediger-skjema ────────────────────────────────────────────────────

const RISK_OPTIONS = [
  { value: "low", label: "Lav" },
  { value: "normal", label: "Normal" },
  { value: "high", label: "Høy" },
  { value: "critical", label: "Kritisk" },
];

const inputCls =
  "w-full rounded border border-gray-300 bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-xlent-primary";

interface CustomerFormProps {
  initial?: Customer;
  onSubmit: (data: CustomerCreate | CustomerUpdate) => Promise<void>;
  onCancel: () => void;
  isPending: boolean;
}

function CustomerForm({ initial, onSubmit, onCancel, isPending }: CustomerFormProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [country, setCountry] = useState(initial?.country ?? "");
  const [orgNumber, setOrgNumber] = useState(initial?.org_number ?? "");
  const [riskLevel, setRiskLevel] = useState(initial?.risk_level ?? "normal");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError("Navn er påkrevd.");
      return;
    }
    try {
      await onSubmit({
        name: name.trim(),
        country: country.trim().toUpperCase() || null,
        org_number: orgNumber.trim() || null,
        risk_level: riskLevel,
      });
    } catch {
      setError("Lagring feilet. Prøv igjen.");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <label className="mb-1 block text-xs font-medium text-xlent-muted">
            Navn *
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={inputCls}
            placeholder="Kundennavn"
            required
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-xlent-muted">
            Land (ISO-2)
          </label>
          <input
            value={country}
            onChange={(e) => setCountry(e.target.value.toUpperCase().slice(0, 2))}
            className={clsx(inputCls, "uppercase")}
            placeholder="NO"
            maxLength={2}
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-xlent-muted">
            Org.nummer
          </label>
          <input
            value={orgNumber}
            onChange={(e) => setOrgNumber(e.target.value)}
            className={inputCls}
            placeholder="123 456 789"
          />
        </div>

        <div className="col-span-2">
          <label className="mb-1 block text-xs font-medium text-xlent-muted">
            Risikonivå
          </label>
          <select
            value={riskLevel}
            onChange={(e) => setRiskLevel(e.target.value)}
            className={inputCls}
          >
            {RISK_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <p className="text-xs text-traffic-red">{error}</p>}

      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded border border-gray-300 px-3 py-1.5 text-sm text-xlent-muted hover:bg-xlent-surface"
        >
          Avbryt
        </button>
        <button
          type="submit"
          disabled={isPending}
          className="rounded bg-xlent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-xlent-primary/90 disabled:opacity-50"
        >
          {isPending ? "Lagrer …" : initial ? "Oppdater" : "Opprett"}
        </button>
      </div>
    </form>
  );
}

// ── Rad med inline-redigering ─────────────────────────────────────────────────

function CustomerRow({
  customer,
  onEdit,
  onDelete,
  isDeleting,
}: {
  customer: Customer;
  onEdit: (c: Customer) => void;
  onDelete: (id: string) => void;
  isDeleting: boolean;
}) {
  return (
    <tr className="hover:bg-xlent-surface">
      <td className="px-3 py-2 font-medium text-xlent-ink">{customer.name}</td>
      <td className="px-3 py-2 font-mono text-xs uppercase text-xlent-muted">
        {customer.country ?? "—"}
      </td>
      <td className="px-3 py-2 font-mono text-xs text-xlent-muted">
        {customer.org_number ?? "—"}
      </td>
      <td className="px-3 py-2">
        <RiskBadge level={customer.risk_level} />
      </td>
      <td className="px-3 py-2 text-xs text-xlent-muted">
        {new Date(customer.created_at).toLocaleDateString("nb-NO")}
      </td>
      <td className="px-3 py-2 text-right">
        <div className="flex justify-end gap-2">
          <button
            onClick={() => onEdit(customer)}
            className="rounded px-2 py-0.5 text-xs text-xlent-primary hover:bg-blue-50"
          >
            Rediger
          </button>
          <button
            onClick={() => onDelete(customer.id)}
            disabled={isDeleting}
            className="rounded px-2 py-0.5 text-xs text-traffic-red hover:bg-red-50 disabled:opacity-40"
          >
            Slett
          </button>
        </div>
      </td>
    </tr>
  );
}

// ── Hoved-komponent ───────────────────────────────────────────────────────────

export function CustomerList() {
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data, isLoading, error } = useCustomerList({
    limit,
    offset,
    search: search || undefined,
  });

  const createCustomer = useCreateCustomer();
  const deleteCustomer = useDeleteCustomer();

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const updateCustomer = useUpdateCustomer(editingCustomer?.id ?? "");

  const total = data?.total ?? 0;

  function handleDelete(id: string) {
    const customer = data?.items.find((c) => c.id === id);
    const label = customer?.name ?? id;
    if (!window.confirm(`Slett «${label}»?\n\nKunden fjernes permanent.`)) return;
    deleteCustomer.mutate(id);
  }

  async function handleCreate(formData: CustomerCreate | CustomerUpdate) {
    await createCustomer.mutateAsync(formData as CustomerCreate);
    setShowCreateForm(false);
  }

  async function handleUpdate(formData: CustomerCreate | CustomerUpdate) {
    if (!editingCustomer) return;
    await updateCustomer.mutateAsync(formData as CustomerUpdate);
    setEditingCustomer(null);
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-xlent-ink">Kunder</h1>
        <p className="mt-1 text-sm text-xlent-muted">
          Administrer kunder og risikonivå. Kunder kan kobles til invoices ved opplasting.
        </p>
      </header>

      {/* Opprett ny kunde */}
      {showCreateForm ? (
        <section className="rounded-lg border border-xlent-primary/30 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-xlent-ink">Ny kunde</h2>
          <CustomerForm
            onSubmit={handleCreate}
            onCancel={() => setShowCreateForm(false)}
            isPending={createCustomer.isPending}
          />
        </section>
      ) : (
        <button
          onClick={() => setShowCreateForm(true)}
          className="rounded bg-xlent-primary px-4 py-2 text-sm font-medium text-white hover:bg-xlent-primary/90"
        >
          + Ny kunde
        </button>
      )}

      {/* Redigerings-modal (inline) */}
      {editingCustomer && (
        <section className="rounded-lg border border-yellow-300 bg-yellow-50 p-4">
          <h2 className="mb-3 text-sm font-semibold text-xlent-ink">
            Rediger: {editingCustomer.name}
          </h2>
          <CustomerForm
            initial={editingCustomer}
            onSubmit={handleUpdate}
            onCancel={() => setEditingCustomer(null)}
            isPending={updateCustomer.isPending}
          />
        </section>
      )}

      {/* Søk */}
      <section>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-xlent-muted">
            Alle kunder
            {total > 0 && (
              <span className="ml-2 font-normal normal-case text-xlent-muted/60">
                ({total} totalt)
              </span>
            )}
          </h2>
          <input
            type="search"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
            placeholder="Søk på navn…"
            className="rounded border border-gray-200 bg-white px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-xlent-primary"
          />
        </div>

        {isLoading && <p className="text-sm text-xlent-muted">Laster …</p>}
        {error && (
          <p className="text-sm text-traffic-red">
            Kunne ikke laste kunder. Sjekk at API-et kjører.
          </p>
        )}

        {data && (
          <>
            <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-xlent-surface text-left text-xs uppercase text-xlent-muted">
                  <tr>
                    <th className="px-3 py-2">Navn</th>
                    <th className="px-3 py-2">Land</th>
                    <th className="px-3 py-2">Org.nr</th>
                    <th className="px-3 py-2">Risiko</th>
                    <th className="px-3 py-2">Opprettet</th>
                    <th className="px-3 py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data.items.length === 0 && (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-3 py-6 text-center text-xlent-muted"
                      >
                        {search
                          ? "Ingen kunder matcher søket."
                          : 'Ingen kunder ennå — klikk «+ Ny kunde» for å komme i gang.'}
                      </td>
                    </tr>
                  )}
                  {data.items.map((customer) => (
                    <CustomerRow
                      key={customer.id}
                      customer={customer}
                      onEdit={setEditingCustomer}
                      onDelete={handleDelete}
                      isDeleting={deleteCustomer.isPending}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            <Pagination
              total={total}
              limit={limit}
              offset={offset}
              onPrev={() => setOffset(Math.max(0, offset - limit))}
              onNext={() => setOffset(offset + limit)}
            />
          </>
        )}
      </section>
    </div>
  );
}
