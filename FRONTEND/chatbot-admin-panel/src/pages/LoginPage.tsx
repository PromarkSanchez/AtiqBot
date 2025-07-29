// src/pages/LoginPage.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  useLoginAdminUnificadoApiV1AdminAuthLoginPost as useLoginAdminWithAdAndHandleMfaApiV1AdminAuthLoginPost,
  useVerifyMfaCodeAfterAdLoginApiV1AdminAuthVerifyMfaPost 
} from '../services/api/endpoints';
import { useAuth } from '../contexts/AuthContext';
import type { AxiosError } from 'axios';
import type { HTTPValidationError, TokenSchema, PreMFATokenResponseSchema } from '../services/api/schemas'; 

type LoginApiResponse = TokenSchema | PreMFATokenResponseSchema | { detail?: any };
type MFAVerifySuccessResponse = TokenSchema;

const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [isMfaStep, setIsMfaStep] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const navigate = useNavigate();
  const { login: authLoginContext } = useAuth();

  const loginMutation = useLoginAdminWithAdAndHandleMfaApiV1AdminAuthLoginPost();
  const mfaVerifyMutation = useVerifyMfaCodeAfterAdLoginApiV1AdminAuthVerifyMfaPost();

  const handleLoginSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoginError(null);
    try {
      const result = await loginMutation.mutateAsync({
        data: { username, password }
      }) as LoginApiResponse;

      if (result && 'access_token' in result && result.access_token) {
        authLoginContext(result.access_token);
        navigate('/admin', { replace: true });
      } else if (result && 'pre_mfa_token' in result && result.pre_mfa_token) {
        // En este punto, no necesitamos guardar nada extra.
        // El `username` ya está en nuestro estado `username`.
        setIsMfaStep(true);
        setLoginError(result.message || 'Se requiere verificación de segundo factor (MFA).');
      } else {
        if (result && 'detail' in result && result.detail) {
            if (Array.isArray(result.detail)) {
                setLoginError(result.detail.map((err: any) => err.msg).join('; '));
            } else {
                setLoginError(String(result.detail));
            }
        } else {
            setLoginError('Respuesta inesperada del servidor durante el login.');
        }
      }

    } catch (error) {
      const axiosError = error as AxiosError<HTTPValidationError>;
      const apiErrorData = axiosError.response?.data;
      
      let errorMessageToShow = 'Error de login. Inténtalo de nuevo.';
      if (apiErrorData && apiErrorData.detail) {
        if (Array.isArray(apiErrorData.detail)) {
          errorMessageToShow = apiErrorData.detail.map((err: any) => err.msg).join('; ');
        } else if (typeof apiErrorData.detail === 'string') {
          errorMessageToShow = apiErrorData.detail;
        }
      } else if (axiosError.message) {
        errorMessageToShow = axiosError.message;
      }
      setLoginError(errorMessageToShow);
    }
  };

  const handleMfaSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoginError(null);

    // Verificamos que tenemos el username que inició el proceso
    if (!username) {
        setLoginError("No se ha especificado un usuario. Por favor, reinicia el proceso.");
        setIsMfaStep(false);
        return;
    }
    try {
      // --- SOLUCIÓN: Volvemos a la estructura de payload que tenías, porque es la correcta según los tipos. ---
      const result = await mfaVerifyMutation.mutateAsync({
        data: { username_ad: username, mfa_code: mfaCode }
      }) as MFAVerifySuccessResponse;

      if (result && 'access_token' in result && result.access_token) {
        authLoginContext(result.access_token);
        setIsMfaStep(false);
        navigate('/admin', { replace: true });
      } else {
        setLoginError('Respuesta inesperada del servidor durante la verificación MFA.');
      }
    } catch (error) {
      const axiosError = error as AxiosError<HTTPValidationError>;
      const apiErrorData = axiosError.response?.data;
      
      let errorMessageToShow = 'Código MFA inválido o error en la verificación.';
      if (apiErrorData && apiErrorData.detail) {
        if (Array.isArray(apiErrorData.detail)) {
          errorMessageToShow = apiErrorData.detail.map((err: any) => err.msg).join('; ');
        } else if (typeof apiErrorData.detail === 'string') {
          errorMessageToShow = apiErrorData.detail;
        }
      } else if (axiosError.message) {
        errorMessageToShow = axiosError.message;
      }
      setLoginError(errorMessageToShow);
    }
  };
  
  const handleGoBackToLogin = () => {
    setIsMfaStep(false);
    setLoginError(null);
    setPassword('');
    setMfaCode('');
  };


  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900 p-4">
      <div className="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-xl w-full max-w-md">
        <h1 className="text-2xl font-bold text-center text-gray-700 dark:text-white mb-6">
          {isMfaStep ? 'Verificar Código MFA' : 'Login de Administrador'}
        </h1>

        {!isMfaStep ? (
          <form onSubmit={handleLoginSubmit} className="space-y-6">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-600 dark:text-gray-300">Usuario (DNI)</label>
              <input id="username" name="username" type="text" autoComplete="username" required value={username} onChange={(e) => setUsername(e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-gray-700 dark:text-white" />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-600 dark:text-gray-300">Contraseña</label>
              <input id="password" name="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-gray-700 dark:text-white" />
            </div>
            {loginError && !isMfaStep && <p className="text-sm text-red-500 dark:text-red-400">{loginError}</p>}
            {loginError && isMfaStep && !mfaVerifyMutation.isError && <p className="text-sm text-yellow-500 dark:text-yellow-400">{loginError}</p>}
            <div>
              <button type="submit" disabled={loginMutation.isPending} className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 dark:focus:ring-offset-gray-800 disabled:opacity-50">
                {loginMutation.isPending ? 'Ingresando...' : 'Ingresar'}
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleMfaSubmit} className="space-y-6">
            <p className="text-sm text-center text-gray-600 dark:text-gray-300">
              Para el usuario <strong>{username}</strong>, ingresa el código de 6 dígitos de tu app de autenticación.
            </p>
            <div>
              <label htmlFor="mfaCode" className="block text-sm font-medium text-gray-600 dark:text-gray-300">Código MFA (6 dígitos)</label>
              <input id="mfaCode" name="mfaCode" type="text" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required autoFocus value={mfaCode} onChange={(e) => setMfaCode(e.target.value)} className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-gray-700 dark:text-white" />
            </div>
            {mfaVerifyMutation.isError && <p className="text-sm text-red-500 dark:text-red-400">{loginError}</p>}
            <div>
              <button type="submit" disabled={mfaVerifyMutation.isPending} className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 dark:focus:ring-offset-gray-800 disabled:opacity-50">
                {mfaVerifyMutation.isPending ? 'Verificando...' : 'Verificar Código'}
              </button>
            </div>
            <button type="button" onClick={handleGoBackToLogin} className="mt-2 w-full text-sm text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300">
                Volver al login
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

export default LoginPage;