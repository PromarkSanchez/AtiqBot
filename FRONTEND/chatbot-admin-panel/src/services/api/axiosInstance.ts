// src/services/api/axiosInstance.ts
import Axios, { type AxiosRequestConfig, AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export const AXIOS_INSTANCE = Axios.create({ baseURL: API_BASE_URL });

export const axiosInstance = <T>(
  config: AxiosRequestConfig,
  options?: AxiosRequestConfig,
): Promise<T> => {
  const source = Axios.CancelToken.source();

  // Función para construir los headers dinámicamente
  const buildHeaders = () => {
    const dynamicHeaders: Record<string, string> = {};

    // 1. Header de Autorización del Admin
    const sessionToken = localStorage.getItem('session_token');
    if (sessionToken) {
      dynamicHeaders['Authorization'] = `Bearer ${sessionToken}`;
    }

    // 2. Headers especiales para la prueba del chat desde el panel de admin
    const isChatTestContext = config.url?.includes('/api/v1/chat');
    if (isChatTestContext) {
      const testApiKey = localStorage.getItem('admin_test_x_api_key');
      const testAppId = localStorage.getItem('admin_test_x_application_id');

      if (testApiKey) {
        dynamicHeaders['X-API-Key'] = testApiKey;
      }
      if (testAppId) {
        dynamicHeaders['X-Application-ID'] = testAppId;
      }
    }
    
    return dynamicHeaders;
  };
  
  // Combina todos los headers en el orden correcto de prioridad:
  // 1. Headers base del AXIOS_INSTANCE (si los tuviera).
  // 2. Headers dinámicos que acabamos de construir (como Authorization).
  // 3. Headers específicos de la llamada (de Orval, por ejemplo).
  // 4. Headers de opciones extra que pasemos manualmente.
  const finalHeaders = {
    ...AXIOS_INSTANCE.defaults.headers.common,
    ...buildHeaders(),
    ...config.headers,
    ...options?.headers,
  };
  
  // Limpiar headers que no son válidos (no son string)
  Object.keys(finalHeaders).forEach(key => {
    if (typeof (finalHeaders as any)[key] !== 'string') {
        delete (finalHeaders as any)[key];
    }
  });


  const requestConfig: AxiosRequestConfig = {
    ...config,
    ...options,
    headers: finalHeaders,
    cancelToken: source.token,
  };

  const promise = AXIOS_INSTANCE(requestConfig)
    .then(({ data }) => data)
    .catch((error: AxiosError) => {
      // Log detallado del error
      console.error("Axios Request Error:", {
        message: error.message,
        url: error.config?.url,
        method: error.config?.method,
        status: error.response?.status,
        requestHeadersSent: error.config?.headers,
        responseData: error.response?.data,
        axiosErrorCode: error.code,
      });
      return Promise.reject(error);
    });
  
  // Para cancelar peticiones
  // @ts-ignore
  promise.cancel = () => {
    source.cancel('Query Request Canceled!');
  };

  return promise as Promise<T>;
};

export type ErrorType<ErrorData = any> = AxiosError<ErrorData>;

export default axiosInstance;