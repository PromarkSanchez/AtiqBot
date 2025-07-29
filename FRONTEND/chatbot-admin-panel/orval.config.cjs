// orval.config.js (o orval.config.cjs)
// Si es .cjs, usa 'const ... = require(...)' para 'path' si es necesario.
// Para este ejemplo, asumimos que 'path' no es crítico aún.

module.exports = {
  chatbotApi: { // Puedes nombrar esta clave como quieras
    input: {
        // ¡¡¡IMPORTANTE: AJUSTA ESTA URL A TU BACKEND!!!
        // Si tu backend está en el mismo PC, suele ser 127.0.0.1 o localhost
        target: 'http://127.0.0.1:8000/openapi.json', 
    },
    output: {
      mode: 'split',
      target: 'src/services/api/endpoints.ts', // Donde se guardarán los endpoints
      schemas: 'src/services/api/schemas',    // Donde se guardarán los tipos/schemas
      client: 'react-query', // Queremos hooks para React Query
      override: {
        mutator: {
          path: './src/services/api/axiosInstance.ts', // Archivo para nuestra instancia de Axios
          name: 'axiosInstance', // Nombre de la función exportada en axiosInstance.ts
        },
      },
    },
    
  },
};