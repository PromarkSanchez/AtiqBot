// src/App.tsx (VERSIÓN SIMPLIFICADA FINAL)
import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import AdminLayout from './components/layout/AdminLayout';
import { useAuth } from './contexts/AuthContext';
// Importa tus páginas
import AdminUsersPage from './pages/AdminUsersPage';
import AdminRolesPage from './pages/AdminRolesPage';
import AdminMenusPage from './pages/AdminMenusPage';
import AdminApiClientsPage from './pages/AdminApiClientsPage';
import AdminDbConnectionsPage from './pages/AdminDbConnectionsPage';
import AdminDocSourcesPage from './pages/AdminDocSourcesPage';
import AdminContextDefinitionsPage from './pages/AdminContextDefinitionsPage';
import AdminSecurityPage from './pages/AdminSecurityPage';
import AdminChatTestPage from './pages/AdminChatTestPage';
import AccessDeniedPage from './pages/AccessDeniedPage'; // <-- Nueva página
import AdminLlmModelsPage from './pages/AdminLlmModelsPage';
import AdminVirtualAgentsPage from './pages/AdminVirtualAgentsPage';
import AdminWebchatCustomizerPage from './pages/AdminWebchatCustomizerPage'; 

const ProtectedRoute: React.FC = () => {
    const { isAuthenticated } = useAuth();
    return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
};

function App() {
  const { isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900">
        Cargando...
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/access-denied" element={<AccessDeniedPage />} />

      {/* RUTA PROTEGIDA (SOLO AUTENTICACIÓN) */}
      <Route path="/admin" element={<ProtectedRoute />}>
        {/* LAYOUT GENERAL. TODAS las páginas de admin van aquí dentro */}
        <Route element={<AdminLayout />}>
          <Route index element={<Navigate to="users" replace />} />
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="roles" element={<AdminRolesPage />} />
          <Route path="menus" element={<AdminMenusPage />} />
          <Route path="api-clients" element={<AdminApiClientsPage />} />
          <Route path="db-connections" element={<AdminDbConnectionsPage />} />
          <Route path="doc-sources" element={<AdminDocSourcesPage />} />
          <Route path="context-definitions" element={<AdminContextDefinitionsPage />} />
          <Route path="profile/security" element={<AdminSecurityPage />} />
          <Route path="test-chat" element={<AdminChatTestPage />} />
          <Route path="/admin/llm-models" element={<AdminLlmModelsPage />} />
          <Route path="/admin/virtual-agents" element={<AdminVirtualAgentsPage />} />
          <Route path="webchat-customizer" element={<AdminWebchatCustomizerPage />} />

        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default App;