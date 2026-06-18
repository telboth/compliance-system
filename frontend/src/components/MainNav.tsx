import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import clsx from "clsx";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/auth/AuthContext";
import type { Permission } from "@/auth/permissions";

type NavGroupItem = {
  to: string;
  label: string;
  end?: boolean;
  require?: Permission;
  adminOnly?: boolean;
  badge?: number;
};

function pathMatches(pathname: string, to: string, end = false) {
  if (end) return pathname === to;
  return pathname === to || pathname.startsWith(`${to}/`);
}

function NavEntry({ item }: { item: NavGroupItem }) {
  const { can } = useAuth();
  const { t } = useTranslation();

  if (item.adminOnly && !can("system:admin")) return null;

  const badge = item.badge && item.badge > 0 ? item.badge : null;
  const activeClass = "bg-xlent-primary/10 text-xlent-primary";
  const baseClass = "flex items-center justify-between rounded-lg px-3 py-2 text-sm transition";

  if (item.require && !can(item.require)) {
    return (
      <span
        title={t("nav.no_access")}
        className={clsx(baseClass, "cursor-not-allowed text-gray-300")}
      >
        <span>{item.label}</span>
        {badge != null && (
          <span className="ml-2 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold leading-none text-white">
            {badge > 99 ? "99+" : badge}
          </span>
        )}
      </span>
    );
  }

  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) =>
        clsx(
          baseClass,
          isActive ? activeClass : "text-xlent-muted hover:bg-gray-50 hover:text-xlent-ink",
        )
      }
    >
      <span>{item.label}</span>
      {badge != null && (
        <span className="ml-2 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold leading-none text-white">
          {badge > 99 ? "99+" : badge}
        </span>
      )}
    </NavLink>
  );
}

function NavGroup({
  id,
  label,
  items,
  openGroup,
  setOpenGroup,
}: {
  id: string;
  label: string;
  items: NavGroupItem[];
  openGroup: string | null;
  setOpenGroup: (next: string | null) => void;
}) {
  const { can } = useAuth();
  const location = useLocation();

  const visibleItems = items.filter((item) => !item.adminOnly || can("system:admin"));
  const isActive = visibleItems.some((item) => pathMatches(location.pathname, item.to, item.end));

  if (visibleItems.length === 0) {
    return null;
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpenGroup(openGroup === id ? null : id)}
        className={clsx(
          "inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-sm font-medium transition",
          isActive
            ? "bg-xlent-primary/10 text-xlent-primary"
            : "text-xlent-muted hover:text-xlent-primary",
        )}
        aria-expanded={openGroup === id}
        aria-haspopup="menu"
      >
        <span>{label}</span>
        <span className="text-[10px] leading-none opacity-70">{openGroup === id ? "▴" : "▾"}</span>
      </button>

      {openGroup === id && (
        <div className="absolute left-0 top-full z-30 mt-2 w-72 max-w-[calc(100vw-2rem)] rounded-xl border border-gray-200 bg-white p-2 shadow-lg sm:w-80">
          <div className="max-h-[70vh] space-y-1 overflow-y-auto">
            {visibleItems.map((item) => (
              <NavEntry key={item.to} item={item} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function MainNav({ reviewBadge }: { reviewBadge: number }) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const [openGroup, setOpenGroup] = useState<string | null>(null);

  useEffect(() => {
    setOpenGroup(null);
  }, [pathname]);

  return (
    <nav className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <NavGroup
        id="invoices"
        label={t("nav.invoices")}
        openGroup={openGroup}
        setOpenGroup={setOpenGroup}
        items={[
          { to: "/invoices", label: t("nav.invoice_overview"), end: true },
          { to: "/invoices/search", label: t("nav.invoice_search"), end: true },
        ]}
      />

      <NavGroup
        id="worklists"
        label={t("nav.worklists_group")}
        openGroup={openGroup}
        setOpenGroup={setOpenGroup}
        items={[
          { to: "/review-queue", label: t("nav.review_queue"), badge: reviewBadge },
          { to: "/control-effectiveness", label: t("nav.control_effectiveness"), require: "invoices:review" },
        ]}
      />

      <NavGroup
        id="analysis"
        label={t("nav.analysis_group")}
        openGroup={openGroup}
        setOpenGroup={setOpenGroup}
        items={[
          { to: "/dashboard", label: t("nav.dashboard") },
          { to: "/kri", label: t("nav.kri") },
          { to: "/regulatory-radar", label: t("nav.regulatory_radar") },
          { to: "/maps", label: t("nav.maps") },
          { to: "/sanctioned-entities", label: t("nav.sanctioned_entities") },
          { to: "/customers", label: t("nav.customers") },
          { to: "/vendors", label: t("nav.vendors"), require: "customers:view" },
        ]}
      />

      <NavGroup
        id="configuration"
        label={t("nav.configuration_group")}
        openGroup={openGroup}
        setOpenGroup={setOpenGroup}
        items={[
          { to: "/rules", label: t("nav.rules"), require: "rules:view" },
          { to: "/watchlist", label: t("nav.watchlist"), require: "rules:edit" },
          { to: "/agreements", label: t("nav.agreements") },
          { to: "/list-admin", label: t("nav.list_admin") },
        ]}
      />

      <NavGroup
        id="operations"
        label={t("nav.operations_group")}
        openGroup={openGroup}
        setOpenGroup={setOpenGroup}
        items={[
          { to: "/pipeline-ops", label: t("nav.pipeline_ops"), adminOnly: true },
        ]}
      />

      <NavLink
        to="/about"
        className={({ isActive }) =>
          clsx(
            "inline-flex items-center rounded-full px-3 py-1.5 text-sm font-medium transition hover:text-xlent-primary",
            isActive ? "bg-xlent-primary/10 text-xlent-primary" : "text-xlent-muted",
          )
        }
      >
        {t("nav.about")}
      </NavLink>
    </nav>
  );
}
