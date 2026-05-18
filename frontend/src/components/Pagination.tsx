interface PaginationProps {
  total: number;
  limit: number;
  offset: number;
  onPrev: () => void;
  onNext: () => void;
}

export function Pagination({ total, limit, offset, onPrev, onNext }: PaginationProps) {
  if (total <= limit) return null;
  return (
    <div className="mt-3 flex items-center justify-between text-xs text-xlent-muted">
      <span>
        Viser {offset + 1}–{Math.min(offset + limit, total)} av {total}
      </span>
      <div className="flex gap-2">
        <button
          onClick={onPrev}
          disabled={offset === 0}
          className="rounded border px-2 py-1 hover:bg-xlent-surface disabled:opacity-40"
        >
          ← Forrige
        </button>
        <button
          onClick={onNext}
          disabled={offset + limit >= total}
          className="rounded border px-2 py-1 hover:bg-xlent-surface disabled:opacity-40"
        >
          Neste →
        </button>
      </div>
    </div>
  );
}
