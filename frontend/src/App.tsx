import { Suspense, lazy } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import clsx from "clsx";

import { useTranslation } from "react-i18next";

import { ModelSelector } from "@/components/ModelSelector";
import { NotificationBell } from "@/components/NotificationBell";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import xlentLogoWhite from "@/assets/xlent-logo-white.svg";
import { AuthProvider } from "@/auth/AuthContext";
import { DevRoleSwitcher } from "@/auth/DevRoleSwitcher";
import { ProtectedRoute } from "@/auth/ProtectedRoute";
import { useAuth } from "@/auth/AuthContext";
import type { Permission } from "@/auth/permissions";
import { useReviewQueue } from "@/hooks/useInvoices";

const InvoiceList = lazy(async () => {
  const m = await import("@/pages/InvoiceList");
  return { default: m.InvoiceList };
});
const InvoiceDetail = lazy(async () => {
  const m = await import("@/pages/InvoiceDetail");
  return { default: m.InvoiceDetail };
});
const ExtendedScreeningRunPage = lazy(async () => {
  const m = await import("@/pages/ExtendedScreeningRun");
  return { default: m.ExtendedScreeningRunPage };
});
const CustomerList = lazy(async () => {
  const m = await import("@/pages/CustomerList");
  return { default: m.CustomerList };
});
const MapsPage = lazy(async () => {
  const m = await import("@/pages/Maps");
  return { default: m.MapsPage };
});
const SanctionedEntitiesPage = lazy(async () => {
  const m = await import("@/pages/SanctionedEntities");
  return { default: m.SanctionedEntitiesPage };
});
const InvoiceSearchPage = lazy(async () => {
  const m = await import("@/pages/InvoiceSearch");
  return { default: m.InvoiceSearchPage };
});
const PipelineOpsPage = lazy(async () => {
  const m = await import("@/pages/PipelineOps");
  return { default: m.PipelineOpsPage };
});
const DashboardPage = lazy(async () => {
  const m = await import("@/pages/Dashboard");
  return { default: m.DashboardPage };
});
const RulesPage = lazy(async () => {
  const m = await import("@/pages/Rules");
  return { default: m.RulesPage };
});
const AgreementsPage = lazy(async () => {
  const m = await import("@/pages/Agreements");
  return { default: m.AgreementsPage };
});
const ReviewQueuePage = lazy(async () => {
  const m = await import("@/pages/ReviewQueue");
  return { default: m.ReviewQueuePage };
});
const WatchlistPage = lazy(async () => {
  const m = await import("@/pages/Watchlist");
  return { default: m.WatchlistPage };
});

function PageFallback() {
  const { t } = useTranslation();
  return <div className="p-6 text-sm text-xlent-muted">{t("loading_page")}</div>;
}

/**
 * Nav-lenke med rettighets-bevissthet.
 *
 * - `require` mangler / oppfylt  → vanlig aktiv NavLink
 * - `require` ikke oppfylt       → grå span med tooltip (minimal skjuling)
 * - `adminOnly`                  → skjules helt for ikke-admins
 * - `badge`                      → rød teller-boble (f.eks. antall ventende reviews)
 */
function NavItem({
  to,
  label,
  end,
  require,
  adminOnly,
  badge,
}: {
  to: string;
  label: string;
  end?: boolean;
  /** Rettighet som kreves — mangler den vises lenken grå */
  require?: Permission;
  /** Skjul siden helt for alle uten system:admin */
  adminOnly?: boolean;
  /** Vises som rød boble bak label-teksten */
  badge?: number;
}) {
  const { can } = useAuth();
  const { t } = useTranslation();

  if (adminOnly && !can("system:admin")) return null;

  const allowed = !require || can(require);

  if (!allowed) {
    return (
      <span
        title={t("nav.no_access")}
        className="cursor-not-allowed text-sm text-gray-300 select-none"
      >
        {label}
      </span>
    );
  }

  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        clsx(
          "relative inline-flex items-center gap-1.5 text-sm hover:text-xlent-primary",
          isActive ? "text-xlent-primary" : "text-xlent-muted",
        )
      }
    >
      {label}
      {badge != null && badge > 0 && (
        <span className="inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold leading-none text-white">
          {badge > 99 ? "99+" : badge}
        </span>
      )}
    </NavLink>
  );
}

/** Henter antall fakturaer som venter på review (status=screened, score red/yellow). */
function useReviewBadge(): number {
  const { can } = useAuth();
  const { data } = useReviewQueue(
    { limit: 100 },
    { enabled: can("invoices:review") },
  );
  if (!data) return 0;
  return data.items.filter((i) => i.status === "screened").length;
}

