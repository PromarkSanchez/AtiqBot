// src/components/auth/PermissionRoute.tsx
import React from 'react';
import { useLocation, Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

// Un componente de Loader simple para usarlo mientras se verifican los permisos.
const PermissionLoader: React.FC = () => (
    <div className="flex h-full w-full items-center justify-center p-20">
        <p className="animate-pulse text-gray-500 dark:text-gray-400">Verificando permisos...</p>
    </div>
);


const PermissionRoute: React.FC = () => {
  const { user, hasAccessToRoute, authorizedMenus, isLoadingMenus } = useAuth();
  const location = useLocation();

  // ----- ESTA ES LA LÓGICA MÁS IMPORTANTE -----
  
  // 1. Caso Base: El usuario no está definido o el contexto principal todavía está cargando.
  //    ProtectedRoute ya debería haberlo manejado, pero es una salvaguarda.
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  // 2. Esperar Datos: Si la query para obtener los menús está en curso,
  //    Y el usuario no es SuperAdmin (quien no necesita esperar), MOSTRAMOS UN LOADER.
  //    Esto DETIENE la ejecución y previene una decisión de redirección prematura.
  if (isLoadingMenus && !user.roles.includes('SuperAdmin')) {
    return <PermissionLoader />;
  }

  // A partir de aquí, o somos SuperAdmin, o isLoadingMenus es false y tenemos datos.

  // 3. Tomar la Decisión de Acceso
  const canAccess = hasAccessToRoute(location.pathname);
  
  if (canAccess) {
    // Si tiene permiso, renderiza el componente de la página real.
    return <Outlet />;
  }
  
  // 4. Denegar y Redirigir si no hay acceso.
  //    (Llega aquí si canAccess es false DESPUÉS de que los menús hayan cargado)

  // Primero, comprobamos si el usuario no tiene NINGÚN menú.
  // Esto es un caso especial para evitar bucles.
  if (authorizedMenus.length === 0 && !user.roles.includes('SuperAdmin')) {
    // Podrías tener una página dedicada para esto.
    return <Navigate to="/access-denied" replace />; 
  }

  // Si tiene menús pero no el específico al que intenta acceder,
  // lo mandamos a la primera página segura que tenga en su lista.
  const safeRedirectPath = authorizedMenus[0]?.frontend_route || '/admin'; // fallback a /admin

  return <Navigate to={safeRedirectPath} replace />;
};

export default PermissionRoute;