/**
 * DevRoleSwitcher — dummy rollevelger for pilot/utvikling.
 *
 * Fjernes (eller skjules med en feature-flag) når ekte JWT-auth er på plass.
 * Vises med en amber ramme for å gjøre det åpenbart at dette IKKE er produksjon.
 */

import { useState, useRef, useEffect } from "react";
import clsx from "clsx";
import { useAuth } from "./AuthContext";
import { ROLE_LABELS, ROLE_COLORS, DEV_USERS } from "./permissions";
import type { Role } from "./permissions";

const ALL_ROLES = Object.keys(DEV_USERS) as Role[];

export function DevRoleSwitcher() {
  const { user, role, _devSetRole } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Lukk dropdown ved klikk utenfor
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      {/* Trigger-knapp */}
      <button
        onClick={() => setOpen((o) => !o)}
        className={clsx(
          "flex items-center gap-2 rounded border-2 border-amber-400 bg-amber-50 px-2 py-1",
          "text-xs font-medium text-amber-900 hover:bg-amber-100 focus:outline-none",
          "transition-colors",
        )}
        title="DEV: Bytt brukerrolle"
      >
        {/* Bruker-avatar */}
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-400 text-[10px] font-bold text-white">
          {user.name[0]}
        </span>
        <span className="hidden sm:inline">{user.name}</span>
        <span
          className={clsx(
            "hidden rounded px-1 py-0.5 text-[10px] font-semibold sm:inline",
            ROLE_COLORS[role],
          )}
        >
          {ROLE_LABELS[role]}
        </span>
        <svg
          className={clsx("h-3 w-3 transition-transform", open && "rotate-180")}
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-56 rounded-lg border border-amber-200 bg-white text-gray-900 shadow-lg">
          {/* Header */}
          <div className="border-b border-amber-100 bg-amber-50 px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-700">
              DEV-modus — velg rolle
            </p>
            <p className="text-[10px] text-amber-600">
              Byttes ut med JWT ved produksjon
            </p>
          </div>

          {/* Roller */}
          <ul className="py-1">
            {ALL_ROLES.map((r) => {
              const u = DEV_USERS[r];
              const isActive = r === role;
              return (
                <li key={r}>
                  <button
                    onClick={() => {
                      _devSetRole(r);
                      setOpen(false);
                    }}
                    className={clsx(
                      "flex w-full items-center gap-3 px-3 py-2 text-left text-sm text-gray-800",
                      "hover:bg-gray-50 focus:outline-none",
                      isActive && "bg-xlent-surface",
                    )}
                  >
                    {/* Avatar */}
                    <span
                      className={clsx(
                        "flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold",
                        isActive
                          ? "bg-xlent-primary text-white"
                          : "bg-gray-200 text-gray-600",
                      )}
                    >
                      {u.name[0]}
                    </span>

                    {/* Navn og rolle */}
                    <div className="min-w-0 flex-1">
                      <p
                        className={clsx(
                          "font-medium",
                          isActive ? "text-xlent-ink" : "text-gray-700",
                        )}
                      >
                        {u.name}
                      </p>
                      <p className="text-xs text-gray-400">{ROLE_LABELS[r]}</p>
                    </div>

                    {/* Aktiv-indikator */}
                    {isActive && (
                      <svg
                        className="h-4 w-4 flex-shrink-0 text-xlent-primary"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                      >
                        <path
                          fillRule="evenodd"
                          d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
                          clipRule="evenodd"
                        />
                      </svg>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>

          {/* Rettighets-oppsummering */}
          <div className="border-t border-gray-100 bg-gray-50 px-3 py-2">
            <RolePermissionSummary role={role} />
          </div>
        </div>
      )}
    </div>
  );
}

function RolePermissionSummary({ role }: { role: Role }) {
  const capabilities: { label: string; roles: Role[] }[] = [
    {
      label: "Last opp fakturaer",
      roles: ["admin", "compliance_officer", "controller"],
    },
    { label: "Rediger fakturaer", roles: ["admin", "compliance_officer", "controller"] },
    { label: "Godkjenn/avvis", roles: ["admin", "compliance_officer"] },
    { label: "Administrer regler", roles: ["admin", "compliance_officer"] },
    { label: "Systemadmin", roles: ["admin"] },
  ];

  return (
    <div className="space-y-0.5">
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-gray-400">
        Tilganger for {ROLE_LABELS[role]}
      </p>
      {capabilities.map((c) => {
        const allowed = c.roles.includes(role);
        return (
          <div key={c.label} className="flex items-center gap-1.5">
            <span className={allowed ? "text-green-500" : "text-gray-300"}>
              {allowed ? "✓" : "✗"}
            </span>
            <span
              className={clsx(
                "text-[11px]",
                allowed ? "text-gray-700" : "text-gray-400 line-through",
              )}
            >
              {c.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
