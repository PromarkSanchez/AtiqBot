// src/components/admin/security/MfaSetup.tsx
import React, { useState, Suspense } from 'react';
import {
  useMfaSetupInitiateApiV1AdminAuthMfaSetupInitiatePost as useInitiateMfa,
  useMfaSetupConfirmApiV1AdminAuthMfaSetupConfirmPost as useConfirmMfa,
} from '../../../services/api/endpoints';
import { Button } from '../../shared/Button';
import toast from 'react-hot-toast';

// --- SOLUCIÓN DEFINITIVA PARA LAZY LOADING ---
const QRCode = React.lazy(() => 
  import('qrcode.react').then(module => ({ default: module.QRCodeCanvas }))
);

const QRCodeLoader: React.FC = () => (
  <div className="w-[224px] h-[224px] p-4 bg-gray-100 dark:bg-slate-700 rounded-lg animate-pulse flex items-center justify-center">
    <p className="text-xs text-gray-500">Generando QR...</p>
  </div>
);


interface MfaSetupProps {
  onSetupComplete: () => void;
  onCancel: () => void;
}

const MfaSetup: React.FC<MfaSetupProps> = ({ onSetupComplete, onCancel }) => {
  // ... (el resto del código del componente no cambia en absoluto) ...
  const [provisioningUri, setProvisioningUri] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState('');

  const initiateMutation = useInitiateMfa({
    mutation: {
      onSuccess: (data) => {
        setProvisioningUri(data.otpauth_url);
        toast.success("Paso 1: Escanea el código QR.");
      },
      onError: (err: any) => {
        toast.error(err.message || "Error al iniciar la configuración de MFA.");
      },
    },
  });

  const confirmMutation = useConfirmMfa({
    mutation: {
      onSuccess: () => {
        onSetupComplete(); 
      },
      onError: (err: any) => {
        toast.error(err.message || "Código incorrecto o expirado.");
      },
    },
  });

  const handleStartSetup = () => {
    initiateMutation.mutate();
  };
  
  const handleConfirmCode = () => {
    if (mfaCode.length === 6 && /^\d{6}$/.test(mfaCode)) {
      confirmMutation.mutate({ data: { mfa_code: mfaCode } });
    } else {
      toast.error("El código debe ser de 6 dígitos numéricos.");
    }
  };

  if (!provisioningUri) {
    return (
      <div className="text-center p-6 bg-white dark:bg-slate-800 rounded-lg shadow-md">
        <p className="mb-4 text-gray-600 dark:text-gray-300">Activa la autenticación de dos factores para una capa extra de seguridad.</p>
        <Button onClick={handleStartSetup} isLoading={initiateMutation.isPending} size="lg">
          Comenzar Configuración
        </Button>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-800 p-6 rounded-lg shadow-md transition-opacity duration-500 animate-fadeIn">
       <h3 className="text-lg font-semibold mb-4 text-center text-gray-900 dark:text-white">Paso 2: Escanea y Confirma</h3>

      <div className="flex flex-col items-center">
        <p className="text-sm text-center text-gray-600 dark:text-gray-300 mb-4">
          Abre tu app de autenticación y escanea este código.
        </p>
        
        <Suspense fallback={<QRCodeLoader />}>
            <div className="p-2 bg-white inline-block rounded-lg border">
                <QRCode value={provisioningUri} size={200} level="M" />
            </div>
        </Suspense>

        <details className="mt-4 text-center w-full max-w-sm">
          <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">
            ¿No puedes escanear? Ver clave manual
          </summary>
          <div className="mt-2 p-2 bg-gray-100 dark:bg-slate-700 rounded">
            <p className="text-xs text-gray-500">Ingresa esta clave en tu app:</p>
            <code className="text-xs font-mono break-all block mt-1">
              {provisioningUri}
            </code>
          </div>
        </details>
      </div>
      
      <hr className="my-6 border-gray-200 dark:border-slate-700" />

      <h3 className="text-lg font-semibold mb-2 text-center text-gray-900 dark:text-white">Paso 3: Verifica tu Dispositivo</h3>
      <div className="flex flex-col items-center gap-4">
        <p className="text-sm text-center text-gray-600 dark:text-gray-300">
          Ingresa el código de 6 dígitos que aparece en tu app.
        </p>
        <div className="flex items-center space-x-3">
              <input
              type="text"
              maxLength={6}
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ''))}
              className="w-40 text-center text-2xl tracking-[.2em] font-mono bg-white dark:bg-slate-900 border border-gray-300 dark:border-slate-600 rounded-md p-2 text-gray-900 dark:text-white focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="123456"
              aria-label="Código de 6 dígitos"
            />
            <Button onClick={handleConfirmCode} isLoading={confirmMutation.isPending}>
                Verificar
            </Button>
        </div>
      </div>
      <div className="flex justify-center mt-6">
        <Button variant="secondary" onClick={onCancel} disabled={confirmMutation.isPending}>Cancelar</Button>
      </div>
    </div>
  );
};

export default MfaSetup;