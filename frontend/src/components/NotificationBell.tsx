/**
 * NotificationBell — varselbjelle med dropdown.
 *
 * Vises i header. Poller backend hvert 30. sekund for nye varsler.
 * Uleste varsler spores via localStorage — ingen DB-rad per bruker.
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";

import { useNotifications } from "@/hooks/useNotifications";
import type { AppNotification } from "@/api/types";

// ── Level-styling ─────────────────────────────────────────────────────────────

function levelIcon(level: AppNotification["level"]): string {
  if (level === "error") return "🔴";
  if (level === "warn") return "🟡";
  return "🔵";
}

function levelBorderClass(level: AppNotification["level"]): string {
  if (level === "error") return "border-l-red-400";
  if (level === "warn") return "border-l-yellow-400";
  return "border-l-blue-300";
}

// ── Enkelt varsel i dropdown ──────────────────────────────────────────────────

function NotifItem({
  notif,
  isRead,
  onRead,
}: {
  notif: AppNotification;
  isRead: boolean;
  onRead: (id: string) => void;
}) {
  const navigate = useNavigate();

  function handleClick() {
    onRead(notif.id);
    if (notif.invoice_id) {
      navigate(`/invoices/${notif.invoice_id}`);
    }
  }

  return (
    <button
      onClick={handleClick}
      className={clsx(
        "w-full border-l-4 px-3 py-2 text-left transition-colors",
        levelBorderClass(notif.level),
        isRead
          ? "bg-white hover:bg-gray-50 opacity-60"
          : "bg-blue-50/50 hover:bg-blue-50 font-medium",
      )}
    >
      <div className="flex items-start gap-2">
        <span className="mt-0.5 shrink-0 text-xs">{levelIcon(notif.level)}</span>
        <div className="min-w-0">
          <p className="text-xs leading-snug text-xlent-ink line-clamp-2">
            {notif.message}
          </p>
          <p className="mt-0.5 text-[10px] text-xlent-muted">
            {new Date(notif.created_at).toLocaleString("nb-NO", {
              day: "2-digit",
              month: "2-digit",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
        </div>
        {!isRead && (
          <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-blue-500" />
        )}
      </div>
    </button>
  );
}

// ── Bjellen ───────────────────────────────────────────────────────────────────

export function NotificationBell({ role }: { role: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const { notifications, unreadCount, markRead, markAllRead, isLoading } =
    useNotifications(role, { enabled: Boolean(role) });

  // Lukk dropdown ved klikk utenfor
  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [open]);

  const readIds = new Set(
    JSON.parse(localStorage.getItem("xlent_read_notifications") ?? "[]") as string[],
  );

  return (
    <div ref={ref} className="relative">
      {/* Bjelle-knapp */}
      <button
        onClick={() => setOpen((o) => !o)}
        title="Varsler"
        className="relative flex h-8 w-8 items-center justify-center rounded-full text-xlent-muted hover:bg-gray-100 hover:text-xlent-ink focus:outline-none"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-5 w-5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.8}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>

        {/* Badge */}
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-bold leading-none text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-10 z-50 w-80 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-gray-100 px-3 py-2">
            <span className="text-xs font-semibold text-xlent-ink">
              Varsler
              {unreadCount > 0 && (
                <span className="ml-1.5 rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-700">
                  {unreadCount} nye
                </span>
              )}
            </span>
            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                className="text-[10px] text-xlent-primary hover:underline"
              >
                Merk alle lest
              </button>
            )}
          </div>

          {/* Liste */}
          <div className="max-h-80 overflow-y-auto divide-y divide-gray-50">
            {isLoading && (
              <p className="px-3 py-4 text-center text-xs text-xlent-muted">
                Laster varsler …
              </p>
            )}
            {!isLoading && notifications.length === 0 && (
              <p className="px-3 py-6 text-center text-xs text-xlent-muted">
                Ingen varsler ennå
              </p>
            )}
            {notifications.map((n) => (
              <NotifItem
                key={n.id}
                notif={n}
                isRead={readIds.has(n.id)}
                onRead={(id) => {
                  markRead(id);
                  setOpen(false);
                }}
              />
            ))}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="border-t border-gray-100 px-3 py-2 text-center">
              <span className="text-[10px] text-xlent-muted">
                Viser {notifications.length} siste
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
