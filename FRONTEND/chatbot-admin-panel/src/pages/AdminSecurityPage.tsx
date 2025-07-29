// src/pages/AdminSecurityPage.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom'; // <--- IMPORTAR useNavigate
import PageHeader from '../components/ui/PageHeader';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/shared/Button';
import MfaSetup from '../components/admin/security/MfaSetup';
import { ShieldCheckIcon, ShieldExclamationIcon } from '@heroicons/react/24/solid';
import toast, { Toaster } from 'react-hot-toast';


const AdminSecurityPage: React.FC = () => {
  const { user, logout } = useAuth(); // <-- Obtenemos la función logout
  const navigate = useNavigate(); // <-- Hook para navegar
  const [isSettingUpMfa, setIsSettingUpMfa] = useState(false);
  
  const isMfaEnabled = user?.isMfaEnabled || false;

  const handleDeactivateMfa = () => {
      toast('Funcionalidad de desactivar MFA pendiente.', { icon: '🧑‍💻' });
  }

  return (
    <div>
      <Toaster position="top-center" />
      <PageHeader title="Seguridad de la Cuenta" subtitle="Gestiona la autenticación de dos factores (MFA) para proteger tu acceso." />
      
      <div className="mt-8 max-w-2xl mx-auto bg-white dark:bg-slate-800 p-6 rounded-lg shadow-md border border-gray-200 dark:border-slate-700">
        <h2 className="text-xl font-semibold mb-4 text-gray-800 dark:text-white">Autenticación de Dos Factores (MFA)</h2>
        
        {/* Tu JSX para los banners se mantiene igual... */}
        {isMfaEnabled ? (
            <div className="flex items-start p-4 bg-green-50 dark:bg-green-900/20 border-l-4 border-green-500 rounded-md">
                <ShieldCheckIcon className="h-8 w-8 text-green-500 mr-4 flex-shrink-0 mt-1" />
                <div>
                    <p className="font-bold text-green-800 dark:text-green-300">MFA está ACTIVO</p>
                    <p className="text-sm text-green-700 dark:text-green-400 mt-1">Tu cuenta está protegida con un segundo factor de autenticación.</p>
                    <Button variant="danger" size="sm" className="mt-4" onClick={handleDeactivateMfa}>Desactivar MFA</Button>
                </div>
            </div>
        ) : !isSettingUpMfa && (
            <div className="flex items-start p-4 bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-500 rounded-md">
                <ShieldExclamationIcon className="h-8 w-8 text-yellow-500 mr-4 flex-shrink-0 mt-1" />
                <div>
                    <p className="font-bold text-yellow-800 dark:text-yellow-300">MFA está INACTIVO</p>
                    <p className="text-sm text-yellow-700 dark:text-yellow-400 mt-1">Se recomienda encarecidamente activar MFA para una mayor seguridad de tu cuenta.</p>
                    <Button onClick={() => setIsSettingUpMfa(true)} variant="primary" size="sm" className="mt-4">
                        Activar MFA ahora
                    </Button>
                </div>
            </div>
        )}

        {isSettingUpMfa && (
          <MfaSetup 
            onSetupComplete={() => {
              // --- ¡LÓGICA CORREGIDA! ---
              toast.success("¡MFA activado! Por seguridad, debes iniciar sesión de nuevo.", {
                  duration: 6000,
                  icon: '🔒'
              });
              // Esperamos un par de segundos para que el usuario lea el toast,
              // luego cerramos sesión y lo enviamos al login.
              setTimeout(() => {
                  logout();
                  navigate('/login');
              }, 2500);
            }} 
            onCancel={() => setIsSettingUpMfa(false)}
          />
        )}
      </div>
    </div>
  );
};

export default AdminSecurityPage;