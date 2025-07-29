// src/pages/AccessDeniedPage.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldExclamationIcon } from '@heroicons/react/24/solid';
import { Button } from '../components/shared/Button';

const AccessDeniedPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900 flex flex-col justify-center items-center p-4">
      <div className="text-center bg-white dark:bg-slate-800 p-8 sm:p-12 rounded-lg shadow-2xl max-w-lg w-full">
        <ShieldExclamationIcon className="w-16 h-16 text-red-500 dark:text-red-400 mx-auto mb-6" />
        <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-800 dark:text-white mb-2">
          Acceso Denegado
        </h1>
        <p className="text-base sm:text-lg text-gray-600 dark:text-gray-300 mb-8">
          No tienes los permisos necesarios para acceder a esta sección o a la página solicitada.
        </p>
        <Button onClick={() => navigate('/admin')} size="lg">
          Volver a un lugar seguro
        </Button>
      </div>
    </div>
  );
};

export default AccessDeniedPage;