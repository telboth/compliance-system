import { Suspense, lazy, Component, type ReactNode, type ErrorInfo } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import { useTranslation } from "react-i18next";

import { ModelSelector } from "@/components/ModelSelector";
import { NotificationBell } from "@/components/NotificationBell";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { MainNav } from "@/components/MainNav";
import xlentLogoWhite from "@/assets/xlent-logo-white.svg";
import { AuthProvider } from "@/auth/AuthContext";
import { DevRoleSwitcher } from "@/auth/DevRoleSwitcher";
import { ProtectedRoute } from "@/auth/ProtectedRoute";
import { useAuth } from "@/auth/AuthContext";
import { useReviewQueue } from "@/hooks/useInvoices";
import { APP_VERSION } from "@/version";
import { ApiKeysModal } from "@/components/ApiKeysModal";

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
const AboutPage = lazy(async () => {
  const m = await import("@/pages/About");
  return { default: m.AboutPage };
});
const KRIPage = lazy(async () => {
  const m = await import("@/pages/KRI");
  return { default: m.KRIPage };
});
const RegulatoryRadarPage = lazy(async () => {
  const m = await import("@/pages/RegulatoryRadar");
  return { default: m.RegulatoryRadarPage };
});
const VendorsPage = lazy(async () => {
  const m = await import("@/pages/Vendors");
  return { default: m.VendorsPage };
});
const ControlEffectivenessPage = lazy(async () => {
  const m = await import("@/pages/ControlEffectiveness");
  return { default: m.ControlEffectivenessPage };
});
const ExportControlReferencePage = lazy(async () => {
  const m = await import("@/pages/ExportControlReference");
  return { default: m.ExportControlReferencePage };
});
const ListAdminPage = lazy(async () => {
  const m = await import("@/pages/ListAdmin");
  return { default: m.ListAdminPage };
});

/** Fanger krasj i lazy-lastede sider og viser feilmelding i stedet for blank side. */
class PageErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[PageErrorBoundary] side krasjet:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8 text-center">
          <div className="text-4xl">⚠️</div>
          <h2 className="text-lg font-semibold text-xlent-ink">Siden kunne ikke lastes</h2>
          <p className="max-w-md text-sm text-xlent-muted">
            {this.state.error.message || "En uventet feil oppstod."}
          </p>
          <button
            className="rounded bg-xlent-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            onClick={() => window.location.reload()}
          >
            Last inn siden på nytt
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function PageFallback() {
  const { t } = useTranslation();
  return <div className="p-6 text-sm text-xlent-muted">{t("loading_page")}</div>;
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
  const { role, can } = useAuth();
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
            <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[11px] text-white/60">
              {APP_VERSION}
            </span>
            <div className="ml-auto flex items-center gap-2">
              <DevRoleSwitcher />
              <LanguageSwitcher variant="dark" />
              <ModelSelector variant="dark" />
              <NotificationBell role={role} />
            </div>
          </div>
        </div>

        <div className="mx-auto max-w-6xl px-6 py-3">
          <MainNav reviewBadge={reviewBadge} />
        </div>
      </header>

      {/* Nøkkelstatus-sjekk: blokkerende modal eller advarselsbanner */}
      <ApiKeysModal />

      <main>
        <PageErrorBoundary>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            {/* Åpne ruter (alle roller med invoices:view) */}
            <Route
              path="/"
              element={
                can("invoices:review")
                  ? <Navigate to="/review-queue" replace />
                  : <Navigate to="/invoices" replace />
              }
            />
            <Route path="/invoices" element={<InvoiceList />} />
            <Route path="/invoices/:id" element={<InvoiceDetail />} />
            <Route
              path="/invoices/:invoiceId/entities/:entityId/extended-screen/:runId"
              element={<ExtendedScreeningRunPage />}
            />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/maps" element={<MapsPage />} />
            <Route path="/invoices/search" element={<InvoiceSearchPage />} />
            <Route path="/invoice-search" element={<Navigate to="/invoices/search" replace />} />
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

            {/* KRI og regulatorisk radar */}
            <Route path="/kri" element={<KRIPage />} />
            <Route path="/regulatory-radar" element={<RegulatoryRadarPage />} />

            {/* Leverandørregister */}
            <Route
              path="/vendors"
              element={
                <ProtectedRoute require="customers:view">
                  <VendorsPage />
                </ProtectedRoute>
              }
            />

            {/* MVA-avvik — arbeidsliste for controlleren */}
            <Route path="/vat-mismatch" element={<Navigate to="/review-queue?filter=vat" replace />} />

            {/* Eksportkontroll — listematch mot Vareliste I/II */}
            <Route path="/export-control" element={<Navigate to="/review-queue?filter=export_control" replace />} />
            <Route path="/export-control/reference" element={<ExportControlReferencePage />} />

            {/* Catch-all — sluttbruker-/sluttbruk-screening */}
            <Route path="/catch-all" element={<Navigate to="/review-queue?filter=catch_all" replace />} />

            {/* Liste-admin — månedlig synkronisering av DEKSA/embargo */}
            <Route path="/list-admin" element={<ListAdminPage />} />

            {/* Kontrolleffektivitet — compliance_officer og admin */}
            <Route
              path="/control-effectiveness"
              element={
                <ProtectedRoute require="invoices:review">
                  <ControlEffectivenessPage />
                </ProtectedRoute>
              }
            />

            {/* Om systemet */}
            <Route path="/about" element={<AboutPage />} />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
        </PageErrorBoundary>
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
