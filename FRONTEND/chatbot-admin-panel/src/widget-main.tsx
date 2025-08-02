// Archivo: src/widget-main.tsx

import React, { useEffect } from 'react'; // <--- Añadido useEffect
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import axios from 'axios';
import ChatbotPreview from './components/webchat/ChatbotPreview';
import type { WebchatUIConfig } from './services/api/schemas';
import './index.css';

const publicAxios = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000' });
const queryClient = new QueryClient({
    defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

const WidgetApp: React.FC = () => {
  const urlParams = new URLSearchParams(window.location.search);
  const apiKey = urlParams.get('apiKey');
  const appId = urlParams.get('appId');

  // ---> ¡NUEVO CÓDIGO! <---
  // Este efecto se ejecuta una sola vez cuando el componente se monta.
  useEffect(() => {
    // Busca los elementos <html> y <body> DENTRO del iframe.
    const htmlElement = document.documentElement;
    const bodyElement = document.body;
    
    // Les aplica un fondo transparente explícitamente.
    // Esto sobreescribe cualquier estilo que Tailwind pueda haber inyectado.
    if (htmlElement) htmlElement.style.backgroundColor = 'transparent';
    if (bodyElement) bodyElement.style.backgroundColor = 'transparent';
  }, []); // El array vacío [] asegura que se ejecute solo una vez.

  
  const { data: config, isLoading, isError, error } = useQuery<WebchatUIConfig>({
      queryKey: ['webchatConfig', apiKey],
      queryFn: async () => {
          if (!apiKey) throw new Error('Falta API Key');
          const response = await publicAxios.get('/api/v1/public/webchat-config', {
              headers: { 'X-API-KEY': apiKey },
          });
          return response.data;
      },
      enabled: !!apiKey,
  });

  if (!apiKey || !appId) return null;
  if (isLoading) return null;
  if (isError || !config) {
    console.error("AtiqTec Chatbot: Error al cargar configuración.", error);
    return null;
  }
  
  return (
    <ChatbotPreview
        config={config}
        apiKey={apiKey}
        applicationId={appId}
    />
  );
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <WidgetApp />
    </QueryClientProvider>
  </React.StrictMode>
);