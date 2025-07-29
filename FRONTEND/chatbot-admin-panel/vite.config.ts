import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Ya lo tenías bien, esto permite el acceso externo
    port: 5173,      // El puerto que estás usando
    
    // --- LÍNEA A AÑADIR ---
    allowedHosts: ['admin-ia.cayetano.pe'],

    // strictPort: true, // Opcional (si lo quieres, lo dejas)
  }
})