// Archivo: vite.config.ts

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: ['admin-ia.cayetano.pe','localhost'],
    // cors: true  <-- Opcional, pero bueno tenerlo para desarrollo
  },
  preview: {
    port: 4173,
    host: true
  },
  build: {
    rollupOptions: {
      // SOLO DOS PUNTOS DE ENTRADA: tu app principal y la página del chatbot
      input: {
        main: path.resolve(__dirname, 'index.html'),
        chatbot: path.resolve(__dirname, 'chatbot.html'),
      }
      // No necesitamos una configuración de 'output' compleja,
      // dejaremos que Vite maneje los nombres de los archivos por defecto.
    }
  }
});