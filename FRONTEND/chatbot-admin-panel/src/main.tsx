// src/main.tsx
import React from 'react'; // React suele ser importado así
import ReactDOM from 'react-dom/client'; // 'react-dom/client' es el import correcto
import App from './App.tsx';
import './index.css'; // Tus estilos globales y Tailwind


// 1. Importa QueryClient y QueryClientProvider de @tanstack/react-query
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// 2. (Opcional pero recomendado) Importa las Devtools de React Query
 
import { BrowserRouter } from 'react-router-dom'; // <-- IMPORTAR BROWSERROUTER
import { AuthProvider } from './contexts/AuthContext'; // <-- IMPORTAR

// 3. Crea una instancia de QueryClient
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Aquí puedes poner configuraciones por defecto para todas tus queries
      // por ejemplo, para evitar refetch demasiado frecuentes durante el desarrollo:
      // refetchOnWindowFocus: false, 
      // staleTime: Infinity, // Las queries no se considerarán "stale" automáticamente
      // O un tiempo de stale más razonable para producción:
      // staleTime: 1000 * 60 * 5, // 5 minutos
    },
  },
});

// createRoot ya lo tienes, solo modificamos el render
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider> {/* <-- ENVOLVER CON AUTHPROVIDER */}
          <App />
        
        </AuthProvider> {/* <-- CERRAR AUTHPROVIDER */}
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>
);