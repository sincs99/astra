import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
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
import { isAuthenticated } from "../services/api";

/**
 * Schuetzt Routen: Leitet zu /login um wenn nicht eingeloggt.
 */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
        <Route path="/admin/agents" element={<ProtectedRoute><AdminAgentsPage /></ProtectedRoute>} />
        <Route path="/admin/agents/monitoring" element={<ProtectedRoute><AdminAgentsMonitoringPage /></ProtectedRoute>} />
        <Route path="/admin/blueprints" element={<ProtectedRoute><AdminBlueprintsPage /></ProtectedRoute>} />
        <Route path="/admin/instances" element={<ProtectedRoute><AdminInstancesPage /></ProtectedRoute>} />
        <Route path="/admin/webhooks" element={<ProtectedRoute><AdminWebhooksPage /></ProtectedRoute>} />
        <Route path="/admin/jobs" element={<ProtectedRoute><AdminJobsPage /></ProtectedRoute>} />
        <Route path="/admin/system" element={<ProtectedRoute><AdminSystemPage /></ProtectedRoute>} />
        <Route path="/instances/:uuid" element={<ProtectedRoute><InstanceDetailPage /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  );
}
