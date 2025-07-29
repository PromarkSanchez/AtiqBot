// src/services/api/axiosInstance.ts
import Axios, { type AxiosRequestConfig, AxiosError, type RawAxiosRequestHeaders } from 'axios';

// Asegúrate que VITE_API_BASE_URL esté definido en tu .env
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export const AXIOS_INSTANCE = Axios.create({ baseURL: API_BASE_URL });

export const axiosInstance = <T>(
  config: AxiosRequestConfig,
  options?: AxiosRequestConfig,
): Promise<T> => {
  const source = Axios.CancelToken.source();

  // Clonar los headers para evitar mutar el config original
  const requestSpecificHeaders: Record<string, string> = {};
  const combinedHeadersConfig = { ...(config.headers || {}), ...(options?.headers || {}) };

  for (const key in combinedHeadersConfig) {
    if (Object.prototype.hasOwnProperty.call(combinedHeadersConfig, key)) {
      const value = (combinedHeadersConfig as any)[key];
      // Solo incluir headers si son string, number o boolean
      if (typeof value === 'string') {
        requestSpecificHeaders[key] = value;
      } else if (typeof value === 'number' || typeof value === 'boolean') {
        requestSpecificHeaders[key] = String(value);
      }
    }
  }
  
  // Headers por defecto o globales que podrían aplicarse
  const defaultHeaders: Record<string, string> = {};

  // 1. Header de Autorización (Token de Sesión del Admin)
  // Asumiendo que 'session_token' es para el panel de admin
  const sessionToken = localStorage.getItem('session_token'); // o Cookies.get('tu_cookie_admin')
  if (sessionToken) {
     defaultHeaders['Authorization'] = `Bearer ${sessionToken}`;
  }

  // 2. Headers para la Prueba de Chat (X-API-Key, X-Application-ID)
  // Estos solo se aplican si es una petición a la ruta del chat Y los ítems están en localStorage.
  const isChatTestContext = config.url?.includes('/api/v1/chat'); // Ajusta la URL si es necesario

  if (isChatTestContext) {
    const testApiKey = localStorage.getItem('admin_test_x_api_key');
    const testAppId = localStorage.getItem('admin_test_x_application_id');

    if (testApiKey) {
      defaultHeaders['X-API-Key'] = testApiKey; // Sobrescribe cualquier X-API-Key global si estamos en contexto de chat de prueba
    }
    if (testAppId) {
      defaultHeaders['X-Application-ID'] = testAppId; // Idem para X-Application-ID
    }
  } else {
    // Aquí podrías poner lógica para headers X-API-Key/X-Application-ID globales
    // si el *panel de administración mismo* necesitara autenticarse con una API Key específica
    // para TODAS sus llamadas (además del Bearer token). Generalmente no es el caso.
    // const globalPanelApiKey = localStorage.getItem('global_panel_x_api_key');
    // if (globalPanelApiKey) defaultHeaders['X-API-Key'] = globalPanelApiKey;
  }
  
  // Asegurar Content-Type si la petición tiene datos (body) y no se ha seteado ya
  // Orval usualmente maneja Content-Type basado en el schema OpenAPI, pero esto es un fallback.
  if (config.data && !requestSpecificHeaders['Content-Type'] && !requestSpecificHeaders['content-type']) {
      defaultHeaders['Content-Type'] = 'application/json';
  }

  // Combinar headers: los específicos de la petición tienen prioridad sobre los por defecto/globales.
  const finalHeaders = { ...defaultHeaders, ...requestSpecificHeaders };

  const requestConfig: AxiosRequestConfig = {
    ...config,
    ...options,
    headers: finalHeaders,
    cancelToken: source.token,
  };

  const promise = AXIOS_INSTANCE(requestConfig)
    .then(({ data }) => data)
    .catch(error => {
      // Log detallado del error
      console.error("Axios Request Error:", {
        message: error.message,
        url: error.config?.url,
        method: error.config?.method,
        status: error.response?.status,
        requestPayload: error.config?.data, // Cuidado si hay datos sensibles
        requestHeadersSent: requestConfig.headers, // Muestra los headers que se intentaron enviar
        responseData: error.response?.data,
        axiosErrorCode: error.code, // e.g., 'ECONNABORTED' for timeout
      });
      return Promise.reject(error);
    });

  // Para cancelar peticiones (si se usa con React Query `cancelQueries`)
  // @ts-ignore - Orval o React Query podrían intentar usar esta propiedad.
  promise.cancel = () => {
    source.cancel('Query Request Canceled!');
  };

  return promise as Promise<T>;
};

// Tipado para el error, útil en los hooks de React Query
export type ErrorType<ErrorData = any> = AxiosError<ErrorData>;

export default axiosInstance;