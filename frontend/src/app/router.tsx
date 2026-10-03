import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { LoginPage } from "../pages/LoginPage";
import { DashboardPage } from "../pages/DashboardPage";
import { AdminAgentsPage } from "../pages/AdminAgentsPage";
import { AdminAgentsMonitoringPage } from "../pages/AdminAgentsMonitoringPage";
import { AdminBlueprintsPage } from "../pages/AdminBlueprintsPage";
import { AdminInstancesPage } from "../pages/AdminInstancesPage";
import { AdminWebhooksPage } from "../pages/AdminWebhooksPage";
import { AdminJobsPage } from "../pages/AdminJobsPage";
import { AdminSystemPage } from "../pages/AdminSystemPage";
import { InstanceDetailPage } from "../pages/InstanceDetailPage";
import { AccountPage } from "../pages/AccountPage";
import { SshKeysPage } from "../pages/SshKeysPage";
import { RegisterPage } from "../pages/RegisterPage";
import { ForgotPasswordPage } from "../pages/ForgotPasswordPage";
import { ResetPasswordPage } from "../pages/ResetPasswordPage";
import { VerifyEmailPage } from "../pages/VerifyEmailPage";
import { ShopPage } from "../pages/ShopPage";
import { OrdersPage } from "../pages/OrdersPage";
import { AdminProductsPage } from "../pages/AdminProductsPage";
import { AdminOrdersPage } from "../pages/AdminOrdersPage";
import { ImpressumPage, DatenschutzPage, AgbPage } from "../pages/LegalPages";
import { NotFoundPage } from "../pages/NotFoundPage";
import { loginUrl } from "../lib/redirect";
import { isAuthenticated } from "../services/api";
import { useCurrentUser } from "../hooks/useCurrentUser";
import { LoadingState } from "../components/ui";

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

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/impressum" element={<ImpressumPage />} />
        <Route path="/datenschutz" element={<DatenschutzPage />} />
        <Route path="/agb" element={<AgbPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/password-reset" element={<ForgotPasswordPage />} />
        <Route path="/password-reset/confirm" element={<ResetPasswordPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
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
        <Route path="/admin/orders" element={<ProtectedRoute><AdminRoute><AdminOrdersPage /></AdminRoute></ProtectedRoute>} />
        <Route path="/account" element={<ProtectedRoute><AccountPage /></ProtectedRoute>} />
        <Route path="/account/ssh-keys" element={<ProtectedRoute><SshKeysPage /></ProtectedRoute>} />
        <Route path="*" element={<ProtectedRoute><NotFoundPage /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  );
}
