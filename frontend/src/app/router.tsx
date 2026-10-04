import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { LoginPage } from "../pages/LoginPage";
import { DashboardPage } from "../pages/DashboardPage";
import { LandingPage } from "../pages/LandingPage";
import { RegisterPage } from "../pages/RegisterPage";
import { ForgotPasswordPage } from "../pages/ForgotPasswordPage";
import { ResetPasswordPage } from "../pages/ResetPasswordPage";
import { VerifyEmailPage } from "../pages/VerifyEmailPage";
import { ShopPage } from "../pages/ShopPage";
import { OrdersPage } from "../pages/OrdersPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { loginUrl } from "../lib/redirect";
import { isAuthenticated } from "../services/api";
import { useCurrentUser } from "../hooks/useCurrentUser";
import { LoadingState } from "../components/ui";

// Selten gebrauchte Seiten und der Admin-Bereich werden erst bei Bedarf geladen; Dashboard, Shop und Bestellungen bleiben im Haupt-Chunk
const InstanceDetailPage = lazy(() => import("../pages/InstanceDetailPage").then((m) => ({ default: m.InstanceDetailPage })));
const AccountPage = lazy(() => import("../pages/AccountPage").then((m) => ({ default: m.AccountPage })));
const SshKeysPage = lazy(() => import("../pages/SshKeysPage").then((m) => ({ default: m.SshKeysPage })));
const ImpressumPage = lazy(() => import("../pages/LegalPages").then((m) => ({ default: m.ImpressumPage })));
const DatenschutzPage = lazy(() => import("../pages/LegalPages").then((m) => ({ default: m.DatenschutzPage })));
const AgbPage = lazy(() => import("../pages/LegalPages").then((m) => ({ default: m.AgbPage })));
const AdminOverviewPage = lazy(() => import("../pages/AdminOverviewPage").then((m) => ({ default: m.AdminOverviewPage })));
const AdminAgentsPage = lazy(() => import("../pages/AdminAgentsPage").then((m) => ({ default: m.AdminAgentsPage })));
const AdminAgentsMonitoringPage = lazy(() => import("../pages/AdminAgentsMonitoringPage").then((m) => ({ default: m.AdminAgentsMonitoringPage })));
const AdminBlueprintsPage = lazy(() => import("../pages/AdminBlueprintsPage").then((m) => ({ default: m.AdminBlueprintsPage })));
const AdminInstancesPage = lazy(() => import("../pages/AdminInstancesPage").then((m) => ({ default: m.AdminInstancesPage })));
const AdminWebhooksPage = lazy(() => import("../pages/AdminWebhooksPage").then((m) => ({ default: m.AdminWebhooksPage })));
const AdminJobsPage = lazy(() => import("../pages/AdminJobsPage").then((m) => ({ default: m.AdminJobsPage })));
const AdminSystemPage = lazy(() => import("../pages/AdminSystemPage").then((m) => ({ default: m.AdminSystemPage })));
const AdminProductsPage = lazy(() => import("../pages/AdminProductsPage").then((m) => ({ default: m.AdminProductsPage })));
const AdminInvoicesPage = lazy(() => import("../pages/AdminInvoicesPage").then((m) => ({ default: m.AdminInvoicesPage })));
const AdminOrdersPage = lazy(() => import("../pages/AdminOrdersPage").then((m) => ({ default: m.AdminOrdersPage })));

/**
 * Schuetzt Routen: Leitet zu /login um wenn nicht eingeloggt.
 */
export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  if (!isAuthenticated()) {
    // Nach dem Login zurueck zur urspruenglich angefragten Seite
    return <Navigate to={loginUrl(location.pathname + location.search)} replace />;
  }
  return <>{children}</>;
}

/**
 * Nur fuer Administratoren; Kunden werden zum Dashboard umgeleitet.
 * (Die eigentliche Absicherung passiert im Backend, das hier ist nur UX.)
 */
function AdminRoute({ children }: { children: React.ReactNode }) {
  const user = useCurrentUser();
  if (!user) return <LoadingState />;
  if (!user.is_admin) return <Navigate to="/" replace />;
  return <>{children}</>;
}

/** "/": angemeldet das Dashboard "Meine Server", sonst die öffentliche Landingpage. */
function HomeRoute() {
  return isAuthenticated() ? <DashboardPage /> : <LandingPage />;
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingState />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/impressum" element={<ImpressumPage />} />
        <Route path="/datenschutz" element={<DatenschutzPage />} />
        <Route path="/agb" element={<AgbPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/password-reset" element={<ForgotPasswordPage />} />
        <Route path="/password-reset/confirm" element={<ResetPasswordPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/" element={<HomeRoute />} />
        <Route path="/admin" element={<ProtectedRoute><AdminRoute><AdminOverviewPage /></AdminRoute></ProtectedRoute>} />
        <Route path="/admin/agents" element={<ProtectedRoute><AdminRoute><AdminAgentsPage /></AdminRoute></ProtectedRoute>} />
        <Route path="/admin/agents/monitoring" element={<ProtectedRoute><AdminRoute><AdminAgentsMonitoringPage /></AdminRoute></ProtectedRoute>} />
        <Route path="/admin/blueprints" element={<ProtectedRoute><AdminRoute><AdminBlueprintsPage /></AdminRoute></ProtectedRoute>} />
        <Route path="/admin/instances" element={<ProtectedRoute><AdminRoute><AdminInstancesPage /></AdminRoute></ProtectedRoute>} />
        <Route path="/admin/webhooks" element={<ProtectedRoute><AdminRoute><AdminWebhooksPage /></AdminRoute></ProtectedRoute>} />
        <Route path="/admin/jobs" element={<ProtectedRoute><AdminRoute><AdminJobsPage /></AdminRoute></ProtectedRoute>} />
        <Route path="/admin/system" element={<ProtectedRoute><AdminRoute><AdminSystemPage /></AdminRoute></ProtectedRoute>} />
        <Route path="/instances/:uuid" element={<ProtectedRoute><InstanceDetailPage /></ProtectedRoute>} />
        <Route path="/shop" element={<ProtectedRoute><ShopPage /></ProtectedRoute>} />
        <Route path="/orders" element={<ProtectedRoute><OrdersPage /></ProtectedRoute>} />
        <Route path="/admin/products" element={<ProtectedRoute><AdminRoute><AdminProductsPage /></AdminRoute></ProtectedRoute>} />
        <Route path="/admin/invoices" element={<ProtectedRoute><AdminRoute><AdminInvoicesPage /></AdminRoute></ProtectedRoute>} />
        <Route path="/admin/orders" element={<ProtectedRoute><AdminRoute><AdminOrdersPage /></AdminRoute></ProtectedRoute>} />
        <Route path="/account" element={<ProtectedRoute><AccountPage /></ProtectedRoute>} />
        <Route path="/account/ssh-keys" element={<ProtectedRoute><SshKeysPage /></ProtectedRoute>} />
        <Route path="*" element={<ProtectedRoute><NotFoundPage /></ProtectedRoute>} />
      </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