function AppShell() {
  const reviewBadge = useReviewBadge();
  const { role } = useAuth();
  const { t } = useTranslation();

  return (
    <div className="min-h-full">
      <header className="border-b border-gray-200 bg-white">
        <div className="border-b border-white/20 bg-xlent-primary">
          <div className="mx-auto flex max-w-6xl items-center gap-3 px-6 py-3">
            <NavLink to="/" className="inline-flex items-center" end>
              <img src={xlentLogoWhite} alt="XLENT" className="h-6 w-auto" />
            </NavLink>
            <span className="text-base font-medium text-white/90">{t("header_title")}</span>
            <div className="ml-auto flex items-center gap-2">
              <DevRoleSwitcher />
              <LanguageSwitcher variant="dark" />
              <ModelSelector variant="dark" />
              <NotificationBell role={role} />
            </div>
          </div>
        </div>

        <div className="mx-auto max-w-6xl px-6 py-3">
          <nav className="flex flex-wrap items-center gap-x-4 gap-y-2">
            {/* Primære sider — synlig for alle */}
            <NavItem to="/" label={t("nav.invoices")} end />
            <NavItem to="/dashboard" label={t("nav.dashboard")} />
            <NavItem to="/customers" label={t("nav.customers")} />

            {/* Review-kø — synlig for compliance_officer og admin */}
            <NavItem
              to="/review-queue"
              label={t("nav.review_queue")}
              require="invoices:review"
              badge={reviewBadge}
            />

            {/* Compliance-verktøy */}
            <NavItem to="/rules" label={t("nav.rules")} require="rules:view" />
            <NavItem to="/watchlist" label={t("nav.watchlist")} require="rules:edit" />
            <NavItem to="/agreements" label={t("nav.agreements")} />

            {/* Kart og screening — synlig for alle */}
            <NavItem to="/maps" label={t("nav.maps")} />
            <NavItem to="/sanctioned-entities" label={t("nav.sanctioned_entities")} />

            {/* Søk */}
            <NavItem to="/invoice-search" label={t("nav.invoice_search")} />

            {/* Drift — skjules helt for ikke-admins */}
            <NavItem to="/pipeline-ops" label={t("nav.pipeline_ops")} adminOnly />

          </nav>
        </div>
      </header>

      <main>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            {/* Åpne ruter (alle roller med invoices:view) */}
            <Route path="/" element={<InvoiceList />} />
            <Route path="/invoices/:id" element={<InvoiceDetail />} />
            <Route
              path="/invoices/:invoiceId/entities/:entityId/extended-screen/:runId"
              element={<ExtendedScreeningRunPage />}
            />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/maps" element={<MapsPage />} />
            <Route path="/invoice-search" element={<InvoiceSearchPage />} />
            <Route path="/risk-map" element={<Navigate to="/maps" replace />} />
            <Route path="/shipments-map" element={<Navigate to="/maps" replace />} />

            {/* Kunder */}
            <Route
              path="/customers"
              element={
                <ProtectedRoute require="customers:view">
                  <CustomerList />
                </ProtectedRoute>
              }
            />

            {/* Regler — compliance_officer og admin */}
            <Route
              path="/rules"
              element={
                <ProtectedRoute require="rules:view">
                  <RulesPage />
                </ProtectedRoute>
              }
            />

            {/* Rammeavtaler */}
            <Route
              path="/agreements"
              element={
                <ProtectedRoute require="agreements:view">
                  <AgreementsPage />
                </ProtectedRoute>
              }
            />

            {/* Sanksjonerte entiteter — krever screen-rettighet */}
            <Route
              path="/sanctioned-entities"
              element={
                <ProtectedRoute require="invoices:screen">
                  <SanctionedEntitiesPage />
                </ProtectedRoute>
              }
            />

            {/* Review-kø — compliance_officer og admin */}
            <Route
              path="/review-queue"
              element={
                <ProtectedRoute require="invoices:review">
                  <ReviewQueuePage />
                </ProtectedRoute>
              }
            />

            {/* Intern sperreliste — admin og compliance_officer */}
            <Route
              path="/watchlist"
              element={
                <ProtectedRoute require="rules:edit">
                  <WatchlistPage />
                </ProtectedRoute>
              }
            />

            {/* Pipeline-drift — kun admin */}
            <Route
              path="/pipeline-ops"
              element={
                <ProtectedRoute require="system:admin">
                  <PipelineOpsPage />
                </ProtectedRoute>
              }
            />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
